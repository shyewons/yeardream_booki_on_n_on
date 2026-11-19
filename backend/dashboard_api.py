"""대시보드 주소 (/api/dashboard). 실제 조회는 dashboard_repo.py 가 한다.

  GET /api/dashboard               대시보드 메인 (FR-042)
                                   → {"owner", "week": {start, end, count, days: [{date, weekday, written}]},
                                      "spelling": {min_entries, items: [{before, after, explanation, entry_count, last_at}]},
                                      "expressions": {items: [{original, picked, book_title, written_at ...}]}}
  GET /api/dashboard/recent-fixes  최근 고친 문장 (FR-021)
                                   → {"items": [{fixed_at, kind, kind_label, book_title, diary_date, before, after,
                                                 reasons: [{before, after, explanation}]}]}

토큰이 틀리면 401, DB에 닿지 못하면 503 (books_api 와 같은 규칙).
"""
from fastapi import APIRouter

import dashboard_repo
from books_api import _guard, _user

router = APIRouter(prefix="/api")


@router.get("/dashboard")
def dashboard():
    uid = _user()
    return _guard(dashboard_repo.dashboard, uid)


@router.get("/dashboard/recent-fixes")
def recent_fixes():
    uid = _user()
    return _guard(dashboard_repo.recent_fixes, uid)
