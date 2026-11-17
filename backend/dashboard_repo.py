"""대시보드에 보여 줄 값을 DB에서 모으는 함수들 (요구사항정의서 FR-042 대시보드 메인).

지금 만든 것 (기존 테이블만으로 되는 것)
  - FR-024 이번 주 일기 작성 요일
  - FR-044 내가 골라 쓴 표현

아직 안 만든 것
  - FR-043 다시 살펴볼 맞춤법, FR-021 최근 고친 문장:
    문장을 다시 고쳐 저장하면 이전 교정 기록이 지워져서(books_repo.save_sentence) 지금 데이터로는 만들 수 없다.
    교정 기록을 남기는 방식이 정해지면 추가한다.
"""
import datetime

import books_repo
import db

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
MAX_EXPRESSIONS = 10        # 내가 골라 쓴 표현: 최근 몇 개까지 보여 줄지


def _week_of(day):
    """day 가 들어 있는 주의 월요일과 일요일."""
    monday = day - datetime.timedelta(days=day.weekday())
    return monday, monday + datetime.timedelta(days=6)


def week_diary_days(user_id, today=None):
    """FR-024 이번 주(월~일) 일기 작성 요일.
    - 날짜 기준은 아이가 일기에 고른 날짜(entries.diary_date)
    - 일기책이 여러 권이어도 합쳐서 본다. 같은 날짜는 한 번만 표시
    - '이야기 저장하기'를 한 번이라도 누른 일기만 센다(saved_at). 저장 뒤 다시 고치는 중이어도 빠지지 않게 status 대신 saved_at 을 본다
      (1~2문장 일기를 넣을지는 아직 미정이라 지금은 문장 수와 상관없이 넣는다)"""
    monday, sunday = _week_of(today or books_repo.today_kst())
    rows = db.query(
        """SELECT DISTINCT e.diary_date
             FROM entries e
             JOIN books b ON b.id = e.book_id
            WHERE b.user_id = :uid AND b.kind = 'diary'
              AND e.saved_at IS NOT NULL
              AND e.diary_date BETWEEN :mon AND :sun""",
        {"uid": user_id, "mon": monday, "sun": sunday},
    )
    written = {r["diary_date"] for r in rows}
    days = []
    for i in range(7):
        d = monday + datetime.timedelta(days=i)
        days.append({"date": d, "weekday": WEEKDAYS[i], "written": d in written})
    return {"start": monday, "end": sunday, "days": days, "count": len(written)}


def picked_expressions(user_id, limit=MAX_EXPRESSIONS):
    """FR-044 동화에서 추천받은 표현 중 아이가 직접 골라 쓴 것 (최근 것부터).
    sentences.expression_choice = {"base": 원래 문장, "options": [후보...], "picked": 고른 문장 또는 null}
    picked 가 null(원래 문장 그대로)이면 넣지 않는다. 고르지 않은 후보도 보여 주지 않는다."""
    rows = db.query(
        """SELECT s.id, s.expression_choice, s.written_at, b.id AS book_id, b.title AS book_title
             FROM sentences s
             JOIN entries e ON e.id = s.entry_id
             JOIN books b ON b.id = e.book_id
            WHERE b.user_id = :uid AND b.kind = 'fairy'
              AND s.expression_choice IS NOT NULL
            ORDER BY s.written_at DESC, s.id DESC""",
        {"uid": user_id},
    )
    items = []
    for r in rows:
        choice = books_repo._json(r["expression_choice"]) or {}
        picked = choice.get("picked") if isinstance(choice, dict) else None
        if not picked:
            continue
        items.append({"sentence_id": r["id"], "original": choice.get("base"), "picked": picked,
                      "book_id": r["book_id"], "book_title": r["book_title"], "written_at": r["written_at"]})
        if len(items) >= limit:
            break
    return {"items": items}


def dashboard(user_id):
    """대시보드 메인 한 번에 (FR-042)."""
    return {
        "owner": books_repo.current_nickname(),
        "week": week_diary_days(user_id),
        "expressions": picked_expressions(user_id),
    }
