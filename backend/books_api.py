"""DB의 책 · 글을 불러오는 주소들 (/api/...). 실제 조회는 books_repo.py 가 한다.

  GET /api/books?page=1&size=5                    책 목록 (한 쪽 책 수는 PAGE_SIZE_BOOKS)
  GET /api/books/{book_id}/entries?page=1         책 안의 글 목록 (일기: 날짜별, 한 쪽 글 수는 PAGE_SIZE_ENTRIES)
  GET /api/entries/{entry_id}                     글 하나 (문장 + 교정 항목)
  GET /api/books/{book_id}/diary/{YYYY-MM-DD}     일기를 날짜로 찾기 (하루 = 글 하나)

  쓰기
  POST /api/books                                 책 만들기('새로운 이야기')  body: {"kind": "diary"|"fairy", "title": "몽실"}
  POST /api/books/{book_id}/entries               글 열기/만들기  body: {"date": "2026-11-12"} (일기, 생략하면 오늘) → 글 + 쓴 문장
  PUT  /api/entries/{entry_id}/sentences/{seq}    문장 저장(임시저장). 같은 seq 면 덮어쓰기, 끝 다음 순서면 새로 붙이기
  POST /api/entries/{entry_id}/sentences/{seq}/insert   문장 끼워 넣기 (body 는 문장 저장과 같다)
  POST /api/entries/{entry_id}/sentences/{seq}/move     문장 순서 바꾸기  body: {"to": 3}
  POST /api/entries/{entry_id}/complete           '이야기 저장하기' (상태 done)

DB에 닿지 못하면 503, 책이나 글이 없거나 내 것이 아니면 404, 요청 내용이 맞지 않으면 400 을 돌려준다.
"""
import datetime

from fastapi import APIRouter, Body, HTTPException, Query

import books_repo as repo
import db
import devlog

router = APIRouter(prefix="/api")


def _guard(fn, *args):
    """DB 쪽 문제(설정 없음, 연결 실패, 더미 사용자 없음)를 503 으로 바꿔 준다. 문제는 로그(error / action)에도 남긴다."""
    try:
        return fn(*args)
    except (db.DBNotConfigured, db.DBUnavailable, repo.NoUser) as e:
        devlog.error("db", e, {"call": getattr(fn, "__name__", "")})
        raise HTTPException(status_code=503, detail=str(e))
    except repo.BadRequest as e:
        devlog.write("action", "rejected", {"call": getattr(fn, "__name__", ""), "reason": str(e)})
        raise HTTPException(status_code=400, detail=str(e))


def _act(name, result, **ids):
    """저장 동작 하나를 logs/action_날짜.log 에 적고 result 를 그대로 돌려준다. 글 내용은 적지 않고 번호 · 상태 · 개수만 적는다."""
    brief = {}
    if isinstance(result, dict):
        for key in ("id", "kind", "seq", "changed", "moved", "status"):
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
    uid = _guard(repo.current_user_id)
    return _guard(repo.list_books, uid, page, size)


@router.get("/books/{book_id}/entries")
def book_entries(book_id: int, page: int = Query(1, ge=1), size: int | None = Query(None, ge=1, le=repo.MAX_SIZE)):
    uid = _guard(repo.current_user_id)
    return _found(_guard(repo.list_entries, uid, book_id, page, size), "책")


@router.get("/entries/{entry_id}")
def entry(entry_id: int):
    uid = _guard(repo.current_user_id)
    return _found(_guard(repo.get_entry, uid, entry_id), "글")


@router.get("/books/{book_id}/diary/{day}")
def diary_by_date(book_id: int, day: datetime.date):
    uid = _guard(repo.current_user_id)
    return _found(_guard(repo.get_entry_by_date, uid, book_id, day.isoformat()), "그 날짜의 일기")


# ── 쓰기 ────────────────────────────────────────────────────────────────────
@router.post("/books")
def create_book(body: dict = Body(...)):
    uid = _guard(repo.current_user_id)
    return _act("create_book", _guard(repo.create_book, uid, (body or {}).get("kind"), (body or {}).get("title")), user=uid)


@router.post("/books/{book_id}/entries")
def open_entry(book_id: int, body: dict | None = Body(None)):
    uid = _guard(repo.current_user_id)
    return _found(_act("open_entry", _guard(repo.open_entry, uid, book_id, (body or {}).get("date")), user=uid, book=book_id, date=(body or {}).get("date")), "책")


@router.put("/entries/{entry_id}/sentences/{seq}")
def put_sentence(entry_id: int, seq: int, body: dict = Body(...)):
    uid = _guard(repo.current_user_id)
    return _found(_act("save_sentence", _guard(repo.save_sentence, uid, entry_id, seq, body), user=uid, entry=entry_id, seq=seq), "글")


@router.post("/entries/{entry_id}/sentences/{seq}/insert")       # 문장 끼워 넣기 (그 자리부터 한 칸씩 뒤로)
def insert_sentence(entry_id: int, seq: int, body: dict = Body(...)):
    uid = _guard(repo.current_user_id)
    return _found(_act("insert_sentence", _guard(repo.insert_sentence, uid, entry_id, seq, body), user=uid, entry=entry_id, seq=seq), "글")


@router.post("/entries/{entry_id}/sentences/{seq}/move")         # 문장 순서 바꾸기  body: {"to": 옮길 자리}
def move_sentence(entry_id: int, seq: int, body: dict = Body(...)):
    uid = _guard(repo.current_user_id)
    return _found(_act("move_sentence", _guard(repo.move_sentence, uid, entry_id, seq, (body or {}).get("to")), user=uid, entry=entry_id, seq=seq, to=(body or {}).get("to")), "글")


@router.post("/entries/{entry_id}/complete")
def complete_entry(entry_id: int):
    uid = _guard(repo.current_user_id)
    return _found(_act("complete_entry", _guard(repo.complete_entry, uid, entry_id), user=uid, entry=entry_id), "글")
