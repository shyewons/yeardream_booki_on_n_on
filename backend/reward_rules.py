"""보상 기준 숫자 모음. 보상 조건을 바꿀 때는 이 파일의 숫자만 고친다.

쓰는 곳
  books_repo.py      일기 하루치 달성(entries.day_done_at)을 적을 때 · 글 응답의 rules
  progress_repo.py   보상 코드가 부르는 '세는 함수'들
  화면               글 응답(get_entry)의 rules 로 받는다 (이야기 완성 권유 등). 화면에 숫자를 따로 적지 않는다

세는 문장은 모두 '화면에 보이는 문장'(sentences.seq IS NOT NULL)이다.
  다시쓰기 · 지우기 · 표현 선택으로 빠진 옛 줄과, 확인하기 전의 임시저장(entries.draft_text)은 세지 않는다.

정한 날: 2026-11-18 (팀 의논)
"""

# ── 일기 ──
DIARY_DAY_SENTENCES = 3     # 하루치로 치는 문장 수 (이만큼 쓰면 entries.day_done_at 을 적는다)
DIARY_LATE_DAYS = 3         # 지난 날짜 일기를 며칠 뒤까지 하루치로 인정할지 (15일 일기 → 18일까지). 앞으로 올 날짜는 아예 못 쓴다
WEEK_MIN_DAYS = 5           # 한 주(월~일, 한국 시간)에 하루치를 채운 날이 이만큼이면 주간 달성. 지난 주 보상도 기한 없이 받을 수 있다

# ── 동화 ──
STORY_PAGE_SENTENCES = 10   # 한 페이지로 치는 문장 수. 페이지 보상은 '다음 페이지의 첫 문장'(11번째, 21번째 …)을 쓸 때 생긴다.
                            # 마지막 페이지는 페이지 보상 대신 완성 보상을 받는다 (겹치지 않게)
                            # 화면의 한 쪽 줄 수(PostDetailPage.jsx 의 SENTENCES_PER_PAGE)와는 따로다: 디자인 때문에 화면을 바꿔도 보상은 그대로
STORY_DONE_MIN_SENTENCES = 10   # 완성 보상: '이야기 저장하기'(status = done)를 누르고, 문장이 이만큼 이상일 때


def public():
    """화면에 보내는 기준 숫자 (글 응답의 rules)."""
    return {
        "diary_day_sentences": DIARY_DAY_SENTENCES,
        "diary_late_days": DIARY_LATE_DAYS,
        "story_page_sentences": STORY_PAGE_SENTENCES,
        "story_done_min_sentences": STORY_DONE_MIN_SENTENCES,
    }
