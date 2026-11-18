"""보상 기준 숫자 모음. 보상 조건을 바꿀 때는 이 파일의 숫자만 고친다.

쓰는 곳
  books_repo.py      일기 하루치 달성(entries.day_done_at)을 적을 때 · 글 응답의 rules
  progress_repo.py   보상 코드가 부르는 '세는 함수'들
  화면               글 응답(get_entry)의 rules 로 받는다 (이야기 완성 권유 등). 화면에 숫자를 따로 적지 않는다

세는 문장은 모두 '화면에 보이는 문장'(sentences.seq IS NOT NULL)이다.
  다시쓰기 · 지우기 · 표현 선택으로 빠진 옛 줄과, 확인하기 전의 임시저장(entries.draft_text)은 세지 않는다.

정한 날: 2026-11-18 (팀 의논). 동화는 같은 날 오후에 '10문장 = 한 페이지'에서 '장' 기준(디자인 04C)으로 바꿨다
"""

# ── 일기 ──
DIARY_DAY_SENTENCES = 3     # 하루치로 치는 문장 수 (이만큼 쓰면 entries.day_done_at 을 적는다)
DIARY_LATE_DAYS = 3         # 지난 날짜 일기를 며칠 뒤까지 하루치로 인정할지 (15일 일기 → 18일까지). 앞으로 올 날짜는 아예 못 쓴다
WEEK_MIN_DAYS = 5           # 한 주(월~일, 한국 시간)에 하루치를 채운 날이 이만큼이면 주간 달성. 지난 주 보상도 기한 없이 받을 수 있다

# ── 동화 ── (동화 책 하나 = 이야기 하나, 이야기는 장으로 나뉜다. books_repo.py 의 '동화 장' 참고)
STORY_CHAPTER_MIN_SENTENCES = 3       # 보상 · 끝내기에 세는 장: 보이는 문장이 이만큼 이상인 장
STORY_REWARD_CHAPTERS = (3, 6, 10)    # 장 보상 구간: 위 기준을 채운 장이 이 수가 되면 보상 (디자인 04C 의 선물 3개)
STORY_FINISH_MIN_CHAPTERS = 3         # '이야기 끝내기'를 할 수 있는 최소 장 수 (완성 보상도 이 기준. 첫 장 보상 구간과 같게)
STORY_FINISH_ASK_AT = (3, 6, 9)       # 이 장 수를 채우고 나갈 때 '끝낼까요?'를 한 번씩 묻는다. 마지막 장(STORY_MAX_CHAPTERS)은 채운 뒤 나갈 때마다 묻는다
STORY_MAX_CHAPTERS = 10               # 이야기 하나의 최대 장 수


def public():
    """화면에 보내는 기준 숫자 (글 응답의 rules)."""
    return {
        "diary_day_sentences": DIARY_DAY_SENTENCES,
        "diary_late_days": DIARY_LATE_DAYS,
        "story_chapter_min_sentences": STORY_CHAPTER_MIN_SENTENCES,
        "story_reward_chapters": list(STORY_REWARD_CHAPTERS),
        "story_finish_min_chapters": STORY_FINISH_MIN_CHAPTERS,
        "story_finish_ask_at": list(STORY_FINISH_ASK_AT),
        "story_max_chapters": STORY_MAX_CHAPTERS,
    }
