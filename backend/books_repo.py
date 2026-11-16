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
        "SELECT id, kind, title, cover FROM books WHERE id = :bid AND user_id = :uid",
        {"bid": book_id, "uid": user_id},
    )
    return rows[0] if rows else None


# ── 책 만들기 ('새로운 이야기': 종류를 고르고 동물 이름을 지으면 책이 하나 생긴다) ───
KINDS = ("diary", "fairy")
COVERS = ("sheep", "alpaca")
MAX_TITLE = 20          # 동물 이름 최대 글자 수 (DB 칸은 60자)


def create_book(user_id, kind, title):
    if kind not in KINDS:
        raise BadRequest("일기와 동화 중에서 골라 주세요.")
    if not isinstance(title, str) or not title.strip():
        raise BadRequest("친구의 이름을 적어 주세요.")
    title = " ".join(title.split())
    if len(title) > MAX_TITLE:
        raise BadRequest(f"이름은 {MAX_TITLE}자까지 쓸 수 있어요.")

    def work(tx):
        n = tx.query("SELECT COUNT(*) AS n FROM books WHERE user_id = :uid", {"uid": user_id})[0]["n"]
        cover = COVERS[n % len(COVERS)]                     # 양 · 알파카를 번갈아 (모양 고르기는 화면이 생기면)
        bid = tx.insert(
            "INSERT INTO books (user_id, kind, title, cover, visibility, created_at) VALUES (:uid, :k, :t, :c, 'stats', :now)",
            {"uid": user_id, "k": kind, "t": title, "c": cover, "now": _now_str()})
        return {"id": bid, "kind": kind, "title": title, "cover": cover}

    return db.run_in_transaction(work)


# 목록에 보이는 글: 문장이 하나라도 있거나, 쓰다 멈춘 문장(draft_text)이 있는 글.
# ('오늘 일기 쓰기'를 눌러 글만 만들어 두고 아무것도 안 쓴 글이 목록에 "문장 0개"로 쌓이지 않게)
_VISIBLE = "(EXISTS (SELECT 1 FROM sentences s2 WHERE s2.entry_id = e.id) OR e.draft_text IS NOT NULL)"


# ── 책 안의 글 목록 (일기: 날짜별, 최신 날짜부터 / 동화: 이야기 한 편) ─────────────
def list_entries(user_id, book_id, page=1, size=None):
    """책이 없거나 내 책이 아니면 None."""
    book = get_book(user_id, book_id)
    if book is None:
        return None
    size = _size(size, PAGE_SIZE_ENTRIES)
    total = db.query(f"SELECT COUNT(*) AS n FROM entries e WHERE e.book_id = :bid AND {_VISIBLE}", {"bid": book_id})[0]["n"]
    rows = db.query(
        """SELECT e.id, e.diary_date, e.status, e.saved_at, e.edited_at,
                  (SELECT COUNT(*) FROM sentences s WHERE s.entry_id = e.id) AS sentence_count
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
    return {"book": book, "items": items, "writing": writing, **_meta(total, page, size)}


# ── 글 하나 (문장 + 교정 항목까지) ───────────────────────────────────────────
def get_entry(user_id, entry_id):
    """글이 없거나 내 글이 아니면 None. 문장은 순서대로, 교정 항목은 파이프라인 응답과 같은 이름으로 붙인다."""
    rows = db.query(
        """SELECT e.id, e.book_id, e.diary_date, e.status, e.draft_text, e.draft_saved_at,
                  e.saved_at, e.edited_at, e.created_at,
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
                  has_correction, correction_mode, expression_choice, written_at
             FROM sentences
            WHERE entry_id = :eid
            ORDER BY seq""",
        {"eid": entry_id},
    )
    cors = db.query(
        """SELECT c.sentence_id, c.idx, c.start_pos, c.end_pos, c.before_text, c.after_text,
                  c.explanation, c.evidence_doc_id, c.evidence_article, c.evidence_page,
                  c.evidence_score, c.query_text, c.error_type, c.evidence_part, c.evidences
             FROM corrections c
             JOIN sentences s ON s.id = c.sentence_id
            WHERE s.entry_id = :eid
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
        "corrections": by_sentence.get(s["id"], []),
    } for s in sents]

    return {
        "nav": _neighbors(e),
        "book": {"id": e["book_id"], "kind": e["book_kind"], "title": e["book_title"]},
        "entry": {"id": e["id"], "book_id": e["book_id"], "date": e["diary_date"], "status": e["status"],
                  "draft_text": e["draft_text"], "draft_saved_at": e["draft_saved_at"],
                  "saved_at": e["saved_at"], "edited_at": e["edited_at"], "created_at": e["created_at"]},
        "sentences": sentences,
    }


def _neighbors(e):
    """같은 책 안의 이전 이야기(더 오래된 글) · 다음 이야기(더 새 글) 번호. 없으면 None. 목록에 보이는 글만 센다."""
    if e["diary_date"] is not None:
        older, newer, order, p = "e.diary_date < :v", "e.diary_date > :v", "e.diary_date", {"v": str(e["diary_date"])[:10]}
    else:
        older, newer, order, p = "e.id < :v", "e.id > :v", "e.id", {"v": e["id"]}
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
#  규칙: 하루 = 글 하나 / 문장을 추가·수정하면 상태는 writing, '이야기 저장하기'를 누르면 done
#        edited_at 은 문장 내용이 바뀔 때만, saved_at 은 저장하기를 누를 때만 갱신 / 시각은 앱이 한국 시간으로 넣는다
# ═════════════════════════════════════════════════════════════════════════
MAX_SENTENCES = 200     # 글 하나에 쓸 수 있는 문장 수 (넘으면 새 문장을 받지 않는다. 고치기 · 순서 바꾸기는 계속 된다)
MAX_TEXT = 500          # 문장 한 줄 최대 글자 수
MAX_REASONS = 20        # 틀린 이유 최대 개수
MAX_REASON_LEN = 300
MAX_CORRECTIONS = 30    # 한 문장의 교정 항목 최대 개수
MAX_EXPLANATION = 2000  # 교정 설명문 최대 글자 수 (넘는 부분은 자른다)
MAX_CHOICE_LEN = 4000   # 표현 선택 기록(JSON으로 바꾼 길이) 최대 글자 수
MAX_EVIDENCES = 5       # 교정 항목 하나의 근거 조항 최대 개수 (파이프라인은 최대 3개를 준다)


def _own_entry(tx, user_id, entry_id):
    rows = tx.query(
        """SELECT e.id FROM entries e JOIN books b ON b.id = e.book_id
            WHERE e.id = :eid AND b.user_id = :uid""", {"eid": entry_id, "uid": user_id})
    return rows[0] if rows else None


def open_entry(user_id, book_id, day=None):
    """글을 열거나(이미 있으면) 만든다. 책이 없거나 내 책이 아니면 None.
    일기는 날짜(기본: 오늘, 한국 시간)로 하루에 하나, 동화는 책 하나에 이야기 한 편이다.
    돌려주는 값은 get_entry 와 같은 모양에 "created"(방금 만들었는지)를 더한 것이다."""
    book = get_book(user_id, book_id)
    if book is None:
        return None
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
        except db.Conflict:                      # 동시에 다른 곳에서 먼저 만들었다면 그 글을 연다
            return find(tx)[0]["id"], False

    eid, created = db.run_in_transaction(work)
    return {"created": created, **get_entry(user_id, eid)}


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
        ids = [r["id"] for r in tx.query("SELECT id FROM sentences WHERE entry_id = :eid ORDER BY seq", {"eid": entry_id})]
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
    data: original, revised, attempt_count, invalid_reasons[], has_correction, correction_mode, expression_choice, corrections[]"""
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

    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        rows = tx.query("SELECT id, seq, original, revised FROM sentences WHERE entry_id = :eid ORDER BY seq", {"eid": entry_id})
        if seq > (rows[-1]["seq"] if rows else 0) + 1:
            raise BadRequest("앞의 문장이 아직 저장되지 않았어요.")
        cur = next((r for r in rows if r["seq"] == seq), None)
        squeeze = insert and cur is not None and not (cur["original"] == original and cur["revised"] == revised)   # 사이에 끼워 넣는 경우
        if (cur is None or squeeze) and len(rows) >= MAX_SENTENCES:            # 문장이 하나 늘어나는 저장만 막는다
            raise BadRequest(f"한 글에는 문장을 {MAX_SENTENCES}개까지 쓸 수 있어요.")
        if squeeze:
            tx.execute("UPDATE sentences SET seq = -seq WHERE entry_id = :eid AND seq >= :seq", {"eid": entry_id, "seq": seq})   # 뒤 문장들을 비켜 두고
            tx.execute("UPDATE sentences SET seq = -seq + 1 WHERE entry_id = :eid AND seq < 0", {"eid": entry_id})                # 한 칸씩 뒤 번호로
            cur = None
        now = _now_str()
        changed = cur is None or cur["original"] != original or cur["revised"] != revised
        p = {"o": original, "r": revised, "n": attempt, "ir": json.dumps(reasons, ensure_ascii=False),
             "hc": has_corr, "m": mode, "ec": choice, "now": now}
        if cur is None:
            sid = tx.insert(
                """INSERT INTO sentences (entry_id, seq, original, revised, attempt_count, invalid_reasons, has_correction,
                                          correction_mode, expression_choice, written_at)
                   VALUES (:eid, :seq, :o, :r, :n, :ir, :hc, :m, :ec, :now)""", {**p, "eid": entry_id, "seq": seq})
        else:
            sid = cur["id"]
            if changed:
                tx.execute(
                    """UPDATE sentences SET original = :o, revised = :r, attempt_count = :n, invalid_reasons = :ir,
                              has_correction = :hc, correction_mode = :m, expression_choice = :ec, written_at = :now
                        WHERE id = :sid""", {**p, "sid": sid})
                tx.execute("DELETE FROM corrections WHERE sentence_id = :sid", {"sid": sid})
            elif choice is not None:                 # 문장은 그대로인데 표현 선택 기록만 온 경우 (예: '원래 문장 그대로'): 기록만 남긴다
                tx.execute("UPDATE sentences SET expression_choice = :ec WHERE id = :sid", {"ec": choice, "sid": sid})
        if changed:
            _insert_corrections(tx, sid, items)
            tx.execute("""UPDATE entries SET status = 'writing', edited_at = :now, draft_text = NULL, draft_saved_at = NULL
                           WHERE id = :eid""", {"now": now, "eid": entry_id})
        entry = tx.query("SELECT id, status, edited_at, saved_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        return {"sentence_id": sid, "seq": seq, "changed": changed, "saved_at": now, "entry": entry}

    return db.run_in_transaction(work)


def complete_entry(user_id, entry_id):
    """'이야기 저장하기': 상태를 done 으로 바꾸고 저장 시각을 남긴다. 글이 없거나 내 글이 아니면 None. 여러 번 눌러도 된다."""
    def work(tx):
        if not _own_entry(tx, user_id, entry_id):
            return None
        n = tx.query("SELECT COUNT(*) AS n FROM sentences WHERE entry_id = :eid", {"eid": entry_id})[0]["n"]
        if n == 0:
            raise BadRequest("문장을 하나 이상 써야 저장할 수 있어요.")
        tx.execute("""UPDATE entries SET status = 'done', saved_at = :now, draft_text = NULL, draft_saved_at = NULL
                       WHERE id = :eid""", {"now": _now_str(), "eid": entry_id})
        entry = tx.query("SELECT id, status, edited_at, saved_at FROM entries WHERE id = :eid", {"eid": entry_id})[0]
        return {"entry": entry, "sentence_count": n}

    return db.run_in_transaction(work)
