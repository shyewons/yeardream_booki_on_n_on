"""책 · 글 · 문장을 DB에서 불러오는 함수들 (FastAPI 와 상관없이 쓸 수 있는 일반 함수).

- 모든 조회는 user_id 로 걸러서, 다른 사용자의 책이나 글은 찾을 수 없다(None).
- 목록은 {"items": [...], "page", "size", "total", "total_pages"} 모양이다.
  없는 쪽(범위를 벗어난 쪽)을 부르면 오류가 아니라 빈 items 를 준다.
"""
import datetime
import json
import os

import auth
import db
import reward_rules as rules

# 한 쪽에 몇 개를 줄지 (환경변수/.env 로 바꿀 수 있다)
PAGE_SIZE_BOOKS = int(os.environ.get("PAGE_SIZE_BOOKS", 6))        # 목장(책 목록): 한 쪽 책 수 (화면은 한 줄에 3권)
PAGE_SIZE_ENTRIES = int(os.environ.get("PAGE_SIZE_ENTRIES", 10))   # 일기 목록: 한 쪽 글(날짜) 수
MAX_SIZE = 50                                                       # size 를 직접 줄 때의 상한


class NoUser(Exception):
    """더미 사용자가 DB에 없을 때."""


class BadRequest(ValueError):
    """요청한 내용이 맞지 않을 때 (이유를 화면에 그대로 보여 줄 수 있게 한국어로 적는다)."""


# 한국 시간 (서머타임이 없어서 시간대 자료(tzdata) 없이 +9시간으로 계산한다). DB 서버가 UTC 라서 시각은 앱이 정해 넣는다.
KST = datetime.timezone(datetime.timedelta(hours=9))


def now_kst():
    return datetime.datetime.now(KST).replace(tzinfo=None, microsecond=0)


def today_kst():
    return now_kst().date()


def _now_str():
    return now_kst().strftime("%Y-%m-%d %H:%M:%S")


# ── 지금 누구인지 ───────────────────────────────────────────────────────────
# 요청 헤더 X-User-Token 이 있으면 요청마다 그 토큰의 주인을 DB에서 찾는다 (auth.py). 회원별로 자기 목장 · 책만 보인다.
# 토큰 없이 온 요청은 예전처럼 더미 사용자 한 명으로 처리한다 (frontend/temp 시험용 화면 호환). ALLOW_DUMMY_USER=0 이면 401.
_NICKNAME = os.environ.get("DUMMY_NICKNAME", "dummy_user")
_user_id = None          # 더미 사용자 번호만 서버 전체에서 기억한다 (토큰 사용자는 기억하지 않고 요청마다 찾는다)


def _dummy_user_id():
    global _user_id
    if _user_id is None:
        rows = db.query("SELECT id FROM users WHERE nickname = :n", {"n": _NICKNAME})
        if not rows:
            raise NoUser(f"사용자 '{_NICKNAME}'가 없습니다. seed_dummy.sql 을 먼저 실행하세요.")
        _user_id = rows[0]["id"]
    return _user_id


def _current_user():
    """지금 요청의 사용자 {"id", "nickname"}. 토큰이 틀렸거나, 토큰 없이 왔는데 더미를 안 쓰면 auth.InvalidToken (→ 401)."""
    token = auth.current_token()
    if token:
        user = auth.find_user_by_token(token)
        if user is None:
            raise auth.InvalidToken("별명 정보를 찾을 수 없어요. 별명을 다시 만들어 주세요.")
        return user
    if not auth.ALLOW_DUMMY_USER:
        raise auth.InvalidToken("별명을 먼저 만들어 주세요.")
    return {"id": _dummy_user_id(), "nickname": _NICKNAME}


def current_user_id():
    return _current_user()["id"]


def known_user_id():
    """이미 알아낸 더미 사용자 번호 (DB를 새로 묻지 않는다). 아직 모르면 None. 토큰 없이 온 요청의 로그에 쓴다."""
    return _user_id


def current_nickname():
    """화면 제목('○○의 목장')에 쓰는 별명."""
    return _current_user()["nickname"]


# ── 도우미 ──────────────────────────────────────────────────────────────────
def _size(size, default):
    if size is None:
        return default
    return max(1, min(int(size), MAX_SIZE))


def _meta(total, page, size):
    return {"page": page, "size": size, "total": total, "total_pages": -(-total // size)}


def _json(v):
    """MySQL JSON 컬럼은 글자로 오기도 해서 목록/딕셔너리로 바꿔 준다."""
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


# ── 책 목록 ─────────────────────────────────────────────────────────────────
def list_books(user_id, page=1, size=None):
    size = _size(size, PAGE_SIZE_BOOKS)
    total = db.query("SELECT COUNT(*) AS n FROM books WHERE user_id = :uid", {"uid": user_id})[0]["n"]
    items = db.query(
        """SELECT id, kind, title, cover, created_at
             FROM books
            WHERE user_id = :uid
            ORDER BY created_at DESC, id DESC
            LIMIT :size OFFSET :offset""",
        {"uid": user_id, "size": size, "offset": (page - 1) * size},
    )
    return {"owner": current_nickname(), "items": items, **_meta(total, page, size)}


def get_book(user_id, book_id):
    rows = db.query(
        "SELECT id, kind, title, cover, finished_at FROM books WHERE id = :bid AND user_id = :uid",
        {"bid": book_id, "uid": user_id},
    )
    return rows[0] if rows else None


# ── 책 만들기 ('새로운 이야기': 종류를 고르고 동물 이름을 지으면 책이 하나 생긴다) ───
KINDS = ("diary", "fairy")
COVERS = ("sheep", "alpaca")
MAX_TITLE = 20          # 동물 이름 최대 글자 수 (DB 칸은 60자)
TOPIC_CHANGE_MAX_SENTENCES = 0   # 동화 주제를 바꿀 수 있는 때: 이야기의 보이는 문장이 이 수 이하일 때만.
                                 # 0 = 첫 문장을 쓰기 전에만 / None = 언제나. 화면은 글 응답의 entry.topic_changeable 로 안다


def create_book(user_id, kind, title, fairy_topic_id=None):
    """책을 만든다. 동화는 고른 주제 번호(fairy_topic_id)를 함께 받는다: None 이면 자유 주제(내가 정할래요. 책에는 자유 주제 번호를 적는다).
    일기는 주제를 쓰지 않는다 (보내도 NULL)."""
    if kind not in KINDS:
        raise BadRequest("일기와 동화 중에서 골라 주세요.")
    if not isinstance(title, str) or not title.strip():
        raise BadRequest("친구의 이름을 적어 주세요.")
    title = " ".join(title.split())
    if len(title) > MAX_TITLE:
        raise BadRequest(f"이름은 {MAX_TITLE}자까지 쓸 수 있어요.")

    def work(tx):
        topic = _topic_arg(tx, kind, fairy_topic_id)        # 없는 주제 · 꺼진 주제면 400
        n = tx.query("SELECT COUNT(*) AS n FROM books WHERE user_id = :uid", {"uid": user_id})[0]["n"]
        cover = COVERS[n % len(COVERS)]                     # 양 · 알파카를 번갈아 (모양 고르기는 화면이 생기면)
        bid = tx.insert(
            """INSERT INTO books (user_id, kind, title, cover, visibility, created_at, fairy_topic_id)
               VALUES (:uid, :k, :t, :c, 'stats', :now, :tp)""",
            {"uid": user_id, "k": kind, "t": title, "c": cover, "now": _now_str(), "tp": topic})
        return {"id": bid, "kind": kind, "title": title, "cover": cover,
                "fairy_topic_id": topic if topic != _free_topic_id(tx) else None}   # 화면에는 자유 주제를 None 으로

    return db.run_in_transaction(work)


# 목록에 보이는 글: 문장이 하나라도 있거나, 쓰다 멈춘 문장(draft_text)이 있는 글.
# ('오늘 일기 쓰기'를 눌러 글만 만들어 두고 아무것도 안 쓴 글이 목록에 "문장 0개"로 쌓이지 않게)
_VISIBLE = "(EXISTS (SELECT 1 FROM sentences s2 WHERE s2.entry_id = e.id AND s2.seq IS NOT NULL) OR e.draft_text IS NOT NULL)"


# ── 책 안의 글 목록 (일기: 날짜별, 최신 날짜부터 / 동화: 장 목록, 1장부터) ─────────────
def list_entries(user_id, book_id, page=1, size=None):
    """책이 없거나 내 책이 아니면 None. 동화는 장 목록을 돌려준다: items 는 이 쪽의 장(1장부터 STORY_CHAPTERS_PER_PAGE 개씩),
    story 는 이야기 전체 정보(_story: 모든 장 · 보상 진행 · 끝내기)."""
    book = get_book(user_id, book_id)
    if book is None:
        return None
    if book["kind"] == "fairy":
        story = _story(db, book_id)
        shown = [c for c in story["chapters"] if c["visible"]]
        size = rules.STORY_CHAPTERS_PER_PAGE
        items = shown[(page - 1) * size: page * size]
        return {"book": book, "items": items, "writing": None, "story": story, "rules": rules.public(),
                **_meta(len(shown), page, size)}
    size = _size(size, PAGE_SIZE_ENTRIES)
    total = db.query(f"SELECT COUNT(*) AS n FROM entries e WHERE e.book_id = :bid AND {_VISIBLE}", {"bid": book_id})[0]["n"]
    rows = db.query(
        """SELECT e.id, e.diary_date, e.status, e.saved_at, e.edited_at,
                  (SELECT COUNT(*) FROM sentences s WHERE s.entry_id = e.id AND s.seq IS NOT NULL) AS sentence_count
             FROM entries e
            WHERE e.book_id = :bid AND """ + _VISIBLE + """
            ORDER BY e.diary_date DESC, e.id DESC
            LIMIT :size OFFSET :offset""",
        {"bid": book_id, "size": size, "offset": (page - 1) * size},
    )
    items = [
        {"id": r["id"], "date": r["diary_date"], "status": r["status"],
         "sentence_count": r["sentence_count"], "saved_at": r["saved_at"], "edited_at": r["edited_at"]}
        for r in rows
    ]
    # 쓰던 글(가장 최근의 '쓰는 중'): 목록 화면의 '이어서 쓰기' 버튼용. 없으면 None
    w = db.query(
        """SELECT e.id, e.diary_date FROM entries e
            WHERE e.book_id = :bid AND e.status = 'writing' AND """ + _VISIBLE + """
            ORDER BY e.diary_date DESC, e.id DESC LIMIT 1""", {"bid": book_id})
    writing = {"id": w[0]["id"], "date": w[0]["diary_date"]} if w else None
    # 오늘 일기(하루 = 글 하나): 목록 화면의 '새 일기 쓰기 / 오늘 일기 이어서 쓰기 / 오늘 일기 고쳐 쓰기' 문구용. 없으면 None
    t = db.query(f"""SELECT e.id, e.status FROM entries e WHERE e.book_id = :bid AND e.diary_date = :d AND {_VISIBLE}""",
                 {"bid": book_id, "d": today_kst().isoformat()})
    today = {"id": t[0]["id"], "status": t[0]["status"]} if t else None
    return {"book": book, "items": items, "writing": writing, "today": today, **_meta(total, page, size)}


# ── 글 하나 (문장 + 교정 항목까지) ───────────────────────────────────────────
def get_entry(user_id, entry_id):
    """글이 없거나 내 글이 아니면 None. 문장은 순서대로, 교정 항목은 파이프라인 응답과 같은 이름으로 붙인다."""
    rows = db.query(
        """SELECT e.id, e.book_id, e.diary_date, e.status, e.draft_text, e.draft_saved_at, e.draft_mode, e.draft_seq,
                  e.saved_at, e.edited_at, e.created_at, e.day_done_at, e.chapter_no,
                  b.kind AS book_kind, b.title AS book_title
             FROM entries e
             JOIN books b ON b.id = e.book_id
            WHERE e.id = :eid AND b.user_id = :uid""",
        {"eid": entry_id, "uid": user_id},
    )
    if not rows:
        return None
    e = rows[0]

    sents = db.query(
        """SELECT id, seq, original, revised, attempt_count, invalid_reasons,
                  has_correction, correction_mode, expression_choice, written_at, fairy_topic_id
             FROM sentences
            WHERE entry_id = :eid AND seq IS NOT NULL
            ORDER BY seq""",
        {"eid": entry_id},
    )
    cors = db.query(
        """SELECT c.sentence_id, c.idx, c.start_pos, c.end_pos, c.before_text, c.after_text,
                  c.explanation, c.evidence_doc_id, c.evidence_article, c.evidence_page,
                  c.evidence_score, c.query_text, c.error_type, c.evidence_part, c.evidences
             FROM corrections c
             JOIN sentences s ON s.id = c.sentence_id
            WHERE s.entry_id = :eid AND s.seq IS NOT NULL
            ORDER BY c.sentence_id, c.idx""",
        {"eid": entry_id},
    )

    by_sentence = {}
    for c in cors:
        evidence = None
        if any(c[k] is not None for k in ("evidence_doc_id", "evidence_article", "evidence_page", "evidence_score")):
            evidence = {"doc_id": c["evidence_doc_id"], "part": c["evidence_part"], "article": c["evidence_article"],
                        "page": c["evidence_page"], "score": c["evidence_score"]}
        by_sentence.setdefault(c["sentence_id"], []).append({
            "index": c["idx"], "start": c["start_pos"], "end": c["end_pos"],
            "before": c["before_text"], "after": c["after_text"], "explanation": c["explanation"],
            "evidence": evidence, "query": c["query_text"],
            "type": c["error_type"],                       # 판정 유형 (파이프라인의 type). DB 칸 이름은 error_type
            "evidences": _json(c["evidences"]) or [],      # 근거 조항 전체 (최대 3개). 예전 글은 빈 목록
        })

    sentences = [{
        "id": s["id"], "seq": s["seq"],
        "original": s["original"], "revised": s["revised"],
        "attempt_count": s["attempt_count"],
        "invalid_reasons": _json(s["invalid_reasons"]) or [],
        "has_correction": bool(s["has_correction"]),
        "correction_mode": s["correction_mode"],
        "expression_choice": _json(s["expression_choice"]),
        "written_at": s["written_at"],
        "fairy_topic_id": s["fairy_topic_id"],             # 이 문장을 쓸 때 고른 동화 주제 (일기는 None, 자유 주제는 자유 주제 줄 번호)
        "corrections": by_sentence.get(s["id"], []),
    } for s in sents]

    # 동화: 책의 주제(책 만들 때 고름, None 이면 자유 주제) · 장 정보 · 앞 장의 끝 문장
    topic, changeable, story, chapter_no, display_no, prev_tail = None, False, None, None, None, None
    if e["book_kind"] == "fairy":
        topic = _book_topic(db, e["book_id"])
        story = _story(db, e["book_id"])
        changeable = _topic_changeable(sum(c["sentence_count"] for c in story["chapters"]))   # 책 전체 문장 수로 본다
        chapter_no = e["chapter_no"] or 1                                                     # 장 번호가 없는 예전 이야기는 1장
        display_no = next((c["display_no"] for c in story["chapters"] if c["id"] == e["id"]), None) or chapter_no
        prev_tail = _prev_tail(story, chapter_no)

    return {
        "nav": _neighbors(e),
        "book": {"id": e["book_id"], "kind": e["book_kind"], "title": e["book_title"]},
        "entry": {"id": e["id"], "book_id": e["book_id"], "date": e["diary_date"], "status": e["status"],
                  "draft_text": e["draft_text"], "draft_saved_at": e["draft_saved_at"],
                  "draft_mode": e["draft_mode"], "draft_seq": e["draft_seq"],     # 쓰던 문장이 어느 자리의 것인지 (save_draft)
                  "saved_at": e["saved_at"], "edited_at": e["edited_at"], "created_at": e["created_at"],
                  "day_done_at": e["day_done_at"],                                  # 일기 하루치를 처음 채운 시각 (없으면 None)
                  "topic": topic,                                                   # 동화: 책의 주제 {id, title, prompt, opening} 또는 None(자유 주제)
                  "topic_changeable": changeable,                                   # 동화: 지금 주제를 바꿀 수 있는지 (책 전체 문장 수로 본다. 화면은 이 값을 따른다)
                  "topic_change_max": TOPIC_CHANGE_MAX_SENTENCES,                   # 동화: 문장이 몇 개까지일 때 바꿀 수 있는지 (None = 언제나)
                  "chapter_no": chapter_no,                                         # 동화: DB 장 번호 (글을 열 때 쓴다. 일기는 None)
                  "display_no": display_no},                                        # 동화: 화면에 보이는 장 번호 (빈 장을 건너뛰고 센다)
        "story": story,                                                             # 동화: 장 목록 · 끝내기 정보 (_story). 일기는 None
        "prev_tail": prev_tail,                                                     # 동화: 앞 장의 마지막 문장들 {chapter_no, entry_id, sentences} (이어지는 느낌용, 없으면 None)
        "sentences": sentences,
        "rules": rules.public(),                                                    # 보상 기준 숫자 (reward_rules.py)
    }


def _neighbors(e):
    """같은 책 안의 이전 이야기(더 오래된 글) · 다음 이야기(더 새 글) 번호. 없으면 None. 목록에 보이는 글만 센다.
    일기는 날짜 순서, 동화는 장 번호 순서 (이전 장 · 다음 장)."""
    if e["diary_date"] is not None:
        older, newer, order, p = "e.diary_date < :v", "e.diary_date > :v", "e.diary_date", {"v": str(e["diary_date"])[:10]}
    else:
        ch = "COALESCE(e.chapter_no, 1)"
        older, newer, order, p = f"{ch} < :v", f"{ch} > :v", ch, {"v": e.get("chapter_no") or 1}
    p["bid"] = e["book_id"]

    def one(cond, direction):
        rows = db.query(f"SELECT e.id FROM entries e WHERE e.book_id = :bid AND {cond} AND {_VISIBLE} "
                        f"ORDER BY {order} {direction} LIMIT 1", p)
        return rows[0]["id"] if rows else None

    return {"prev": one(older, "DESC"), "next": one(newer, "ASC")}


def get_entry_by_date(user_id, book_id, date_iso):
    """일기는 하루 = 글 하나라서 날짜로도 찾을 수 있다. date_iso 는 'YYYY-MM-DD'. 없으면 None."""
    rows = db.query(
        """SELECT e.id
             FROM entries e
             JOIN books b ON b.id = e.book_id
            WHERE e.book_id = :bid AND b.user_id = :uid AND e.diary_date = :d""",
        {"bid": book_id, "uid": user_id, "d": date_iso},
    )
    if not rows:
        return None
    return get_entry(user_id, rows[0]["id"])


# ═════════════════════════════════════════════════════════════════════════
#  쓰기 (글 열기/만들기 · 문장 저장 · 이야기 저장하기)
#  규칙: 일기 하루 = 글 하나 · 동화 한 장 = 글 하나 / 문장을 추가·수정하면 상태는 writing, '이야기 저장하기'를 누르면 done
#        (동화는 '이야기 끝내기'(finish_story)가 모든 장을 done 으로 바꾸고, 끝낸 뒤 고쳐도 done 을 유지한다)
#        edited_at 은 문장 내용이 바뀔 때만, saved_at 은 저장하기를 누를 때만 갱신 / 시각은 앱이 한국 시간으로 넣는다
#
#  문장 기록은 지우지 않는다 (통계 · 보호자 확인용).
#    다시쓰기 · 지우기 · 동화 표현 선택으로 바뀐 줄은 DB 에서 지우지 않고 '화면에서 빠진 줄'로 남긴다.
#      보이는 줄:  seq 에 순서가 있고 ended_at, end_reason 이 비어 있다
#      빠진 줄:    seq 가 NULL, ended_at(빠진 시각), end_reason(edit / delete / expr). 교정 항목도 그 줄에 그대로 붙어 있다
#    그래서 화면용 조회는 모두 'seq IS NOT NULL' 로 보이는 줄만 읽는다. 순서를 밀고 당기는 쿼리(seq >= x, seq < 0)는
#    NULL 을 저절로 건너뛰므로 따로 조건이 필요 없다. 통계를 낼 때는 빠진 줄까지 함께 읽으면 된다.
# ═════════════════════════════════════════════════════════════════════════
MAX_SENTENCES = 200     # 글 하나에 쓸 수 있는 문장 수 (넘으면 새 문장을 받지 않는다. 고치기 · 순서 바꾸기는 계속 된다)
MAX_TEXT = 500          # 문장 한 줄 최대 글자 수
MAX_REASONS = 20        # 틀린 이유 최대 개수
MAX_REASON_LEN = 300
MAX_CORRECTIONS = 30    # 한 문장의 교정 항목 최대 개수
MAX_EXPLANATION = 2000  # 교정 설명문 최대 글자 수 (넘는 부분은 자른다)
MAX_CHOICE_LEN = 4000   # 표현 선택 기록(JSON으로 바꾼 길이) 최대 글자 수
MAX_EVIDENCES = 5       # 교정 항목 하나의 근거 조항 최대 개수 (파이프라인은 최대 3개를 준다)
END_REASONS = ("edit", "delete", "expr")   # 화면에서 빠진 이유: 다시쓰기 / 지우기 / 동화 표현 선택


class Stale(Exception):
    """화면이 알고 있는 글과 DB 의 글이 달라졌을 때 (다른 탭 · 기기에서 순서를 바꾼 경우 등). 409 로 알린다."""


def _own_entry(tx, user_id, entry_id):
    rows = tx.query(
        """SELECT e.id FROM entries e JOIN books b ON b.id = e.book_id
            WHERE e.id = :eid AND b.user_id = :uid""", {"eid": entry_id, "uid": user_id})
    return rows[0] if rows else None


def open_entry(user_id, book_id, day=None, chapter=None, new_chapter=False):
    """글을 열거나(이미 있으면) 만든다. 책이 없거나 내 책이 아니면 None.
    일기는 날짜(기본: 오늘, 한국 시간)로 하루에 하나.
    동화는 장(chapter)마다 글 하나다 (아래 '동화 장' 참고):
      chapter=3         3장을 연다 (없는 장이면 400. 장이 하나도 없을 때의 1장 · 문장이 있는 마지막 장의 바로 다음 장은 만든다)
      new_chapter=True  다음 장을 만든다 (마지막 장이 비어 있으면 그 장을 그대로 연다. 끝낸 이야기 · STORY_MAX_CHAPTERS(100장)가 넘으면 400)
      둘 다 없음         마지막 장을 연다 (없으면 1장을 만든다)
    돌려주는 값은 get_entry 와 같은 모양에 "created"(방금 만들었는지)를 더한 것이다."""
    book = get_book(user_id, book_id)
    if book is None:
        return None
    if book["kind"] == "fairy":
        return _open_chapter(user_id, book, chapter, new_chapter)
    diary_date = None
    if book["kind"] == "diary":
        if day in (None, ""):
            d = today_kst()
        else:
            try:
                d = datetime.date.fromisoformat(str(day))
            except ValueError:
                raise BadRequest("날짜는 2026-11-12 처럼 적어 주세요.")
        if d > today_kst():
            raise BadRequest("앞으로 올 날짜의 일기는 아직 쓸 수 없어요.")
        diary_date = d.isoformat()

    def find(tx):
        if diary_date:
            return tx.query("SELECT id FROM entries WHERE book_id = :b AND diary_date = :d", {"b": book_id, "d": diary_date})
        return tx.query("SELECT id FROM entries WHERE book_id = :b ORDER BY id LIMIT 1", {"b": book_id})

    def work(tx):
        rows = find(tx)
        if rows:
            return rows[0]["id"], False
        try:
            eid = tx.insert(
                "INSERT INTO entries (book_id, diary_date, status, created_at) VALUES (:b, :d, 'writing', :now)",
                {"b": book_id, "d": diary_date, "now": _now_str()})
            return eid, True
        except db.Conflict:                      # 같은 글을 다른 요청이 동시에 먼저 만들었다 → 아래에서 그 글을 찾아 연다
            return None, False

    eid, created = db.run_in_transaction(work)
    if eid is None:
        # 여기서 다시 찾는 이유: MySQL 은 트랜잭션이 시작될 때의 모습만 보여 줘서, 위 트랜잭션 안에서는
        # 방금 다른 요청이 만든 글이 보이지 않는다 (예전에는 여기서 '목록이 비었다'는 오류로 500 이 났다).
        rows = db.run_in_transaction(find)
        if not rows:
            raise db.DBUnavailable("글을 여는 중에 문제가 생겼어요. 잠시 후 다시 해 주세요.")
        eid = rows[0]["id"]
    return {"created": created, **get_entry(user_id, eid)}


# ── 동화 장 ───────────────────────────────────────────────────────────────────
# 동화 책 하나에 이야기 하나, 이야기는 장(1장 ~ reward_rules.STORY_MAX_CHAPTERS, 지금 100장)으로 나뉜다. 장 하나 = 글(entries) 하나 (entries.chapter_no).
#   화면: 한 장 = 한 쪽. 장 첫머리와 새 장 쓰기 화면에 앞 장의 마지막 문장을 살짝 보여 준다 (_prev_tail)
#   새 장: 목록의 '새 장 쓰기'. 마지막 장을 다른 날 이어 쓸 때는 화면이 '이어 쓸지 · 새 장을 쓸지' 묻는다
#   빈 장: 문장을 다 지운 장은 목록에서 숨기고 번호는 그대로 둔다 (이미 받은 보상과 번호가 어긋나지 않게)
#   끝내기: 3문장 이상 쓴 장이 STORY_FINISH_MIN_CHAPTERS 개 이상이면 '이야기 끝내기'(books.finished_at).
#           끝낸 이야기는 다시쓰기(고쳐 쓰기)만 된다: 새 장 · 새 문장 · 위에 넣기 · 지우기 · 순서 바꾸기는 400
#   끝낼지 묻기: STORY_FINISH_ASK_AT 장째를 채웠을 때 한 번씩 (지금은 비워 둬서 묻지 않는다) (아이가 '다음에 이어 쓸래요'를 고르면 books.finish_asked 에 그 구간을 적는다)
#           마지막 장(100장)은 채운 뒤 나갈 때마다 묻는다. 묻는 판단은 화면이 story 정보로 한다 (writer.js)
# 장 번호가 없는 예전 동화 글(chapter_no NULL)은 1장으로 본다.
FINISHED_MSG = "끝낸 이야기는 고쳐 쓰기만 할 수 있어요."


def _story(q, book_id):
    """동화 책의 장 목록과 끝내기 정보. q 는 db 또는 트랜잭션(tx).
    chapters: [{id, chapter_no, display_no, sentence_count, first, status, edited_at, last_written, visible, qualified}] (장 번호 순서)
      chapter_no  DB 의 장 번호 (글을 열 때 쓰는 번호. 빈 장을 숨겨도 바뀌지 않는다)
      display_no  화면에 보이는 번호: 숨긴 빈 장을 건너뛰고 1장부터 다시 센다 (1 · 3장만 있으면 화면은 1 · 2장).
                  숨긴 빈 장은 None. 비어 있어도 마지막 장(지금 쓰기 시작한 장)은 번호를 받는다
      visible     목록에 보이는 장 (문장이 있거나 쓰던 문장이 있다)
      qualified   3문장 이상 쓴 장 (보상 · 끝내기에 세는 장)
    보상과 장 수 제한(STORY_MAX_CHAPTERS)은 장 번호가 아니라 개수로 센다 (번호를 다시 매겨도 받은 보상과 어긋나지 않는다)."""
    b = q.query("SELECT finished_at, finish_asked FROM books WHERE id = :bid", {"bid": book_id})
    b = b[0] if b else {"finished_at": None, "finish_asked": 0}
    rows = q.query(
        """SELECT e.id, COALESCE(e.chapter_no, 1) AS chapter_no, e.status, e.edited_at, e.draft_text,
                  (SELECT COUNT(*) FROM sentences s WHERE s.entry_id = e.id AND s.seq IS NOT NULL) AS n,
                  (SELECT s.revised FROM sentences s WHERE s.entry_id = e.id AND s.seq = 1) AS first,
                  (SELECT MAX(s.written_at) FROM sentences s WHERE s.entry_id = e.id AND s.seq IS NOT NULL) AS last_written
             FROM entries e
            WHERE e.book_id = :bid
            ORDER BY chapter_no, e.id""", {"bid": book_id})
    chapters = []
    for r in rows:
        if chapters and chapters[-1]["chapter_no"] == r["chapter_no"]:
            continue                                     # 예전 데이터에 같은 장 글이 둘이면 앞의 것만 쓴다
        n = int(r["n"])
        chapters.append({"id": r["id"], "chapter_no": int(r["chapter_no"]), "sentence_count": n,
                         "first": r["first"], "status": r["status"], "edited_at": r["edited_at"],
                         "last_written": r["last_written"],
                         "visible": n > 0 or r["draft_text"] is not None,
                         "qualified": n >= rules.STORY_CHAPTER_MIN_SENTENCES})
    shown = 0
    for i, c in enumerate(chapters):
        if c["visible"] or i == len(chapters) - 1:
            shown += 1
            c["display_no"] = shown
        else:
            c["display_no"] = None                   # 문장을 다 지운 장: 목록 · 이전/다음 장에서 건너뛴다
    qualified = sum(1 for c in chapters if c["qualified"])
    written_chapters = sum(1 for c in chapters if c["sentence_count"] > 0)
    last = chapters[-1] if chapters else None
    finished = b["finished_at"] is not None
    return {
        "chapters": chapters,
        "qualified": qualified,                                              # 3문장 이상 쓴 장 수
        "rewards_reached": [m for m in rules.STORY_REWARD_CHAPTERS if qualified >= m],   # 보상 구간 중 채운 것 (받았는지는 reward_claims)
        "finished": finished,
        "finished_at": b["finished_at"],
        "finish_asked": int(b["finish_asked"] or 0),                         # 아이가 '이어 쓸래요'를 고른 마지막 구간
        "can_finish": not finished and qualified >= rules.STORY_FINISH_MIN_CHAPTERS,
        "last_chapter": last["chapter_no"] if last else 0,                   # 마지막 장의 DB 번호 (이어서 쓰기)
        "last_display": last["display_no"] if last else 0,                   # 마지막 장의 화면 번호
        "written_chapters": written_chapters,                                # 문장이 있는 장 수 (장 수 제한 STORY_MAX_CHAPTERS 에 센다)
        # 새 장 쓰기: 끝내지 않았고, 문장이 있는 장이 10개 미만이거나 마지막 장이 비어 있을 때 (비어 있으면 그 장을 다시 연다)
        "can_new_chapter": not finished and (last is None or last["sentence_count"] == 0 or written_chapters < rules.STORY_MAX_CHAPTERS),
        "max_chapters": rules.STORY_MAX_CHAPTERS,
    }


PREV_TAIL = 2   # 앞 장에서 보여 주는 마지막 문장 수


def _prev_tail(story, chapter_no):
    """chapter_no 보다 앞의 문장이 있는 장 중 가장 가까운 장의 마지막 PREV_TAIL 문장 (최종 문장).
    {chapter_no, display_no, entry_id, sentences: [...]} 또는 앞 장이 없으면 None."""
    prev = [c for c in story["chapters"] if c["chapter_no"] < chapter_no and c["sentence_count"] > 0]
    if not prev:
        return None
    c = prev[-1]
    rows = db.query("""SELECT revised FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL
                        ORDER BY seq DESC LIMIT :n""", {"eid": c["id"], "n": PREV_TAIL})
    return {"chapter_no": c["chapter_no"], "display_no": c["display_no"], "entry_id": c["id"],
            "sentences": [r["revised"] for r in reversed(rows)]}


def _open_chapter(user_id, book, chapter, new_chapter):
    """동화의 장을 열거나 만든다 (open_entry 참고)."""
    book_id = book["id"]
    if chapter not in (None, ""):
        chapter = _opt_int(chapter)
        if chapter is None or chapter < 1:            # DB 번호는 빈 장을 건너뛰면 10을 넘을 수 있다 (개수 제한은 아래에서)
            raise BadRequest("장 번호가 맞지 않아요.")
    else:
        chapter = None

    def find(tx, no):
        return tx.query("""SELECT id FROM entries WHERE book_id = :b AND COALESCE(chapter_no, 1) = :c
                            ORDER BY id LIMIT 1""", {"b": book_id, "c": no})

    def work(tx):
        story = _story(tx, book_id)
        if chapter is not None:
            target = chapter
        elif new_chapter:
            if story["finished"]:
                raise BadRequest("끝낸 이야기에는 새 장을 쓸 수 없어요.")
            last = story["chapters"][-1] if story["chapters"] else None
            if last is not None and last["sentence_count"] == 0:
                return last["id"], False, last["chapter_no"]          # 마지막 장이 비어 있으면 그 장에 쓴다 (빈 장이 쌓이지 않게)
            if story["written_chapters"] >= rules.STORY_MAX_CHAPTERS:
                raise BadRequest(f"이야기는 {rules.STORY_MAX_CHAPTERS}장까지 쓸 수 있어요.")
            target = (last["chapter_no"] if last else 0) + 1
        else:
            target = story["last_chapter"] or 1
        rows = find(tx, target)
        if rows:
            return rows[0]["id"], False, target
        if chapter is not None and target != 1:
            # 없는 장은 '바로 다음 장'일 때만 만든다 (글쓰기 화면의 '다음 장'): 마지막 장에 문장이 있고, 끝내지 않았을 때
            last = story["chapters"][-1] if story["chapters"] else None
            if story["finished"] or last is None or target != last["chapter_no"] + 1 or last["sentence_count"] == 0:
                raise BadRequest("아직 쓰지 않은 장이에요.")
            if story["written_chapters"] >= rules.STORY_MAX_CHAPTERS:
                raise BadRequest(f"이야기는 {rules.STORY_MAX_CHAPTERS}장까지 쓸 수 있어요.")
        try:
            eid = tx.insert(
                "INSERT INTO entries (book_id, diary_date, chapter_no, status, created_at) VALUES (:b, NULL, :c, 'writing', :now)",
                {"b": book_id, "c": target, "now": _now_str()})
            return eid, True, target
        except db.Conflict:                      # 같은 장을 다른 요청이 동시에 먼저 만들었다 → 아래에서 다시 찾는다
            return None, False, target

    eid, created, target = db.run_in_transaction(work)
    if eid is None:
        rows = db.run_in_transaction(lambda tx: find(tx, target))   # 트랜잭션 밖에서 다시 찾는 이유는 open_entry 참고
        if not rows:
            raise db.DBUnavailable("글을 여는 중에 문제가 생겼어요. 잠시 후 다시 해 주세요.")
        eid = rows[0]["id"]
    return {"created": created, **get_entry(user_id, eid)}


def finish_story(user_id, book_id):
    """'이야기 끝내기': 3문장 이상 쓴 장이 STORY_FINISH_MIN_CHAPTERS 개 이상이면 끝낸다 (books.finished_at).
    모든 장의 상태를 done 으로 바꾸고 저장 시각을 남긴다. 이미 끝냈으면 그대로 돌려준다. 책이 없거나 내 동화 책이 아니면 None."""
    def work(tx):
        b = tx.query("SELECT id, kind FROM books WHERE id = :bid AND user_id = :uid", {"bid": book_id, "uid": user_id})
        if not b or b[0]["kind"] != "fairy":
            return None
        story = _story(tx, book_id)
        if story["finished"]:
            return {"finished": True, "changed": False, "story": story}
        if not story["can_finish"]:
            raise BadRequest(f"{rules.STORY_CHAPTER_MIN_SENTENCES}문장 이상 쓴 장이 {rules.STORY_FINISH_MIN_CHAPTERS}개가 되면 이야기를 끝낼 수 있어요.")
        now = _now_str()
        tx.execute("UPDATE books SET finished_at = :now WHERE id = :bid", {"now": now, "bid": book_id})
        tx.execute("""UPDATE entries SET status = 'done', saved_at = :now,
                             draft_text = NULL, draft_saved_at = NULL, draft_mode = NULL, draft_seq = NULL
                       WHERE book_id = :bid""", {"now": now, "bid": book_id})
        return {"finished": True, "changed": True, "story": _story(tx, book_id)}

    return db.run_in_transaction(work)


def finish_later(user_id, book_id, upto):
    """끝낼지 물었을 때 '다음에 이어 쓸래요': 그 구간(reward_rules.STORY_FINISH_ASK_AT, 지금은 비어 있어 쓰이지 않음)을 적어 두어 다시 묻지 않는다. 책이 없거나 내 동화 책이 아니면 None."""
    upto = _opt_int(upto)
    if upto not in rules.STORY_FINISH_ASK_AT:
        raise BadRequest("묻는 구간이 맞지 않아요.")

    def work(tx):
        b = tx.query("SELECT id, kind, finish_asked FROM books WHERE id = :bid AND user_id = :uid", {"bid": book_id, "uid": user_id})
        if not b or b[0]["kind"] != "fairy":
            return None
        if upto > int(b[0]["finish_asked"] or 0):
            tx.execute("UPDATE books SET finish_asked = :u WHERE id = :bid", {"u": upto, "bid": book_id})
        return {"finish_asked": max(upto, int(b[0]["finish_asked"] or 0))}

    return db.run_in_transaction(work)


def _block_if_finished(tx, entry_id):
    """끝낸 동화 이야기면 BadRequest (다시쓰기를 뺀 편집을 막는다)."""
    r = tx.query("""SELECT b.finished_at FROM entries e JOIN books b ON b.id = e.book_id
                     WHERE e.id = :eid AND b.kind = 'fairy'""", {"eid": entry_id})
    if r and r[0]["finished_at"] is not None:
        raise BadRequest(FINISHED_MSG)


def _cut(v, n):
    return None if v is None else str(v)[:n]


def _opt_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _opt_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _evidence_list(v):
    """근거 조항 목록(파이프라인의 evidences)을 저장할 JSON 글자로 다듬는다. 없거나 모양이 다르면 None."""
    if not isinstance(v, list):
        return None
    out = []
    for e in v[:MAX_EVIDENCES]:
        if isinstance(e, dict):
            out.append({"doc_id": _cut(e.get("doc_id"), 100), "part": _cut(e.get("part"), 40), "article": _cut(e.get("article"), 100),
                        "page": _opt_int(e.get("page")), "score": _opt_float(e.get("score")), "source": _cut(e.get("source"), 20)})
    return json.dumps(out, ensure_ascii=False) if out else None


def _insert_corrections(tx, sentence_id, items):
    for i, c in enumerate(items):
        if not isinstance(c, dict):
            continue
        ev = c.get("evidence") if isinstance(c.get("evidence"), dict) else {}
        tx.execute(
            """INSERT INTO corrections (sentence_id, idx, start_pos, end_pos, before_text, after_text, explanation,
                                        evidence_doc_id, evidence_part, evidence_article, evidence_page, evidence_score,
                                        evidences, query_text, error_type)
               VALUES (:sid, :idx, :st, :en, :b, :a, :ex, :doc, :part, :art, :pg, :sc, :evs, :q, :et)""",
            {"sid": sentence_id, "idx": _opt_int(c.get("index"), i), "st": _opt_int(c.get("start")), "en": _opt_int(c.get("end")),
             "b": _cut(c.get("before"), 200) or "", "a": _cut(c.get("after"), 200) or "", "ex": _cut(c.get("explanation"), MAX_EXPLANATION),
             "doc": _cut(ev.get("doc_id"), 100), "art": _cut(ev.get("article"), 100), "pg": _opt_int(ev.get("page")),
             "sc": _opt_float(ev.get("score")), "q": _cut(c.get("query"), 500),
             "part": _cut(ev.get("part"), 40),                           # 근거 문서 이름 (한글 맞춤법 / 표준어 사정 원칙)
             "evs": _evidence_list(c.get("evidences")),                  # 근거 조항 전체 (JSON)
             "et": _cut(c.get("type") or c.get("error_type"), 40)})      # 판정 유형 (파이프라인은 type 으로 준다)


def _clean_text(v, name):
    if not isinstance(v, str) or not v.strip():
        raise BadRequest(f"{name}이(가) 비어 있어요.")
    v = v.strip()
    if len(v) > MAX_TEXT:
        raise BadRequest(f"{name}이(가) 너무 길어요 ({MAX_TEXT}자까지).")
    return v


# ── 동화 주제 · 일기 하루치 ─────────────────────────────────────────────────
# 동화 주제는 책을 만들 때 고른다 (books.fairy_topic_id. 자유 주제 '내가 정할래요'는 자유 주제 줄의 번호, 아래 FREE_TOPIC_TITLE).
# 바꾸기는 TOPIC_CHANGE_MAX_SENTENCES 까지만 된다 (지금은 책의 첫 문장을 쓰기 전에만. 장마다가 아니라 책 전체 문장 수로 본다. set_book_topic).
# 문장마다에도 남긴다 (sentences.fairy_topic_id). 바꾸기를 넓혀도 문장별로 그때의 주제가 남아,
# 보상 쪽에서 '마지막 주제'든 '주제별 문장 수'든 나중에 정해 셀 수 있다.
#   새 문장 · 위에 넣은 문장   책의 지금 주제 (서버가 넣는다. 화면이 보낸 값은 쓰지 않는다)
#   다시쓰기 · 표현 선택       같은 문장을 고친 것이라 옛 줄의 주제를 그대로 물려받는다
# 일기 하루치는 보이는 문장이 reward_rules.DIARY_DAY_SENTENCES 개가 되는 순간 entries.day_done_at 에 한 번 적는다.
#   문장은 검사 · 교정을 통과해야 저장되므로 '검사를 통과한 문장'만 센다 (임시저장 draft_text 는 세지 않는다).

# 자유 주제('내가 정할래요')도 fairy_topics 의 한 줄이다: 제목 FREE_TOPIC_TITLE, is_active = 0 (추천에는 안 나온다).
# 책 · 문장에는 그 줄의 번호를 적어 '주제 없음(NULL)'과 구분한다 (보상 세트를 주제에 이을 때 자유 주제도 이을 수 있게).
# 그 줄이 없으면(표를 새로 만든 직후 등) 예전처럼 NULL 로 저장한다. NULL 도 자유 주제로 본다. 화면에는 자유 주제를 늘 None 으로 보낸다.
# 제목은 띄어쓰기를 빼고 비교한다 ('자유 주제' · '자유주제' 모두 같은 줄).
FREE_TOPIC_TITLE = "자유 주제"
_FREE_KEY = FREE_TOPIC_TITLE.replace(" ", "")
_FREE_SQL = "REPLACE(t.title, ' ', '') = :free"       # fairy_topics 를 t 로 부를 때 '자유 주제 줄인지'


def list_topics():
    """켜져 있는 동화 주제 [{id, title, prompt, opening}] (fairy_topics.is_active = 1). 하나도 없으면 빈 목록.
    prompt 는 주제 카드에 보이는 쓰기 안내 (예: 토끼가 주인공인 동화를 만들어 봐!),
    opening 은 글쓰기 첫 장에 보이는 시작 상황 (예: 토끼가 숲에서 … 누구의 발자국일까?). 없으면 None."""
    return db.query(f"SELECT t.id, t.title, t.prompt, t.opening FROM fairy_topics t WHERE t.is_active = 1 AND NOT ({_FREE_SQL}) ORDER BY t.id",
                    {"free": _FREE_KEY})


def _free_topic_id(q):
    """자유 주제 줄의 번호. 없으면 None. q 는 db 또는 트랜잭션(tx)."""
    rows = q.query(f"SELECT t.id FROM fairy_topics t WHERE {_FREE_SQL} ORDER BY t.id LIMIT 1", {"free": _FREE_KEY})
    return rows[0]["id"] if rows else None


def _book_topic(q, book_id):
    """책의 주제 {id, title, prompt, opening}. 자유 주제 · 일기면 None. q 는 db 또는 트랜잭션(tx)."""
    rows = q.query(f"""SELECT t.id, t.title, t.prompt, t.opening FROM books b JOIN fairy_topics t ON t.id = b.fairy_topic_id
                        WHERE b.id = :bid AND NOT ({_FREE_SQL})""", {"bid": book_id, "free": _FREE_KEY})
    return rows[0] if rows else None


def _topic_changeable(n_sentences):
    """보이는 문장이 n 개인 이야기의 주제를 바꿀 수 있는지 (TOPIC_CHANGE_MAX_SENTENCES)."""
    return TOPIC_CHANGE_MAX_SENTENCES is None or n_sentences <= TOPIC_CHANGE_MAX_SENTENCES


def set_book_topic(user_id, book_id, fairy_topic_id):
    """동화 책의 주제를 바꾼다 (None = 자유 주제). 책이 없거나 내 책이 아니면 None.
    일기 책이거나, 이야기를 이미 TOPIC_CHANGE_MAX_SENTENCES 보다 많이 썼으면 BadRequest (→ 400)."""
    def work(tx):
        b = tx.query("SELECT id, kind FROM books WHERE id = :bid AND user_id = :uid", {"bid": book_id, "uid": user_id})
        if not b:
            return None
        if b[0]["kind"] != "fairy":
            raise BadRequest("동화 책만 주제를 고를 수 있어요.")
        n = tx.query("""SELECT COUNT(*) AS n FROM sentences s JOIN entries e ON e.id = s.entry_id
                          WHERE e.book_id = :bid AND s.seq IS NOT NULL""", {"bid": book_id})[0]["n"]
        if not _topic_changeable(n):
            raise BadRequest("이미 쓰기 시작한 이야기는 주제를 바꿀 수 없어요.")
        topic = _topic_arg(tx, "fairy", fairy_topic_id)
        tx.execute("UPDATE books SET fairy_topic_id = :t WHERE id = :bid", {"t": topic, "bid": book_id})
        return {"book_id": book_id, "topic": _book_topic(tx, book_id), "changed": True}

    return db.run_in_transaction(work)


def _entry_info(tx, entry_id):
    """문장을 저장할 때 필요한 글 정보: 책 종류(diary/fairy) · 책의 동화 주제 · 이야기를 끝냈는지 · 일기 날짜 · 하루치 달성 시각."""
    return tx.query("""SELECT b.kind, b.fairy_topic_id, b.finished_at, e.diary_date, e.day_done_at FROM entries e JOIN books b ON b.id = e.book_id
                        WHERE e.id = :eid""", {"eid": entry_id})[0]


def _topic_arg(tx, kind, v):
    """화면이 보낸 주제 번호를 확인해 책에 적을 번호를 돌려준다. 일기면 None.
    동화에서 비어 있으면(내가 정할래요) 자유 주제 번호 (_free_topic_id, 그 줄이 없으면 None).
    없는 주제 · 꺼진 주제면 BadRequest (→ 400). 자유 주제 번호는 꺼져 있어도 받는다."""
    if kind != "fairy":
        return None
    free = _free_topic_id(tx)
    if v in (None, ""):
        return free
    tid = _opt_int(v)
    if tid is not None and tid == free:
        return tid
    if tid is None or not tx.query("SELECT id FROM fairy_topics WHERE id = :t AND is_active = 1", {"t": tid}):
        raise BadRequest("고른 주제를 찾을 수 없어요. 주제를 다시 골라 주세요.")
    return tid


def _as_date(v):
    """DB 의 날짜 값(date · datetime · 'YYYY-MM-DD' 글자)을 date 로. 없으면 None."""
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v)[:10])


def _mark_day_done(tx, entry_id, info, now):
    """일기 하루치 달성을 적는다. 이번에 적었으면 그 시각, 아니면 None.
    이미 적혀 있으면 그대로 둔다 (나중에 지우거나 고쳐서 문장이 줄어도 달성은 남는다).
    지난 날짜는 일기 날짜 + DIARY_LATE_DAYS 일까지만 (예: 15일 일기는 18일까지). 앞으로 올 날짜는 open_entry 가 이미 막는다."""
    if info["kind"] != "diary" or info["day_done_at"] is not None:
        return None
    day = _as_date(info["diary_date"])
    today = today_kst()
    if day is None or day > today or (today - day).days > rules.DIARY_LATE_DAYS:
        return None
    n = tx.query("SELECT COUNT(*) AS n FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL", {"eid": entry_id})[0]["n"]
    if n < rules.DIARY_DAY_SENTENCES:
        return None
    tx.execute("UPDATE entries SET day_done_at = :now WHERE id = :eid AND day_done_at IS NULL", {"now": now, "eid": entry_id})
    return now


# 순서 번호를 바꿀 때: 같은 글 안에서 번호가 겹치면 안 되므로(UNIQUE) 두 번에 나눠 옮긴다.
#   1) 옮길 문장들의 번호를 음수로 뒤집어 잠깐 비켜 두고 (양수 번호와는 절대 겹치지 않는다. seq 칸은 음수도 담는 INT)
#   2) 새 번호를 매긴다.


def move_sentence(user_id, entry_id, seq, to):
    """문장 순서 바꾸기: seq 번째 문장을 to 번째 자리로 옮긴다 (사이의 문장들은 한 칸씩 밀린다).
    글이 없거나 내 글이 아니면 None. 자리가 실제로 바뀌면 글은 '쓰는 중'으로 돌아가고 수정 시각이 갱신된다."""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (seq, to)):
        raise BadRequest("문장 순서가 맞지 않아요.")

    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        _block_if_finished(tx, entry_id)
        ids = [r["id"] for r in tx.query("SELECT id FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL ORDER BY seq", {"eid": entry_id})]
        if not (1 <= seq <= len(ids) and 1 <= to <= len(ids)):
            raise BadRequest("문장 순서가 맞지 않아요.")
        now = _now_str()
        if seq != to:
            ids.insert(to - 1, ids.pop(seq - 1))
            tx.execute("UPDATE sentences SET seq = -seq WHERE entry_id = :eid", {"eid": entry_id})
            for n, sid in enumerate(ids, 1):
                tx.execute("UPDATE sentences SET seq = :n WHERE id = :sid", {"n": n, "sid": sid})
            tx.execute("UPDATE entries SET status = 'writing', edited_at = :now WHERE id = :eid", {"now": now, "eid": entry_id})
        entry = tx.query("SELECT id, status, edited_at, saved_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        return {"moved": seq != to, "saved_at": now, "entry": entry}

    return db.run_in_transaction(work)


def insert_sentence(user_id, entry_id, seq, data):
    """문장 끼워 넣기: seq 번째 자리에 새 문장을 넣고, 그 자리부터의 문장은 한 칸씩 뒤로 민다 (끝 다음 자리면 그냥 붙인다)."""
    return save_sentence(user_id, entry_id, seq, data, insert=True)


def save_sentence(user_id, entry_id, seq, data, insert=False):
    """문장 하나를 저장한다 (임시저장). 같은 순서(seq)가 이미 있으면 덮어쓰고, 끝 다음 순서면 새로 붙인다.
    insert=True 면 덮어쓰지 않고 그 자리에 끼워 넣는다 (같은 문장이 이미 그 자리에 있으면 다시 넣지 않는다: 재전송 대비).
    글이 없거나 내 글이 아니면 None. 내용(원문·최종문장)이 그대로면 아무것도 바꾸지 않는다(같은 요청을 다시 보내도 안전).
    이미 있는 줄의 내용이 바뀌면 덮어쓰지 않고, 그 줄은 '빠진 줄'로 남기고 같은 순서에 새 줄을 넣는다 (기록 보존).
    data: original, revised, attempt_count, invalid_reasons[], has_correction, correction_mode, expression_choice, corrections[],
          reason (바뀐 이유: edit 다시쓰기 / expr 동화 표현 선택. 없으면 원문이 바뀌었는지로 정한다),
          (동화 주제는 받지 않는다: 새 문장은 책의 주제, 고친 문장은 옛 줄의 주제. 위 '동화 주제 · 일기 하루치' 참고)
    끝낸 동화 이야기는 다시쓰기만 된다 (새 문장 · 위에 넣기는 BadRequest).
    일기는 저장 뒤 하루치 달성을 확인한다 (_mark_day_done). 결과의 day_done 은 이번 저장으로 처음 달성했는지."""
    if not isinstance(data, dict):
        raise BadRequest("문장 내용이 필요해요.")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
        raise BadRequest("문장 순서가 맞지 않아요.")
    original = _clean_text(data.get("original"), "원문")
    revised = _clean_text(data.get("revised") or original, "최종 문장")
    attempt = min(99, max(1, _opt_int(data.get("attempt_count"), 1)))
    reasons = data.get("invalid_reasons") or []
    items = data.get("corrections") or []
    if not isinstance(reasons, list) or not isinstance(items, list):
        raise BadRequest("틀린 이유와 교정 항목은 목록이어야 해요.")
    reasons = [str(x)[:MAX_REASON_LEN] for x in reasons][:MAX_REASONS]
    items = items[:MAX_CORRECTIONS]
    mode = _cut(data.get("correction_mode") or None, 20)
    choice = data.get("expression_choice")
    choice = None if choice is None else json.dumps(choice, ensure_ascii=False)
    if choice is not None and len(choice) > MAX_CHOICE_LEN:
        raise BadRequest("표현 선택 기록이 너무 길어요.")
    has_corr = 1 if data.get("has_correction") else 0
    reason = data.get("reason") if data.get("reason") in ("edit", "expr") else None

    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        info = _entry_info(tx, entry_id)
        rows = tx.query("SELECT id, seq, original, revised, fairy_topic_id FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL ORDER BY seq",
                        {"eid": entry_id})
        if seq > (rows[-1]["seq"] if rows else 0) + 1:
            raise BadRequest("앞의 문장이 아직 저장되지 않았어요.")
        cur = next((r for r in rows if r["seq"] == seq), None)
        squeeze = insert and cur is not None and not (cur["original"] == original and cur["revised"] == revised)   # 사이에 끼워 넣는 경우
        finished = info["kind"] == "fairy" and info["finished_at"] is not None
        if finished and (cur is None or squeeze):                              # 끝낸 이야기: 새 문장 · 위에 넣기는 안 된다 (다시쓰기만)
            raise BadRequest(FINISHED_MSG)
        if (cur is None or squeeze) and len(rows) >= MAX_SENTENCES:            # 문장이 하나 늘어나는 저장만 막는다
            raise BadRequest(f"한 글에는 문장을 {MAX_SENTENCES}개까지 쓸 수 있어요.")
        if squeeze:
            tx.execute("UPDATE sentences SET seq = -seq WHERE entry_id = :eid AND seq >= :seq", {"eid": entry_id, "seq": seq})   # 뒤 문장들을 비켜 두고
            tx.execute("UPDATE sentences SET seq = -seq + 1 WHERE entry_id = :eid AND seq < 0", {"eid": entry_id})                # 한 칸씩 뒤 번호로
            cur = None
        now = _now_str()
        changed = cur is None or cur["original"] != original or cur["revised"] != revised
        why = None                                   # 이미 있던 줄이 바뀐 이유 (기록용)
        p = {"o": original, "r": revised, "n": attempt, "ir": json.dumps(reasons, ensure_ascii=False),
             "hc": has_corr, "m": mode, "ec": choice, "now": now}
        insert_row = """INSERT INTO sentences (entry_id, seq, original, revised, attempt_count, invalid_reasons, has_correction,
                                               correction_mode, expression_choice, written_at, fairy_topic_id)
                        VALUES (:eid, :seq, :o, :r, :n, :ir, :hc, :m, :ec, :now, :tp)"""
        if cur is None:                              # 새 문장 · 위에 넣은 문장: 책의 지금 주제 (일기는 NULL)
            sid = tx.insert(insert_row, {**p, "eid": entry_id, "seq": seq,
                                         "tp": info["fairy_topic_id"] if info["kind"] == "fairy" else None})
        else:
            sid = cur["id"]
            if changed:
                # 덮어쓰지 않는다: 옛 줄은 '빠진 줄'로 남기고(교정 항목도 그대로) 같은 순서에 새 줄을 넣는다.
                # 이유를 화면이 알려 주지 않으면 원문이 바뀌었으면 다시쓰기, 최종 문장만 바뀌었으면 표현 선택으로 본다.
                why = reason or ("edit" if cur["original"] != original else "expr")
                tx.execute("UPDATE sentences SET seq = NULL, ended_at = :now, end_reason = :why WHERE id = :sid",
                           {"now": now, "why": why, "sid": sid})
                sid = tx.insert(insert_row, {**p, "eid": entry_id, "seq": seq, "tp": cur["fairy_topic_id"]})   # 주제는 옛 줄 그대로
            elif choice is not None:                 # 문장은 그대로인데 표현 선택 기록만 온 경우 (예: '원래 문장 그대로'): 기록만 남긴다
                tx.execute("UPDATE sentences SET expression_choice = :ec WHERE id = :sid", {"ec": choice, "sid": sid})
        if changed:
            _insert_corrections(tx, sid, items)
            # 끝낸 이야기는 고쳐도 '완성'을 유지한다 (상태를 writing 으로 돌리면 끝내기가 풀린 것처럼 보인다)
            tx.execute(f"""UPDATE entries SET status = {"status" if finished else "'writing'"}, edited_at = :now,
                                 draft_text = NULL, draft_saved_at = NULL, draft_mode = NULL, draft_seq = NULL
                           WHERE id = :eid""", {"now": now, "eid": entry_id})
        done_now = _mark_day_done(tx, entry_id, info, now) if changed else None
        entry = tx.query("SELECT id, status, edited_at, saved_at, day_done_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        return {"sentence_id": sid, "seq": seq, "changed": changed, "reason": why, "saved_at": now, "entry": entry,
                "day_done": done_now is not None}

    return db.run_in_transaction(work)


# ── 문장 지우기 · 되살리기 ───────────────────────────────────────────────────
# 지운 줄도 DB 에서 지우지 않는다: seq 를 비우고 end_reason = 'delete' 로 남긴다 (위 '문장 기록은 지우지 않는다' 참고).
# 쓰던 문장 임시저장(draft_mode, draft_seq)이 가리키는 자리도 같은 트랜잭션에서 맞춘다.

def _seq_arg(v, name="문장 순서"):
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise BadRequest(f"{name}가 맞지 않아요.")
    return v


def delete_sentence(user_id, entry_id, seq, sentence_id):
    """seq 번째 문장을 화면에서 뺀다. sentence_id 가 그 자리의 문장과 다르면(다른 곳에서 글이 바뀜) Stale.
    뒤 문장은 한 칸씩 당긴다. 글이 없거나 내 글이 아니면 None. 글은 '쓰는 중'으로 돌아가고 수정 시각이 갱신된다."""
    seq = _seq_arg(seq)
    sentence_id = _seq_arg(sentence_id, "문장 번호")

    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        _block_if_finished(tx, entry_id)
        cur = tx.query("SELECT id FROM sentences WHERE entry_id = :eid AND seq = :seq", {"eid": entry_id, "seq": seq})
        if not cur or cur[0]["id"] != sentence_id:
            raise Stale("글이 다른 곳에서 바뀌었어요. 글을 다시 열어 주세요.")
        now = _now_str()
        tx.execute("UPDATE sentences SET seq = NULL, ended_at = :now, end_reason = 'delete' WHERE id = :sid",
                   {"now": now, "sid": sentence_id})
        tx.execute("UPDATE sentences SET seq = -seq WHERE entry_id = :eid AND seq > :seq", {"eid": entry_id, "seq": seq})  # 뒤 문장들을 비켜 두고
        tx.execute("UPDATE sentences SET seq = -seq - 1 WHERE entry_id = :eid AND seq < 0", {"eid": entry_id})             # 한 칸씩 앞 번호로
        n = tx.query("SELECT COUNT(*) AS n FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL", {"eid": entry_id})[0]["n"]

        # 쓰던 문장이 가리키던 자리 맞추기
        d = tx.query("SELECT draft_mode, draft_seq FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        mode, dseq = d["draft_mode"], d["draft_seq"]
        if mode in ("edit", "insert") and dseq:
            if dseq > seq:
                dseq -= 1                            # 앞줄이 빠졌으니 한 칸 당긴다
            elif dseq == seq and mode == "edit":
                mode, dseq = "new", None             # 고치던 줄이 빠졌다 (화면은 막지만 다른 탭에서 지운 경우) → 새 문장으로
            if mode == "insert" and dseq > n:
                mode, dseq = "new", None             # 넣을 자리가 끝을 넘었다 → 맨 뒤에 쓰는 새 문장
        tx.execute("""UPDATE entries SET status = 'writing', edited_at = :now, draft_mode = :m, draft_seq = :s
                       WHERE id = :eid""", {"now": now, "m": mode, "s": dseq, "eid": entry_id})
        entry = tx.query("SELECT id, status, edited_at, saved_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        return {"deleted": True, "seq": seq, "sentence_id": sentence_id, "sentence_count": n, "saved_at": now, "entry": entry}

    return db.run_in_transaction(work)


def restore_sentence(user_id, entry_id, sentence_id, seq):
    """지운 문장을 seq 번째 자리에 되살린다 ('되돌리기'). 그 자리부터의 문장은 한 칸씩 민다.
    seq 가 끝을 넘으면 맨 뒤에 붙인다. 이미 보이는 줄이면 아무것도 바꾸지 않는다 (같은 요청을 다시 보내도 안전).
    글이 없거나 내 글이 아니면 None."""
    sentence_id = _seq_arg(sentence_id, "문장 번호")
    seq = _opt_int(seq, 0)

    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        _block_if_finished(tx, entry_id)
        row = tx.query("SELECT id, seq, end_reason FROM sentences WHERE id = :sid AND entry_id = :eid",
                       {"sid": sentence_id, "eid": entry_id})
        if not row:
            raise BadRequest("되살릴 문장을 찾을 수 없어요.")
        row = row[0]
        entry_now = lambda: tx.query("SELECT id, status, edited_at, saved_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        if row["seq"] is not None:                   # 이미 되살아나 있다
            return {"restored": False, "seq": row["seq"], "sentence_id": sentence_id, "saved_at": None, "entry": entry_now()}
        if row["end_reason"] != "delete":
            raise BadRequest("지운 문장만 되살릴 수 있어요.")
        n = tx.query("SELECT COUNT(*) AS n FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL", {"eid": entry_id})[0]["n"]
        if n >= MAX_SENTENCES:
            raise BadRequest(f"한 글에는 문장을 {MAX_SENTENCES}개까지 쓸 수 있어요.")
        pos = seq if 1 <= seq <= n else n + 1
        now = _now_str()
        tx.execute("UPDATE sentences SET seq = -seq WHERE entry_id = :eid AND seq >= :pos", {"eid": entry_id, "pos": pos})  # 뒤 문장들을 비켜 두고
        tx.execute("UPDATE sentences SET seq = -seq + 1 WHERE entry_id = :eid AND seq < 0", {"eid": entry_id})              # 한 칸씩 뒤 번호로
        tx.execute("UPDATE sentences SET seq = :pos, ended_at = NULL, end_reason = NULL WHERE id = :sid",
                   {"pos": pos, "sid": sentence_id})
        d = tx.query("SELECT draft_mode, draft_seq FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        dseq = d["draft_seq"]
        if d["draft_mode"] in ("edit", "insert") and dseq and dseq >= pos:
            dseq += 1                                # 쓰던 자리 앞에 한 줄 생겼다 → 한 칸 민다
        tx.execute("UPDATE entries SET status = 'writing', edited_at = :now, draft_seq = :s WHERE id = :eid",
                   {"now": now, "s": dseq, "eid": entry_id})
        done_now = _mark_day_done(tx, entry_id, _entry_info(tx, entry_id), now)   # 되살려서 일기 하루치가 찰 수도 있다
        return {"restored": True, "seq": pos, "sentence_id": sentence_id, "saved_at": now, "entry": entry_now(),
                "day_done": done_now is not None}

    return db.run_in_transaction(work)


# ── 쓰던 문장 임시저장 ───────────────────────────────────────────────────────
# 아직 검사 · 교정을 통과하지 않은 '쓰던 글자'를 글(entries)에 덮어써 둔다. 문장(sentences)이 아니다.
#   draft_text   쓰던 글자
#   draft_mode   new 새 문장 / edit 다시쓰기 / insert 위에 넣기
#   draft_seq    edit · insert 일 때 몇 번째 문장 자리인지 (new 는 비워 둔다)
# 문장이 저장되거나(save_sentence) 이야기를 저장하면(complete_entry) 네 칸이 함께 비워진다.
DRAFT_MODES = ("new", "edit", "insert")


def save_draft(user_id, entry_id, data):
    """쓰던 문장을 임시저장한다. 글자가 비어 있으면 임시저장을 지운다. 글이 없거나 내 글이 아니면 None.
    글의 상태(writing/done)와 수정 시각은 바꾸지 않는다 (아직 글 내용이 바뀐 것이 아니다)."""
    data = data if isinstance(data, dict) else {}
    text = data.get("text")
    text = text if isinstance(text, str) else ""
    if len(text) > MAX_TEXT:
        raise BadRequest(f"문장은 {MAX_TEXT}자까지 쓸 수 있어요.")
    mode = data.get("mode") if data.get("mode") in DRAFT_MODES else "new"
    seq = _opt_int(data.get("seq")) if mode != "new" else None
    if mode != "new" and (seq is None or seq < 1):       # 자리를 알 수 없으면 새 문장으로 둔다
        mode, seq = "new", None

    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        now = _now_str()
        if text.strip():
            tx.execute("""UPDATE entries SET draft_text = :t, draft_saved_at = :now, draft_mode = :m, draft_seq = :s
                           WHERE id = :eid""", {"t": text, "now": now, "m": mode, "s": seq, "eid": entry_id})
            return {"saved": True, "chars": len(text), "mode": mode, "seq": seq, "saved_at": now}
        tx.execute("""UPDATE entries SET draft_text = NULL, draft_saved_at = NULL, draft_mode = NULL, draft_seq = NULL
                       WHERE id = :eid""", {"eid": entry_id})
        return {"saved": False, "chars": 0, "mode": None, "seq": None, "saved_at": None}

    return db.run_in_transaction(work)


def complete_entry(user_id, entry_id):
    """'이야기 저장하기': 상태를 done 으로 바꾸고 저장 시각을 남긴다. 글이 없거나 내 글이 아니면 None. 여러 번 눌러도 된다."""
    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        n = tx.query("SELECT COUNT(*) AS n FROM sentences WHERE entry_id = :eid AND seq IS NOT NULL", {"eid": entry_id})[0]["n"]
        if n == 0:
            raise BadRequest("문장을 하나 이상 써야 저장할 수 있어요.")
        tx.execute("""UPDATE entries SET status = 'done', saved_at = :now,
                             draft_text = NULL, draft_saved_at = NULL, draft_mode = NULL, draft_seq = NULL
                       WHERE id = :eid""", {"now": _now_str(), "eid": entry_id})
        entry = tx.query("SELECT id, status, edited_at, saved_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        return {"entry": entry, "sentence_count": n}

    return db.run_in_transaction(work)
