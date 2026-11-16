"""별명 만들기 · 토큰 발급 (01번 화면, FR-025). FastAPI 와 상관없이 쓸 수 있는 일반 함수.

별명 검사는 두 단계다.
  1. 형식 검사 (이 파일): 빈 값, 길이, 쓸 수 있는 글자
  2. 내용 검사 (팀 유효성 검사 diary_pipeline/input_validation.py 의 규칙을 빌려 씀): 비속어, 개인정보, 인젝션
막힌 이유를 자세히 알려 주지 않는 것은 글쓰기 유효성 검사(FR-008)와 같은 방침이다.
"""
import re
import secrets
import unicodedata

import auth
import books_repo
import db
from diary_pipeline.input_validation import Stage1RulePreprocessor

# ── 별명 규칙 (팀 합의 전 임시값. 바꾸면 frontend/src/NicknamePage.jsx 의 maxLength 도 같이) ──
NICKNAME_MIN = 1
NICKNAME_MAX = 10                                  # DB 칸은 30자
NICKNAME_RE = re.compile(r"^[가-힣A-Za-z0-9]+$")    # 한글(완성형) · 영문 · 숫자만, 띄어쓰기 없음


class BadNickname(ValueError):
    """별명이 규칙에 맞지 않을 때 → 400 (메시지를 화면에 그대로 보여 준다)."""


class DuplicateNickname(ValueError):
    """이미 있는 별명 → 409."""


def blocked_by_content(text):
    """팀 유효성 검사 규칙으로 막아야 하면 True (비속어 · 개인정보 · 인젝션)."""
    return (Stage1RulePreprocessor._is_profanity(text)
            or bool(Stage1RulePreprocessor.find_pii_spans(text))
            or bool(Stage1RulePreprocessor.find_injection_spans(text)))


def clean_nickname(nickname):
    """검사를 통과한 별명을 돌려준다. 안 되면 BadNickname."""
    if not isinstance(nickname, str):
        raise BadNickname("별명을 적어 주세요.")
    # 맥/아이패드에서 한 글자가 자모로 풀린 채(조합형) 오는 것을 완성형 한 글자로 합친다
    # (키보드로 친 'ㅂㅗㄱ' 같은 낱자는 합치지 않는다 → 아래 글자 규칙에서 막힌다)
    nickname = unicodedata.normalize("NFC", nickname).strip()
    if not nickname:
        raise BadNickname("별명을 적어 주세요.")
    if len(nickname) < NICKNAME_MIN or len(nickname) > NICKNAME_MAX:
        raise BadNickname(f"별명은 {NICKNAME_MIN}~{NICKNAME_MAX}자로 써 주세요.")
    if not NICKNAME_RE.match(nickname):
        raise BadNickname("별명은 띄어쓰기 없이 한글, 영어, 숫자로만 써 주세요.")
    if blocked_by_content(nickname):
        raise BadNickname("다른 별명을 써 볼까요?")
    return nickname


def create_user(nickname):
    """새 사용자(= 새 목장)를 만들고 토큰을 발급한다. 토큰 원문은 이때 한 번만 돌려준다.
    돌려주는 값: {"token", "nickname"}"""
    nickname = clean_nickname(nickname)
    token = secrets.token_urlsafe(32)

    def work(tx):
        if tx.query("SELECT 1 FROM users WHERE nickname = :n", {"n": nickname}):
            raise DuplicateNickname("이미 있는 별명이에요. 다른 별명을 써 주세요.")
        try:
            tx.insert("INSERT INTO users (nickname, token_hash, created_at) VALUES (:n, :h, :now)",
                      {"n": nickname, "h": auth.hash_token(token), "now": books_repo._now_str()})
        except db.Conflict:                        # 같은 순간에 다른 곳에서 같은 별명을 먼저 만든 경우
            raise DuplicateNickname("이미 있는 별명이에요. 다른 별명을 써 주세요.")

    db.run_in_transaction(work)
    return {"token": token, "nickname": nickname}
