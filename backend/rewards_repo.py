"""의상 보상 · 옷장 (요구사항정의서 FR-039 일기 주간 보상, FR-040 · FR-045 동화 구간 보상, FR-041 캐릭터 옷장).

세는 일은 progress_repo.py(낙준)가 하고, 여기서는 '줄지 판단 · 받기 · 옷장'만 한다.
기준 숫자는 reward_rules.py 만 본다 (WEEK_MIN_DAYS, STORY_REWARD_CHAPTERS).
  clothes.required_count 칸은 NOT NULL 이라 같은 숫자로 채워 두지만 여기서는 읽지 않는다.
  옷은 reward_order 로 찾는다 (일기: 몇 번째로 주간 목표를 달성했는지, 동화: 그 주제 안에서 몇 번째 구간인지)

쓰는 표 (팀 DB 에 직접 만든 표라 temp/schema.sql 에는 없다. 의상 데이터는 temp/seed_clothes.sql)
  clothes                의상 목록
  reward_claims          보상 기록. achieved_at = 달성 확인 시각, claimed_at = 받은 시각 (NULL 이면 아직 안 받음)
  user_clothes           가진 옷
  user_equipped_clothes  입은 옷 (사용자당 한 줄, 부위 5칸)

일기 주간 보상 (FR-039)
  - 하루치(entries.day_done_at, 3문장)를 채운 날이 한 주(월~일)에 WEEK_MIN_DAYS 일이면 달성
  - 차수 = 주간 목표를 달성한 순서. 받은 순서가 아니다. 달성 못 한 주는 차수를 올리지 않는다
  - sync_diary_claims 가 달성했지만 기록이 없는 주를 날짜 순서대로 찾아 다음 차수로 reward_claims 에 적는다 (claimed_at = NULL)
    지난 날짜 일기는 3일 안에만 하루치가 되므로(DIARY_LATE_DAYS) 지난주가 이번 주보다 늦게 달성되는 일은 없다
  - 준비된 일기 의상을 다 받으면 더 적지 않는다 (그 뒤 처리는 미정, 화면에는 status 'none')

동화 구간 보상 (FR-040)
  - 같은 책에서 3문장 이상 쓴 장 수가 STORY_REWARD_CHAPTERS(3 · 6 · 10)에 닿으면 그 구간을 받을 수 있다
  - 옷은 책의 동화 주제에 연결된 세트의 구성품. 자유 주제('내가 정할래요')도 주제 하나로 보고 세트를 준다
    (주제가 NULL 인 옛 책도 books_repo 규칙대로 자유 주제로 본다). 주제에 옷이 없으면 clothes = None 이고 받을 수 없다
  - 받는 순간 reward_claims 에 적는다 (책 · 구간이 정해져 있어 미리 적어 둘 필요가 없다)

공통
  - 받기는 한 트랜잭션으로 reward_claims 와 user_clothes 를 함께 적는다. 두 번 받기는 UNIQUE 와 claimed_at 확인으로 막는다
  - 문장을 지워서 날짜 · 장 수가 줄어도 이미 받은 보상은 그대로 둔다 (progress_repo 주석과 같은 규칙)
"""
import datetime

import db
import progress_repo
import reward_rules as rules
from books_repo import BadRequest, _as_date, _now_str

SLOTS = ("top", "bottom", "hat", "shoes", "gloves")
SLOT_LABEL = {"top": "상의", "bottom": "하의", "hat": "모자", "shoes": "신발", "gloves": "장갑"}


class AlreadyClaimed(Exception):
    """이미 받은 보상을 다시 받으려 할 때 (API 에서 409)."""


def _clothes(r, prefix=""):
    """DB 한 줄에서 옷 정보만 꺼낸다. 옷이 없으면 None."""
    if r.get(prefix + "id") is None:
        return None
    return {"id": r[prefix + "id"], "name": r[prefix + "name"], "slot": r[prefix + "slot"],
            "slot_label": SLOT_LABEL.get(r[prefix + "slot"]), "image_url": r[prefix + "image_url"]}


# ── 일기 주간 보상 ──

def _achieved_weeks(q, user_id):
    """주간 목표를 달성한 주의 월요일 목록 (오래된 주부터). 일기 책이 여러 권이어도 같은 날짜는 하루로 센다."""
    rows = q.query(
        """SELECT w.week_start
             FROM (SELECT DISTINCT e.diary_date,
                          DATE_SUB(e.diary_date, INTERVAL WEEKDAY(e.diary_date) DAY) AS week_start
                     FROM entries e JOIN books b ON b.id = e.book_id
                    WHERE b.user_id = :uid AND b.kind = 'diary' AND e.day_done_at IS NOT NULL) AS w
            GROUP BY w.week_start
           HAVING COUNT(*) >= :need
            ORDER BY w.week_start""",
        {"uid": user_id, "need": rules.WEEK_MIN_DAYS})
    return [_as_date(r["week_start"]) for r in rows]


def sync_diary_claims(user_id):
    """달성했지만 아직 기록이 없는 주를 날짜 순서대로 다음 차수로 적는다 (아직 안 받은 상태). 새로 적은 줄 수를 돌려준다."""
    def work(tx):
        have = tx.query("""SELECT week_start, reward_order FROM reward_claims
                            WHERE user_id = :uid AND reward_kind = 'diary'""", {"uid": user_id})
        done = {_as_date(r["week_start"]) for r in have}
        order = max((r["reward_order"] for r in have), default=0)
        added = 0
        for week in _achieved_weeks(tx, user_id):
            if week in done:
                continue
            order += 1
            c = tx.query("SELECT id FROM clothes WHERE reward_kind = 'diary' AND reward_order = :o", {"o": order})
            if not c:                       # 준비된 일기 의상을 다 받았다
                break
            tx.insert("""INSERT INTO reward_claims (user_id, clothes_id, reward_kind, reward_order, week_start, achieved_at)
                         VALUES (:uid, :cid, 'diary', :o, :w, :now)""",
                      {"uid": user_id, "cid": c[0]["id"], "o": order, "w": week.isoformat(), "now": _now_str()})
            added += 1
        return added
    try:
        return db.run_in_transaction(work)
    except db.Conflict:                     # 같은 때 들어온 다른 요청이 먼저 적었다
        return 0


def diary_reward(user_id):
    """대시보드의 '이번 주 선물' (FR-039 · FR-042).
      progress    이번 주 하루치 진행 {start, end, days, count, need}
      this_week   {status, order, week_start, clothes}
                  status: locked 아직 / claimable 받을 수 있음 / claimed 받음 / none 준비된 의상을 다 받음
      unclaimed   받지 않은 지난주 보상 [{week_start, order, clothes}] (지난주 보상도 기한 없이 받을 수 있다)"""
    sync_diary_claims(user_id)
    week = progress_repo.week_status(user_id)
    start = _as_date(week["week_start"])
    claims = db.query(
        """SELECT r.week_start, r.reward_order, r.claimed_at,
                  c.id, c.name, c.slot, c.image_url
             FROM reward_claims r JOIN clothes c ON c.id = r.clothes_id
            WHERE r.user_id = :uid AND r.reward_kind = 'diary'
            ORDER BY r.reward_order""",
        {"uid": user_id})
    mine = next((r for r in claims if _as_date(r["week_start"]) == start), None)
    if mine:
        this_week = {"status": "claimed" if mine["claimed_at"] else "claimable", "order": mine["reward_order"],
                     "clothes": _clothes(mine)}
    else:
        order = len(claims) + 1             # 이번 주에 달성하면 받을 차수
        nxt = db.query("""SELECT id, name, slot, image_url FROM clothes
                           WHERE reward_kind = 'diary' AND reward_order = :o""", {"o": order})
        this_week = {"status": "locked" if nxt else "none", "order": order,
                     "clothes": _clothes(nxt[0]) if nxt else None}
    this_week["week_start"] = start
    return {
        "progress": {"start": start, "end": start + datetime.timedelta(days=6), "days": week["days"],
                     "count": week["count"], "need": week["need"]},
        "this_week": this_week,
        "unclaimed": [{"week_start": r["week_start"], "order": r["reward_order"], "clothes": _clothes(r)}
                      for r in claims if not r["claimed_at"] and _as_date(r["week_start"]) != start],
    }


def claim_diary(user_id, week_start):
    """일기 주간 보상 받기. week_start 는 그 주의 아무 날짜나 된다 (월요일로 맞춘다)."""
    day = _as_date(week_start) if week_start else None
    if day is None:
        raise BadRequest("어느 주의 선물인지 알려 주세요.")
    week = progress_repo.week_start_of(day)
    sync_diary_claims(user_id)

    def work(tx):
        rows = tx.query(
            """SELECT r.id AS claim_id, r.claimed_at, c.id, c.name, c.slot, c.image_url
                 FROM reward_claims r JOIN clothes c ON c.id = r.clothes_id
                WHERE r.user_id = :uid AND r.reward_kind = 'diary' AND r.week_start = :w
                FOR UPDATE""",
            {"uid": user_id, "w": week.isoformat()})
        if not rows:
            raise BadRequest(f"아직 받을 수 있는 선물이 아니에요. 한 주에 {rules.WEEK_MIN_DAYS}일을 채우면 받을 수 있어요.")
        r = rows[0]
        if r["claimed_at"]:
            raise AlreadyClaimed("이미 받은 선물이에요.")
        now = _now_str()
        tx.execute("UPDATE reward_claims SET claimed_at = :now WHERE id = :id", {"now": now, "id": r["claim_id"]})
        tx.execute("INSERT IGNORE INTO user_clothes (user_id, clothes_id, acquired_at) VALUES (:uid, :cid, :now)",
                   {"uid": user_id, "cid": r["id"], "now": now})
        return _clothes(r)

    got = db.run_in_transaction(work)
    return {"clothes": got, "diary_reward": diary_reward(user_id), "character": character(user_id)}


# ── 동화 구간 보상 ──

def _free_topic_id():
    """자유 주제('내가 정할래요') 줄 번호. 없으면 None. books_repo.FREE_TOPIC_TITLE 과 같이 띄어쓰기를 빼고 비교한다."""
    rows = db.query("SELECT MIN(id) AS id FROM fairy_topics WHERE REPLACE(title, ' ', '') = '자유주제'")
    return rows[0]["id"] if rows else None


def fairy_reward(user_id, book_id):
    """동화책 한 권의 보상 진행 (FR-040 · FR-045, 장 목록 화면에서 쓴다). 내 동화책이 아니면 None.
      qualified  3문장 이상 쓴 장 수
      stages     [{order, chapters, status, clothes}] status: locked / claimable / claimed
      next       다음 보상까지 {chapters, remaining}. 모든 구간을 채웠으면 None"""
    book = db.query("SELECT id, fairy_topic_id FROM books WHERE id = :bid AND user_id = :uid AND kind = 'fairy'",
                    {"bid": book_id, "uid": user_id})
    if not book:
        return None
    prog = progress_repo.story_progress(user_id, book_id)
    qualified = prog["qualified"] if prog else 0
    claimed = {r["reward_order"]: r for r in db.query(
        """SELECT r.reward_order, r.claimed_at, c.id, c.name, c.slot, c.image_url
             FROM reward_claims r JOIN clothes c ON c.id = r.clothes_id
            WHERE r.book_id = :bid AND r.reward_kind = 'fairy'""", {"bid": book_id})}
    topic = book[0]["fairy_topic_id"]
    if topic is None:                       # 자유 주제 줄이 없을 때 만든 책: NULL 도 자유 주제로 본다 (books_repo 주석)
        topic = _free_topic_id()
    sets ={r["reward_order"]: r for r in db.query(
        """SELECT reward_order, id, name, slot, image_url FROM clothes
            WHERE reward_kind = 'fairy' AND fairy_topic_id = :t""", {"t": topic})} if topic else {}
    stages = []
    for order, chapters in enumerate(rules.STORY_REWARD_CHAPTERS, start=1):
        if order in claimed:
            status, row = "claimed", claimed[order]
        else:
            status, row = ("claimable" if qualified >= chapters else "locked"), sets.get(order)
        stages.append({"order": order, "chapters": chapters, "status": status,
                       "clothes": _clothes(row) if row else None})
    nxt = next((c for c in rules.STORY_REWARD_CHAPTERS if c > qualified), None)
    return {"book_id": book_id, "qualified": qualified, "stages": stages,
            "next": {"chapters": nxt, "remaining": nxt - qualified} if nxt else None}


def claim_fairy(user_id, book_id, order):
    """동화 구간 보상 받기. order 는 1 · 2 · 3 (3장 · 6장 · 10장 구간). 내 동화책이 아니면 None."""
    try:
        order = int(order)
    except (TypeError, ValueError):
        raise BadRequest("몇 번째 선물인지 알려 주세요.")
    if not 1 <= order <= len(rules.STORY_REWARD_CHAPTERS):
        raise BadRequest("없는 선물이에요.")
    info = fairy_reward(user_id, book_id)
    if info is None:
        return None
    stage = info["stages"][order - 1]
    if stage["status"] == "claimed":
        raise AlreadyClaimed("이미 받은 선물이에요.")
    if stage["status"] == "locked":
        raise BadRequest(f"아직 받을 수 없어요. 3문장 이상 쓴 장이 {stage['chapters']}장이 되면 받을 수 있어요.")
    if stage["clothes"] is None:
        raise BadRequest("이 책에는 준비된 선물이 없어요.")

    def work(tx):
        now = _now_str()
        tx.insert("""INSERT INTO reward_claims (user_id, clothes_id, reward_kind, reward_order, book_id, achieved_at, claimed_at)
                     VALUES (:uid, :cid, 'fairy', :o, :bid, :now, :now)""",
                  {"uid": user_id, "cid": stage["clothes"]["id"], "o": order, "bid": book_id, "now": now})
        tx.execute("INSERT IGNORE INTO user_clothes (user_id, clothes_id, acquired_at) VALUES (:uid, :cid, :now)",
                   {"uid": user_id, "cid": stage["clothes"]["id"], "now": now})

    try:
        db.run_in_transaction(work)
    except db.Conflict:                     # 같은 때 들어온 다른 요청이 먼저 받았다
        raise AlreadyClaimed("이미 받은 선물이에요.")
    return {"clothes": stage["clothes"], "fairy_reward": fairy_reward(user_id, book_id)}


# ── 옷장 ──

def character(user_id):
    """지금 입은 옷 {top: 옷 | None, bottom, hat, shoes, gloves} (대시보드 '내 캐릭터')."""
    rows = db.query("SELECT * FROM user_equipped_clothes WHERE user_id = :uid", {"uid": user_id})
    ids = {s: rows[0][f"{s}_clothes_id"] for s in SLOTS} if rows else {s: None for s in SLOTS}
    wanted = [i for i in ids.values() if i]
    found = {}
    if wanted:
        marks = ", ".join(f":c{n}" for n in range(len(wanted)))
        found = {r["id"]: r for r in db.query(f"SELECT id, name, slot, image_url FROM clothes WHERE id IN ({marks})",
                                              {f"c{n}": v for n, v in enumerate(wanted)})}
    return {s: (_clothes(found[i]) if i in found else None) for s, i in ids.items()}


def wardrobe(user_id):
    """캐릭터 옷장 (FR-041).
      equipped  {부위: 옷 번호 | None}
      slots     [{slot, label, items: [{id, name, image_url, status, condition, progress}]}]
                status: wearing 입고 있어요 / owned 가지고 있어요 / locked 아직 없어요
                condition: 아직 없는 옷을 받는 조건 (예: '일기 주간 목표 2회 달성', '토끼 동화 6장 완성')
                progress: 다음에 받을 일기 옷에만 '이번 주 3/5일'"""
    sync_diary_claims(user_id)
    rows = db.query(
        """SELECT c.id, c.name, c.slot, c.image_url, c.reward_kind, c.reward_order, t.title AS topic,
                  uc.clothes_id IS NOT NULL AS owned
             FROM clothes c
             LEFT JOIN fairy_topics t ON t.id = c.fairy_topic_id
             LEFT JOIN user_clothes uc ON uc.clothes_id = c.id AND uc.user_id = :uid
            ORDER BY c.reward_kind = 'fairy', c.fairy_topic_id, c.reward_order""",
        {"uid": user_id})
    worn = {s: (c["id"] if c else None) for s, c in character(user_id).items()}
    achieved = db.query("SELECT COUNT(*) AS n FROM reward_claims WHERE user_id = :uid AND reward_kind = 'diary'",
                        {"uid": user_id})[0]["n"]
    week = progress_repo.week_status(user_id)
    slots = {s: [] for s in SLOTS}
    for r in rows:
        if r["slot"] not in slots:
            continue
        if worn.get(r["slot"]) == r["id"]:
            status = "wearing"
        else:
            status = "owned" if r["owned"] else "locked"
        condition = progress = None
        if status == "locked":
            if r["reward_kind"] == "diary":
                condition = f"일기 주간 목표 {r['reward_order']}회 달성"
                if r["reward_order"] == achieved + 1:
                    progress = f"이번 주 {week['count']}/{week['need']}일"
            elif r["reward_order"] <= len(rules.STORY_REWARD_CHAPTERS):
                condition = f"{r['topic'] or '동화'} 동화 {rules.STORY_REWARD_CHAPTERS[r['reward_order'] - 1]}장 완성"
        slots[r["slot"]].append({"id": r["id"], "name": r["name"], "image_url": r["image_url"], "status": status,
                                 "condition": condition, "progress": progress})
    return {"equipped": worn,
            "slots": [{"slot": s, "label": SLOT_LABEL[s], "items": slots[s]} for s in SLOTS]}


def equip(user_id, slot, clothes_id):
    """옷 입히기 · 벗기기. clothes_id 가 None 이면 그 부위를 벗긴다. 다른 부위는 그대로 둔다."""
    if slot not in SLOTS:
        raise BadRequest("없는 부위예요.")
    if clothes_id is not None:
        try:
            clothes_id = int(clothes_id)
        except (TypeError, ValueError):
            raise BadRequest("옷 번호가 맞지 않아요.")
        own = db.query("""SELECT c.slot FROM clothes c
                            JOIN user_clothes uc ON uc.clothes_id = c.id AND uc.user_id = :uid
                           WHERE c.id = :cid""", {"uid": user_id, "cid": clothes_id})
        if not own:
            raise BadRequest("가지고 있는 옷만 입을 수 있어요.")
        if own[0]["slot"] != slot:
            raise BadRequest(f"이 옷은 {SLOT_LABEL[own[0]['slot']]}예요.")
    col = f"{slot}_clothes_id"              # slot 은 위에서 SLOTS 로 확인했다
    db.run_in_transaction(lambda tx: tx.execute(
        f"""INSERT INTO user_equipped_clothes (user_id, {col}) VALUES (:uid, :cid)
            ON DUPLICATE KEY UPDATE {col} = :cid""", {"uid": user_id, "cid": clothes_id}))
    return {"character": character(user_id)}
