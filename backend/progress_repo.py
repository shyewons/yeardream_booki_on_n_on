"""보상 코드가 부르는 '세는 함수' 모음. 판단(보상을 줄지)과 받기(reward_claims)는 하지 않고, 숫자만 센다.

기준 숫자는 reward_rules.py 에 있다. 모두 user_id 로 걸러서 내 책 · 글만 센다.
세는 문장은 화면에 보이는 문장(seq IS NOT NULL)뿐이다 (다시쓰기 · 지우기 · 표현 선택으로 빠진 옛 줄은 세지 않는다).

  diary_done_days(uid, 시작일, 끝일)   일기 하루치를 채운 날짜 목록
  week_status(uid, 날짜)               그 날짜가 든 주(월~일)의 하루치 날짜 수와 주간 달성 여부
  story_progress(uid, 책 번호)         동화 한 편의 문장 수 · 페이지 보상 개수 · 완성 보상 조건
  topic_counts(uid, 책 번호=None)      동화 주제별 문장 수 (주제를 바꿔 가며 쓴 경우 포함)

보상을 이미 받았는지는 보상 코드가 reward_claims 와 비교한다.
  예: 페이지 보상을 2번까지 받았으면, story_progress 의 pages_closed 가 3 이상이 될 때만 3번 보상을 준다.
      (20줄 → 2번까지 받음 → 5줄 지움 → 다시 5줄 써도 pages_closed 는 1 → 새 보상 없음. 받은 보상은 그대로 둔다)
"""
import datetime

import db
import reward_rules as rules
from books_repo import today_kst, _as_date


def week_start_of(day=None):
    """그 날짜가 든 주의 월요일 (한국 시간 기준). day 를 안 주면 오늘."""
    day = _as_date(day) or today_kst()
    return day - datetime.timedelta(days=day.weekday())


def diary_done_days(user_id, start, end):
    """start ~ end(둘 다 포함) 사이에 일기 하루치를 채운 날짜(date) 목록. 일기 책이 여러 권이어도 같은 날은 한 번만 센다.
    하루치는 entries.day_done_at 이 적힌 글이다 (books_repo._mark_day_done: 3문장 · 날짜 + 3일 안)."""
    rows = db.query(
        """SELECT DISTINCT e.diary_date AS d
             FROM entries e JOIN books b ON b.id = e.book_id
            WHERE b.user_id = :uid AND b.kind = 'diary' AND e.day_done_at IS NOT NULL
              AND e.diary_date BETWEEN :s AND :e
            ORDER BY d""",
        {"uid": user_id, "s": _as_date(start).isoformat(), "e": _as_date(end).isoformat()})
    return [_as_date(r["d"]) for r in rows]


def week_status(user_id, day=None):
    """day 가 든 주(월~일)의 일기 하루치. {"week_start", "days": [날짜...], "count", "need", "achieved"}.
    지난 주도 기한 없이 물어볼 수 있다 (지난 날짜 일기는 3일 안에만 하루치가 되므로 몰아 채우기는 이미 막혀 있다)."""
    start = week_start_of(day)
    days = diary_done_days(user_id, start, start + datetime.timedelta(days=6))
    return {"week_start": start.isoformat(), "days": [d.isoformat() for d in days], "count": len(days),
            "need": rules.WEEK_MIN_DAYS, "achieved": len(days) >= rules.WEEK_MIN_DAYS}


def story_progress(user_id, book_id):
    """동화 책 한 권(= 이야기 한 편)의 진행. 책이 없거나 내 동화 책이 아니면 None.
      sentence_count   보이는 문장 수
      pages_closed     페이지 보상 개수: 다음 페이지의 첫 문장을 쓴 페이지 수. (문장 수 - 1) // STORY_PAGE_SENTENCES
                       10줄 → 0, 11줄 → 1, 20줄 → 1, 21줄 → 2. 마지막 페이지는 완성 보상이 대신한다
      done             '이야기 저장하기'를 눌렀는지 (status = done)
      done_reward_ok   완성 보상 조건: done 이고 문장이 STORY_DONE_MIN_SENTENCES 개 이상"""
    rows = db.query(
        """SELECT e.id, e.status,
                  (SELECT COUNT(*) FROM sentences s WHERE s.entry_id = e.id AND s.seq IS NOT NULL) AS n
             FROM entries e JOIN books b ON b.id = e.book_id
            WHERE b.id = :bid AND b.user_id = :uid AND b.kind = 'fairy'
            ORDER BY e.id LIMIT 1""",
        {"bid": book_id, "uid": user_id})
    if not rows:
        book = db.query("SELECT id FROM books WHERE id = :bid AND user_id = :uid AND kind = 'fairy'", {"bid": book_id, "uid": user_id})
        if not book:
            return None
        return {"book_id": book_id, "entry_id": None, "sentence_count": 0, "pages_closed": 0, "done": False, "done_reward_ok": False}
    r = rows[0]
    n = int(r["n"])
    done = r["status"] == "done"
    return {"book_id": book_id, "entry_id": r["id"], "sentence_count": n,
            "pages_closed": max(0, (n - 1) // rules.STORY_PAGE_SENTENCES),
            "done": done, "done_reward_ok": done and n >= rules.STORY_DONE_MIN_SENTENCES}


def topic_counts(user_id, book_id=None):
    """동화 주제별 보이는 문장 수 [{"topic_id", "title", "sentences", "books"}]. book_id 를 주면 그 책만.
    주제 없이 쓴 문장(NULL)은 topic_id = None 한 줄로 묶는다."""
    p = {"uid": user_id}
    only = ""
    if book_id is not None:
        only = "AND b.id = :bid"
        p["bid"] = book_id
    rows = db.query(
        f"""SELECT s.fairy_topic_id AS topic_id, t.title, COUNT(*) AS n, COUNT(DISTINCT b.id) AS books
              FROM sentences s
              JOIN entries e ON e.id = s.entry_id
              JOIN books b ON b.id = e.book_id
              LEFT JOIN fairy_topics t ON t.id = s.fairy_topic_id
             WHERE b.user_id = :uid AND b.kind = 'fairy' AND s.seq IS NOT NULL {only}
             GROUP BY s.fairy_topic_id, t.title
             ORDER BY n DESC""", p)
    return [{"topic_id": r["topic_id"], "title": r["title"], "sentences": int(r["n"]), "books": int(r["books"])} for r in rows]
