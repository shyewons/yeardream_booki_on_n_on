"""DB의 책 · 글을 불러오는 주소들 (/api/...). 실제 조회는 books_repo.py 가 한다.

  GET /api/books?page=1&size=5                    책 목록 (한 쪽 책 수는 PAGE_SIZE_BOOKS)
  GET /api/books/{book_id}/entries?page=1         책 안의 글 목록 (일기: 날짜별, 한 쪽 글 수는 PAGE_SIZE_ENTRIES)
  GET /api/entries/{entry_id}                     글 하나 (문장 + 교정 항목)
  GET /api/books/{book_id}/diary/{YYYY-MM-DD}     일기를 날짜로 찾기 (하루 = 글 하나)
  GET /api/topics?exclude=고양이,곰&others=2      동화 주제 추천 (fairy_topics 표에서 고른다)
                                                  → {"pick", "others", "ids": {제목: 번호}, "items": [{id, title, prompt, opening}, ...]} (items 는 pick 부터)
                                                  prompt = 쓰기 안내(주제 카드), opening = 시작 상황(글쓰기 첫 장). 자유 주제 줄은 추천에 나오지 않는다

  쓰기
  POST /api/books                                 책 만들기('새로운 이야기')  body: {"kind": "diary"|"fairy", "title": "몽실", "fairy_topic_id": 3|null}
                                                  동화는 고른 주제 번호를 함께 보낸다 (null = 자유 주제 '내가 정할래요')
  PUT  /api/books/{book_id}/topic                 동화 주제 바꾸기 body: {"fairy_topic_id": 3|null}. 책의 첫 문장을 쓰기 전에만 (books_repo.TOPIC_CHANGE_MAX_SENTENCES)
  POST /api/books/{book_id}/entries               글 열기/만들기  body: {"date": "2026-11-12"} (일기, 생략하면 오늘) → 글 + 쓴 문장
                                                  동화는 장: {"chapter": 3} 그 장 / {"new_chapter": true} 다음 장 / {} 마지막 장
  PUT  /api/entries/{entry_id}/sentences/{seq}    문장 저장(임시저장). 같은 seq 면 덮어쓰기, 끝 다음 순서면 새로 붙이기
                                                  동화는 body 에 fairy_topic_id(지금 주제)를 함께 보낸다. 일기는 저장 뒤 하루치 달성을 확인한다
  POST /api/entries/{entry_id}/sentences/{seq}/insert   문장 끼워 넣기 (body 는 문장 저장과 같다)
  POST /api/entries/{entry_id}/sentences/{seq}/move     문장 순서 바꾸기  body: {"to": 3}
  DELETE /api/entries/{entry_id}/sentences/{seq}?sentence_id=123   문장 지우기 (DB 에는 '빠진 줄'로 남는다)
  POST /api/entries/{entry_id}/restore            지운 문장 되살리기  body: {"sentence_id": 123, "seq": 3}
  PUT  /api/entries/{entry_id}/draft              쓰던 문장 임시저장  body: {"text": "...", "mode": "new|edit|insert", "seq": 3}  (글자가 비면 지운다)
  POST /api/entries/{entry_id}/complete           '이야기 저장하기' (상태 done). 일기용
  POST /api/books/{book_id}/finish                동화 '이야기 끝내기' (3문장 이상 쓴 장이 3개 이상일 때. 모든 장 done, 끝낸 뒤에는 다시쓰기만)
  POST /api/books/{book_id}/finish-later          동화: 끝낼지 물었을 때 '다음에 이어 쓸래요' body: {"upto": 3|6|10} (그 구간은 다시 묻지 않는다. reward_rules.STORY_FINISH_ASK_AT)

DB에 닿지 못하면 503, 책이나 글이 없거나 내 것이 아니면 404, 요청 내용이 맞지 않으면 400,
X-User-Token 헤더의 토큰이 맞지 않으면 401, 화면이 아는 글과 DB 의 글이 달라졌으면 409 를 돌려준다 (auth.py).
"""
import datetime

from fastapi import APIRouter, Body, HTTPException, Query

import auth
import books_repo as repo
import db
import devlog
import writing_api

router = APIRouter(prefix="/api")


def _guard(fn, *args):
    """DB 쪽 문제(설정 없음, 연결 실패, 더미 사용자 없음)를 503 으로 바꿔 준다. 문제는 로그(error / action)에도 남긴다."""
    try:
        return fn(*args)
    except auth.InvalidToken as e:                       # 토큰이 틀림 → 화면이 01번 별명 화면으로 보낸다
        devlog.write("action", "rejected", {"call": getattr(fn, "__name__", ""), "reason": "invalid_token"})
        raise HTTPException(status_code=401, detail=str(e))
    except (db.DBNotConfigured, db.DBUnavailable, repo.NoUser) as e:
        devlog.error("db", e, {"call": getattr(fn, "__name__", "")})
        raise HTTPException(status_code=503, detail=str(e))
    except repo.Stale as e:                              # 다른 탭 · 기기에서 글이 바뀜 → 화면이 다시 열라고 안내한다
        devlog.write("action", "rejected", {"call": getattr(fn, "__name__", ""), "reason": "stale"})
        raise HTTPException(status_code=409, detail=str(e))
    except repo.BadRequest as e:
        devlog.write("action", "rejected", {"call": getattr(fn, "__name__", ""), "reason": str(e)})
        raise HTTPException(status_code=400, detail=str(e))


def _user():
    """지금 요청의 사용자 번호. 알아낸 번호는 로그에도 알려 준다 (이 요청의 모든 로그 줄에 붙는다)."""
    uid = _guard(repo.current_user_id)
    devlog.set_user(uid)
    return uid


def _act(name, result, **ids):
    """저장 동작 하나를 logs/action_날짜.log 에 적고 result 를 그대로 돌려준다. 글 내용은 적지 않고 번호 · 상태 · 개수만 적는다."""
    brief = {}
    if isinstance(result, dict):
        for key in ("id", "kind", "seq", "changed", "moved", "status", "saved", "chars", "mode", "reason", "deleted", "restored", "sentence_id", "day_done", "fairy_topic_id", "chapter_no", "finished", "finish_asked"):
            if isinstance(result.get(key), (str, int, bool)):
                brief[key] = result[key]
        entry = result.get("entry")
        if isinstance(entry, dict):
            brief["entry"] = {k: entry.get(k) for k in ("id", "status") if k in entry}
        if isinstance(result.get("sentences"), list):
            brief["sentences"] = len(result["sentences"])
    devlog.write("action", name, {**ids, "found": result is not None, "result": brief})
    return result


def _found(result, what):
    if result is None:
        raise HTTPException(status_code=404, detail=f"{what}을(를) 찾을 수 없습니다.")
    return result


@router.get("/books")
def books(page: int = Query(1, ge=1), size: int | None = Query(None, ge=1, le=repo.MAX_SIZE)):
    uid = _user()
    return _guard(repo.list_books, uid, page, size)


@router.get("/books/{book_id}/entries")
def book_entries(book_id: int, page: int = Query(1, ge=1), size: int | None = Query(None, ge=1, le=repo.MAX_SIZE)):
    uid = _user()
    return _found(_guard(repo.list_entries, uid, book_id, page, size), "책")


@router.get("/entries/{entry_id}")
def entry(entry_id: int):
    uid = _user()
    return _found(_guard(repo.get_entry, uid, entry_id), "글")


@router.get("/books/{book_id}/diary/{day}")
def diary_by_date(book_id: int, day: datetime.date):
    uid = _user()
    return _found(_guard(repo.get_entry_by_date, uid, book_id, day.isoformat()), "그 날짜의 일기")


@router.get("/topics")
def topics(exclude: str = "", others: int = 3):
    """동화 주제 추천: 추천 하나(pick) + 다른 주제 others 개. 새 책 화면은 others=2 로 3개를 받는다.
    주제 목록은 fairy_topics 표(켜진 것)에서 읽고, 고르는 방법은 writing_api.get_topics 와 같다.
    표가 비어 있으면 writing_api 의 FAIRY_TOPICS 로 고른다 (그때는 ids 가 비고 items 의 id 가 None 이라 자유 주제로 저장된다)."""
    _user()
    rows = _guard(repo.list_topics)
    ids = {r["title"]: r["id"] for r in rows}
    prompts = {r["title"]: r["prompt"] for r in rows}
    openings = {r["title"]: r.get("opening") for r in rows}
    pool = list(ids) or None
    r = writing_api.get_topics([x for x in exclude.split(",") if x], others=max(0, min(others, 5)), pool=pool)
    items = [{"id": ids.get(t), "title": t, "prompt": prompts.get(t), "opening": openings.get(t)} for t in [r["pick"]] + r["others"]]
    return {**r, "ids": ids, "items": items}


# ── 쓰기 ────────────────────────────────────────────────────────────────────
@router.post("/books")
def create_book(body: dict = Body(...)):
    uid = _user()
    body = body or {}
    return _act("create_book", _guard(repo.create_book, uid, body.get("kind"), body.get("title"), body.get("fairy_topic_id")))


@router.put("/books/{book_id}/topic")
def put_book_topic(book_id: int, body: dict = Body(...)):
    uid = _user()
    return _found(_act("set_book_topic", _guard(repo.set_book_topic, uid, book_id, (body or {}).get("fairy_topic_id")), book=book_id), "책")


@router.post("/books/{book_id}/entries")
def open_entry(book_id: int, body: dict | None = Body(None)):
    uid = _user()
    body = body or {}
    return _found(_act("open_entry", _guard(repo.open_entry, uid, book_id, body.get("date"), body.get("chapter"), bool(body.get("new_chapter"))),
                       book=book_id, date=body.get("date"), chapter=body.get("chapter"), new_chapter=bool(body.get("new_chapter"))), "책")


@router.post("/books/{book_id}/finish")
def finish_story(book_id: int):
    uid = _user()
    return _found(_act("finish_story", _guard(repo.finish_story, uid, book_id), book=book_id), "동화 책")


@router.post("/books/{book_id}/finish-later")
def finish_later(book_id: int, body: dict = Body(...)):
    uid = _user()
    return _found(_act("finish_later", _guard(repo.finish_later, uid, book_id, (body or {}).get("upto")), book=book_id), "동화 책")


@router.put("/entries/{entry_id}/sentences/{seq}")
def put_sentence(entry_id: int, seq: int, body: dict = Body(...)):
    uid = _user()
    return _found(_act("save_sentence", _guard(repo.save_sentence, uid, entry_id, seq, body), entry=entry_id, seq=seq), "글")


@router.post("/entries/{entry_id}/sentences/{seq}/insert")       # 문장 끼워 넣기 (그 자리부터 한 칸씩 뒤로)
def insert_sentence(entry_id: int, seq: int, body: dict = Body(...)):
    uid = _user()
    return _found(_act("insert_sentence", _guard(repo.insert_sentence, uid, entry_id, seq, body), entry=entry_id, seq=seq), "글")


@router.post("/entries/{entry_id}/sentences/{seq}/move")         # 문장 순서 바꾸기  body: {"to": 옮길 자리}
def move_sentence(entry_id: int, seq: int, body: dict = Body(...)):
    uid = _user()
    return _found(_act("move_sentence", _guard(repo.move_sentence, uid, entry_id, seq, (body or {}).get("to")), entry=entry_id, seq=seq, to=(body or {}).get("to")), "글")


@router.delete("/entries/{entry_id}/sentences/{seq}")          # 문장 지우기  ?sentence_id= 그 자리 문장의 번호 (엉뚱한 줄을 지우지 않게)
def delete_sentence(entry_id: int, seq: int, sentence_id: int = Query(...)):
    uid = _user()
    return _found(_act("delete_sentence", _guard(repo.delete_sentence, uid, entry_id, seq, sentence_id), entry=entry_id, seq=seq), "글")


@router.post("/entries/{entry_id}/restore")                       # 지운 문장 되살리기  body: {"sentence_id": 123, "seq": 3}
def restore_sentence(entry_id: int, body: dict = Body(...)):
    uid = _user()
    b = body or {}
    return _found(_act("restore_sentence", _guard(repo.restore_sentence, uid, entry_id, b.get("sentence_id"), b.get("seq")),
                       entry=entry_id, seq=b.get("seq")), "글")


@router.put("/entries/{entry_id}/draft")                         # 쓰던 문장 임시저장  body: {"text": "...", "mode": "new|edit|insert", "seq": 3}
def put_draft(entry_id: int, body: dict = Body(...)):
    uid = _user()
    return _found(_act("save_draft", _guard(repo.save_draft, uid, entry_id, body), entry=entry_id), "글")


@router.post("/entries/{entry_id}/complete")
def complete_entry(entry_id: int):
    uid = _user()
    return _found(_act("complete_entry", _guard(repo.complete_entry, uid, entry_id), entry=entry_id), "글")
