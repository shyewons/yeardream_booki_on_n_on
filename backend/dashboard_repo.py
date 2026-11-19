"""대시보드에 보여 줄 값을 DB에서 모으는 함수들 (요구사항정의서 FR-042 대시보드 메인).

대시보드 메인
  - FR-024 이번 주 일기 작성 요일
  - FR-043 다시 살펴볼 맞춤법
  - FR-044 내가 골라 쓴 표현
대시보드 안의 화면
  - FR-021 최근 고친 문장

문장을 고치거나 지워도 옛 줄은 지우지 않고 '빠진 줄'로 남는다 (books_repo: seq NULL, ended_at, end_reason).
교정 항목(corrections)도 그 줄에 그대로 붙어 있어서, 맞춤법 반복 집계와 고친 문장 기록을 여기서 만든다.

아직 안 만든 것: FR-041 캐릭터 옷장, FR-039 일기 주간 보상 (의상 테이블이 아직 없다)
"""
import datetime

import books_repo
import db

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
MAX_EXPRESSIONS = 10        # 내가 골라 쓴 표현: 최근 몇 개까지 보여 줄지
MAX_SPELLING = 5            # 다시 살펴볼 맞춤법: 몇 개까지 보여 줄지
MIN_SPELLING_ENTRIES = 2    # 다시 살펴볼 맞춤법: 서로 다른 글 몇 개 이상에서 고친 항목만 보여 줄지
MAX_RECENT_FIXES = 20       # 최근 고친 문장: 최근 몇 개까지 보여 줄지
KIND_LABEL = {"diary": "일기", "fairy": "동화"}


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
    picked 가 null(원래 문장 그대로)이면 넣지 않는다. 고르지 않은 후보도 보여 주지 않는다.
    화면에서 빠진 줄(ended_at 이 있는 줄: 다시쓰기 · 지우기 · 표현 다시 고르기)은 넣지 않는다."""
    rows = db.query(
        """SELECT s.id, s.expression_choice, s.written_at, b.id AS book_id, b.title AS book_title
             FROM sentences s
             JOIN entries e ON e.id = s.entry_id
             JOIN books b ON b.id = e.book_id
            WHERE b.user_id = :uid AND b.kind = 'fairy'
              AND s.expression_choice IS NOT NULL
              AND s.ended_at IS NULL
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


def spelling_to_review(user_id, limit=MAX_SPELLING, min_entries=MIN_SPELLING_ENTRIES):
    """FR-043 여러 글에서 반복해 고친 맞춤법 · 띄어쓰기 항목.
    - 같은 항목 = 고치기 전 표현(before_text)과 고친 표현(after_text)이 둘 다 같은 것
    - 서로 다른 글(entry) 수로 센다. 같은 글에서 다시 검사하거나 표현을 골라 줄이 새로 생겨도 한 번만 센다
    - 빠진 줄(다시쓰기 · 지우기)의 교정도 아이가 실제로 틀렸던 기록이라 포함한다
    - corrections 에는 맞춤법 교정만 들어간다. 동화 표현 제안(expression_choice)은 여기에 없다
    - 많이 반복된 것부터, 같으면 최근에 고친 것부터. 설명은 가장 최근 교정의 것을 쓴다"""
    rows = db.query(
        """SELECT c.id, c.before_text, c.after_text, c.explanation, s.entry_id, s.written_at
             FROM corrections c
             JOIN sentences s ON s.id = c.sentence_id
             JOIN entries e ON e.id = s.entry_id
             JOIN books b ON b.id = e.book_id
            WHERE b.user_id = :uid
            ORDER BY s.written_at DESC, c.id DESC""",
        {"uid": user_id},
    )
    groups = {}                                   # (before, after) → 모은 값. rows 가 최근 순이라 처음 본 것이 가장 최근
    for r in rows:
        key = (r["before_text"], r["after_text"])
        if key[0] == key[1]:
            continue
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"before": key[0], "after": key[1], "explanation": r["explanation"],
                               "last_at": r["written_at"], "entries": set()}
        g["entries"].add(r["entry_id"])
    picked = [g for g in groups.values() if len(g["entries"]) >= min_entries]
    picked.sort(key=lambda g: (len(g["entries"]), g["last_at"]), reverse=True)
    items = [{"before": g["before"], "after": g["after"], "explanation": g["explanation"],
              "entry_count": len(g["entries"]), "last_at": g["last_at"]} for g in picked[:limit]]
    return {"items": items, "min_entries": min_entries}


def recent_fixes(user_id, limit=MAX_RECENT_FIXES):
    """FR-021 최근 고친 문장: 교정을 받은 문장을 아이가 직접 다시 써서 바꾼 기록 (최근 것부터).
    - 고치기 전: end_reason = 'edit' 로 빠진 옛 줄의 원문 (그때 교정 항목이 붙어 있던 줄만)
    - 고친 뒤: 같은 글에 그 시각(ended_at = written_at)에 새로 들어간 줄의 원문 = 아이가 실제로 다시 쓴 문장
      (AI가 제안한 최종 문장 revised 를 고친 문장으로 보여 주지 않는다)
    - 사유: 옛 줄에 붙어 있던 교정 항목 (고치기 전 표현 → 고친 표현, 설명)"""
    rows = db.query(
        """SELECT o.id, o.original AS before_sentence, o.ended_at, n.original AS after_sentence,
                  b.kind, b.title AS book_title, e.diary_date
             FROM sentences o
             JOIN entries e ON e.id = o.entry_id
             JOIN books b ON b.id = e.book_id
             JOIN sentences n ON n.id = (SELECT MIN(n2.id) FROM sentences n2
                                          WHERE n2.entry_id = o.entry_id AND n2.written_at = o.ended_at AND n2.id > o.id)
            WHERE b.user_id = :uid AND o.end_reason = 'edit' AND o.has_correction = 1
            ORDER BY o.ended_at DESC, o.id DESC
            LIMIT :lim""",
        {"uid": user_id, "lim": limit},
    )
    items = []
    for r in rows:
        reasons = db.query(
            "SELECT before_text, after_text, explanation FROM corrections WHERE sentence_id = :sid ORDER BY idx",
            {"sid": r["id"]},
        )
        items.append({"sentence_id": r["id"], "fixed_at": r["ended_at"], "kind": r["kind"],
                      "kind_label": KIND_LABEL.get(r["kind"], r["kind"]), "book_title": r["book_title"],
                      "diary_date": r["diary_date"], "before": r["before_sentence"], "after": r["after_sentence"],
                      "reasons": [{"before": x["before_text"], "after": x["after_text"], "explanation": x["explanation"]}
                                  for x in reasons]})
    return {"items": items}


def dashboard(user_id):
    """대시보드 메인 한 번에 (FR-042)."""
    return {
        "owner": books_repo.current_nickname(),
        "week": week_diary_days(user_id),
        "spelling": spelling_to_review(user_id),
        "expressions": picked_expressions(user_id),
    }
