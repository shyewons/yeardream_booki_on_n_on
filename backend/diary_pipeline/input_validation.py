# -*- coding: utf-8 -*-
"""
[아이 일기 입력 단계 - 유효성 검사 노드 (규칙 전용, LLM·네트워크 없음)]
파일명: input_validation.py

플로우(서비스 플로우 05)에서의 위치
  문장 쓰기('확인하기') -> [유효성 검사: 규칙 기반] -> 통과 -> 문장 교정(① et5 ...)
                                                   -> 불통과 -> 다시 입력 안내 -> 문장 쓰기
  일기/동화 공통 단계다. 모드(일기/동화)와 상관없이 같은 규칙을 쓴다.

데이터 명세(엑셀 '유효성 검사' 행)
  input  : user_input (str)          사용자가 적은 원본 문장 (수정되지 않은 날 것)
  output : original_sentence (str)   유효성 검사를 통과한, 아이가 쓴 그대로의 원문 문장
  (개인정보 선택지/한·영 선택지를 아이가 직접 고른 경우에는 '고른 결과가 반영된 글'이 나간다. 태그·치환 표시는 없다.)

호출 방식 = 제출 1회당 노드 1번 (문장 쓰기 화면이 API 경계)
  validate_node(state) -> dict      LangGraph 노드. 바뀐 키만 돌려준다.
  route_after_validation(state)     조건부 간선: "correction"(통과) / "retry"(다시 입력 안내) / "skipped"(3번 실패, 이 줄 건너뜀)
  validate_sentence(...)            같은 로직을 State 없이 부르는 함수 (FastAPI 등에서 바로 호출 가능)
  build_graph(...)                  langgraph가 설치돼 있을 때 그래프로 묶어 주는 함수

한 줄(문장)은 입력 최대 3번 (선택지 고르기는 횟수에 안 센다)
  통과하면 original_sentence 반환 / 못 넘으면 retry_message와 함께 다시 입력 / 3번째도 못 넘으면 line_skipped=True
  (문장 틀·빈칸·감정 분류 같은 '유도'는 쓰지 않는다. 되묻는 문구만 상황별로 다르다.)

문제가 있을 때의 처리
  - 욕설/비속어, 100자 초과, 난타·무의미, 분량 부족, 직전 문장 복붙 : 되묻기(재작성)
  - 인젝션 의심 : 의심 구간만 highlights로 알려 주고 그 부분을 다른 말로 바꿔 쓰도록 되묻기
  - 개인정보(전화번호/이메일/집 주소/학교 이름) :
      PII_CHOICE_FROM_ATTEMPT 번째 입력 전 -> 하이라이트 + 되묻기
      그 이후 입력 -> '개인정보 말고는 문제가 없으면' awaiting_choice=True 와 선택지(highlights[*].choices).
                      조사까지 맞춘 고정 선택지를 UI가 보여 주고, 고른 번호를 choice_picks로 다시 보내면 바뀐 문장을 한 번 더 검사한다.
  - 한/영 자판 오타로 보이면 선택지(한글로 바꾼 글 / 영어 그대로)를 같은 방식으로 묻는다.

규칙 수정 위치
  파일 위쪽 [0] '수정해서 쓰는 규칙 설정' 구역(분량/반복/복붙 기준 숫자, 개인정보·인젝션·욕설 목록, 선택지, 문구)만 고치면 된다.

규칙이 못 하는 일
  - 뜻이 있는 글인지, 문장이 끝났는지, 외국어 발음 표기인지, 이름/지명(예: 강남이, 당산), 도로명 주소 가리기
  - 변형된 인젝션/욕설(띄어쓰기를 끼운 우회 등)
"""

import re
import difflib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, TypedDict, Literal


# =====================================================================
# [0] ★ 수정해서 쓰는 규칙 설정 (여기만 고치면 됩니다) ★
#   - 숫자/목록만 바꾸면 되고, 아래 [1] 이후의 코드는 건드리지 않아도 됩니다.
#   - 바꾼 뒤에는 `python test_input_validation.py --interactive`로 직접 입력해 보며 확인하세요. (`python test_input_validation.py`는 전체 테스트)
#   - 값이 클수록 엄격한지 느슨한지를 각 줄 주석에 적어 두었습니다.
# =====================================================================

# ---- (A) 입력 횟수 / 길이 -------------------------------------------
MAX_STEPS = 3            # 한 줄당 입력 가능 횟수. 이 횟수까지 규칙을 못 넘으면 그 줄은 건너뜀
PII_CHOICE_FROM_ATTEMPT = 2   # 개인정보(주소/학교/전화번호)만 문제일 때 '선택지 팝업'을 띄우기 시작하는 입력 순번.
                              #  1이면 첫 입력부터 선택지, 2면 첫 입력은 다시 쓰기 안내 후 2·3번째부터 선택지, 4 이상이면 선택지 없음
MAX_CHARS = 100          # 한 번에 입력 가능한 최대 글자 수 (화면 maxlength와 같은 값으로 맞출 것). 넘으면 되묻기(자르지 않음)

# ---- (B) 분량 규칙 ----------------------------------------------------
MIN_HANGUL_CHARS = 4     # 한글이 최소 몇 글자여야 하는지 (올리면 엄격). 자모(ㅋㅋ)·영어·숫자는 세지 않음
MIN_WORDS = 2            # 최소 어절 수 (띄어쓰기 단위). 1로 내리면 '재밌었다' 같은 한 단어도 통과
LONG_SINGLE_WORD_CHARS = 8   # 띄어쓰기를 안 해도 한글이 이 글자 수 이상이면 어절 수와 상관없이 분량 충족 (저학년 대응)

# ---- (C) 무의미/반복/복붙 판단 -----------------------------------------
SIMILARITY_LIMIT = 0.80  # 직전 문장과 이 비율 이상 비슷하면 복붙으로 봄 (낮추면 엄격, 1.0이면 완전히 같을 때만)
LOW_DIVERSITY_MIN_LEN = 6    # '오늘오늘오늘' 검사는 한글이 이 글자 수 이상일 때만 함
LOW_DIVERSITY_RATIO = 0.30   # 서로 다른 글자 비율이 이 값 이하면 같은 글자 반복으로 봄 (올리면 엄격)
SPACED_OUT_MIN_WORDS = 4     # '한 글 로 만 씀' 검사는 어절이 이 수 이상일 때만 함
SPACED_OUT_RATIO = 0.80      # 한 글자짜리 어절이 이 비율 이상이면 글자마다 띄어 쓴 것으로 봄

# ---- (C-2) 글 종류별 기준 (일기 / 동화) ---------------------------------
#   위 (A)(B)(C)의 값이 기본값(일기)이다. 종류마다 다르게 하고 싶은 값만 여기에 "이름: 값"으로 적는다.
#   적지 않은 값은 위의 기본값을 그대로 쓴다. 줄을 지우면 그 값은 일기와 같아진다.
#   적을 수 있는 이름: MAX_STEPS, MAX_CHARS, MIN_HANGUL_CHARS, MIN_WORDS, LONG_SINGLE_WORD_CHARS,
#                     SIMILARITY_LIMIT, LOW_DIVERSITY_MIN_LEN, LOW_DIVERSITY_RATIO, SPACED_OUT_MIN_WORDS, SPACED_OUT_RATIO
#   (개인정보 · 욕설 · 인젝션 검사는 종류와 상관없이 똑같이 한다)
KIND_RULES = {
    "diary": {},                     # 일기: 전부 기본값
    "fairy": {                       # 동화: 짧은 대사·의성어("야옹!", "쿵쿵!")와 되풀이되는 문장을 조금 더 허용한다
        "MIN_HANGUL_CHARS": 2,       #  한글 최소 글자 수 (일기 4)
        "MIN_WORDS": 1,              #  최소 어절 수 (일기 2). 1이면 "야옹!" 같은 한 단어도 통과
        "SIMILARITY_LIMIT": 0.90,    #  앞 문장과 비슷한 정도 (일기 0.80). 동화는 "첫째 돼지는…/둘째 돼지는…"처럼 닮은 문장이 자주 나온다. 1.0이면 똑같을 때만 막음
    },
}
DEFAULT_KIND = "diary"               # 종류를 안 주거나 모르는 종류면 이 기준을 쓴다


def rule(kind: Optional[str], name: str):
    """종류(kind)에 맞는 기준값. KIND_RULES 에 적혀 있으면 그 값, 없으면 위의 기본값."""
    return KIND_RULES.get(kind or DEFAULT_KIND, {}).get(name, globals()[name])

# ---- (D) 화면 문구 (문장 쓰기 화면에서 쓰는 고정 안내 문구) ----------------------------------------------------
# 첫 입력 전 유도 질문 (고정 문구)
OPENING_FIRST = [
    "오늘 뭐가 제일 기억에 남아요? 한 문장으로 적어보세요.",
    "오늘 누구와 무엇을 했는지 떠올려 보세요. 한 문장으로 적어볼까요?",
]
OPENING_NEXT = [
    "그다음에는 어떤 일이 있었나요?",
    "그때 기분은 어땠는지 적어볼까요?",
    "기억에 남는 다른 일도 있었나요?",
    "내일은 무엇을 하고 싶은지 적어볼까요?",
]


# 종류별 되묻기 문구. 일기 문구는 아래 코드([4], [5])에 적힌 그대로 쓰고, 동화에서 다르게 할 문구만 여기에 적는다.
#   (적지 않은 문구는 일기와 같은 문구가 나간다. {text} {kinds} 자리는 코드가 채운다)
KIND_MESSAGES = {
    "fairy": {
        "profanity": "예쁜 말로 바꿔서 이야기를 한 문장으로 적어볼까요?",
        "pii": "개인정보({kinds})는 이야기에 쓰지 않아요. 표시된 부분을 지어낸 이름으로 바꿔서 다시 적어볼까요?",
        "pii_choice": "표시된 부분은 개인정보라서 이야기에 쓰지 않아요. 어떤 말로 바꿀까요?",
        "copied": "방금 쓴 문장과 아주 비슷해요. 그다음에는 어떤 일이 벌어졌는지 적어볼까요?",
        "nothing": "어떤 장면이 떠오르나요? 누가 무엇을 했는지 한 문장으로 편하게 적어볼까요?",
        "more_about": "'{text}'에 대해 조금 더 적어볼까요? 누가, 무엇을 했는지 한 문장으로 써보세요.",
        "default": "누가 나와서 어떤 일이 벌어졌는지 한 문장으로 적어볼까요?",
        "empty": "글이 비어 있어요. 상상한 이야기를 한 문장으로 적어볼까요?",
        "numeric": "숫자만으로는 이야기를 쓸 수 없어요. 한글로 직접 적어볼까요?",
    },
}


def say(kind: Optional[str], key: str, default: str) -> str:
    """종류에 맞는 문구. KIND_MESSAGES 에 있으면 그 문구, 없으면 일기 문구(default)."""
    return KIND_MESSAGES.get(kind or DEFAULT_KIND, {}).get(key, default)


# ---- (E) 개인정보 / 인젝션 / 욕설 목록 ---------------------------------
#   패턴은 파이썬 정규식. 추가/삭제만 하면 되고, 오탐을 줄이려면 뒤따름 조건 (?!...) 으로 예외를 뺀다.
# ---------------------------------------------------------------------
# 개인정보 패턴: (종류, 정규식, 구간으로 잡을 그룹 번호)
#  - 이름/지명/도로명 주소는 오탐이 많아 규칙으로 가리지 않는다.
# ---------------------------------------------------------------------
PII_PATTERNS = [
    # 휴대폰 / 지역번호(02, 031 등) 붙여 쓴 것 / 하이픈으로 구분된 일반 번호
    ("전화번호", r"(?<!\d)(?:01[016789]-?\d{3,4}-?\d{4}|0(?:2|[3-6][1-5])-?\d{3,4}-?\d{4}|\d{2,3}-\d{3,4}-\d{4})(?!\d)", 0),
    # 이메일: '@'와 그 뒤 '.도메인'이 모두 있어야 한다 (@만 쓴 글은 제외). 영문/숫자/._%+- 로만 이루어진 형태
    ("이메일", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+", 0),
    ("집주소", r"\d+\s*동\s*\d+\s*호|(?<!\d)\d{3,4}\s?호(?!선)", 0),
    ("학교", r"[가-힣]{2,6}(?:초등학교|중학교|고등학교)", 0),
    ("학교", r"(?:^|\s)([가-힣]{2,4}초)(?=에서|에|는|가|도|를|와|랑|\s|$)", 1),
]
PII_LABEL = {"전화번호": "전화번호", "이메일": "이메일 주소", "집주소": "집 주소", "학교": "학교 이름"}
# 선택지는 고정 목록(아이가 고르는 것이라 시스템이 지어낸 말이 아님). '지우기'는 항상 마지막에 붙는다.
PII_CHOICES = {
    "집주소": ["우리 집", "친구 집", "놀이터"],
    "학교": ["우리 학교", "학교"],
    "전화번호": ["친구 번호", "우리 집 번호"],
    "이메일": ["친구 이메일", "내 이메일"],
}

# ---------------------------------------------------------------------
# 인젝션 의심 패턴. 공백을 모두 뗀 글자열에서 찾고, 찾은 구간을 원문 위치로 되돌려 하이라이트한다.
#  - 오탐 방지 우선이라 이 패턴을 피한 변형은 막지 못한다.
#  - '(?P<x>...)'가 있으면 그 부분만, 없으면 매칭 전체를 구간으로 본다.
# ---------------------------------------------------------------------
INJECTION_PATTERNS = [
    r"프롬프트.{0,6}(무시|알려|보여|출력|말해|잊)(?:하고|하라고|하세요|해줘|해라|하라|해)?",
    r"(이전|앞선|앞의|위의|기존)(내용|명령|지시|프롬프트).{0,4}(무시|잊)(?:하고|하라고|하세요|해줘|해라|하라|해)?",
    r"(ignore|forget|disregard).{0,12}(previous|above|prior|instruction|prompt)[a-z]{0,12}",
    r"systemprompt|시스템프롬프트",
    # 대필 요청: '일기/대신/너가/네가'가 함께 있을 때, 또는 문장 끝맺음일 때. '그려줘서'처럼 이어지는 말은 제외
    r"(일기|대신|너가|네가).{0,6}(써|적어|만들어|지어|작성해)줘(?!서|도|야지)",
    r"(?P<x>(써|적어|만들어|지어|작성해)줘)(?=[.!?~]*$)",
]

# ---------------------------------------------------------------------
# 욕설/비속어 목록 (대표어 일부). 계속 늘려 가는 것을 전제로 한다.
#  - 다른 뜻으로도 흔히 쓰이는 말은 넣지 않는다: '새끼'(새끼 고양이/새끼손가락), '시바'(시바견),
#    '꺼져'(불이 꺼져서), '닥쳐'(시험이 닥쳐서), '뒤져'(서랍을 뒤져서), '미친'(미친 듯이), '엿', '씹다' 등
#  - 뜻이 갈리는 말은 예외를 뒤따름 조건((?!...))으로 뺀다: 시발점/시발역, 병신년, 등신대
#  - 띄어쓰기를 끼운 우회('시 발')는 막지 못한다 (붙여서 보면 '아이시 발견' 같은 정상 문장이 걸리기 때문)
# ---------------------------------------------------------------------
PROFANITY_PATTERNS = [
    r"씨발|씨바알|씨빨|시발(?!점|역)|시팔|씨팔",
    r"병신(?!년)|븅신|병쉰",
    r"지랄",
    r"개새끼|개새키|개색히|개세끼|씹새끼|씹창|씹쌔",
    r"좆|존나|존내|존니",
    r"미친놈|미친년|미친새끼|또라이|돌아이",
    r"썅|염병|엿먹어|호로새끼|창녀|찐따",
    r"등신(?!대|불)|뒈져|뒈질|죽여버|죽어버려",
]
# 초성만 쓴 욕설: 자음만으로 된 덩어리는 짧으면 포함 여부, 길면 앞/끝/2회 이상일 때만 본다 (무작위 난타 속 우연한 한 번은 제외)
PROFANITY_JAMO = r"ㅅㅂ|ㅆㅂ|ㅂㅅ|ㅈㄹ|ㅈㄴ|ㅁㅊ|ㅅㄲ"
# 글자와 자모가 섞인 형태 ('시ㅂ', 'ㅅ발', 'ㅄ같은', 'ㅂ신')
PROFANITY_MIXED = r"[시씨]ㅂ|[ㅅㅆ]발|ㅂ신|병ㅅ|ㅈ랄|ㅈ같|ㅄ"

# =====================================================================
# [0-1] 내부 처리용 표 (조사/받침). 보통 수정할 필요 없음
# =====================================================================
# ---------------------------------------------------------------------
# 조사: 선택지에 조사까지 붙여서 보여주기 위한 표. (받침 있을 때, 없을 때)
# ---------------------------------------------------------------------
JOSA_PAIRS = {
    "은": ("은", "는"), "는": ("은", "는"), "이": ("이", "가"), "가": ("이", "가"),
    "을": ("을", "를"), "를": ("을", "를"), "과": ("과", "와"), "와": ("과", "와"),
    "으로": ("으로", "로"), "로": ("으로", "로"), "이랑": ("이랑", "랑"), "랑": ("이랑", "랑"),
    "이라서": ("이라서", "라서"), "라서": ("이라서", "라서"), "이야": ("이야", "야"), "야": ("이야", "야"),
    "이다": ("이다", "다"), "다": ("이다", "다"),
}
# 바로 뒤에 어절이 끝나는 경우만 조사로 본다 ('학교가기'의 '가'는 조사가 아님)
# (받침에 따라 모양이 바뀌지 않는 조사 에서/에/도/만 ...도 함께 잡아서, 선택지에 조사까지 보여주고 고를 때 같이 바꾼다)
JOSA_RE = r"(이라서|라서|이랑|랑|으로|로|이다|이야|에게서|에게|한테|에서|부터|까지|처럼|보다|은|는|이|가|을|를|과|와|야|다|에|도|만)(?=$|[\s.!?,~])"

# 받침 이름 (받침 ㅅ + 이어 친 ㅂ = '닛ㅂ' 같은 걸침을 찾는 데 쓴다)
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ",
        "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]



# =====================================================================
# [1] 두벌식 영타 -> 한글 완성형 자동 변환기
# =====================================================================
class EngToKorKeyboardConverter:
    ENG_KEY_TO_JAMO = {
        'q': 'ㅂ', 'Q': 'ㅃ', 'w': 'ㅈ', 'W': 'ㅉ', 'e': 'ㄷ', 'E': 'ㄸ',
        'r': 'ㄱ', 'R': 'ㄲ', 't': 'ㅅ', 'T': 'ㅆ', 'y': 'ㅛ', 'u': 'ㅕ',
        'i': 'ㅑ', 'o': 'ㅐ', 'O': 'ㅒ', 'p': 'ㅔ', 'P': 'ㅖ',
        'a': 'ㅁ', 's': 'ㄴ', 'd': 'ㅇ', 'f': 'ㄹ', 'g': 'ㅎ', 'h': 'ㅗ',
        'j': 'ㅓ', 'k': 'ㅏ', 'l': 'ㅣ',
        'z': 'ㅋ', 'x': 'ㅌ', 'c': 'ㅊ', 'v': 'ㅍ', 'b': 'ㅠ', 'n': 'ㅜ', 'm': 'ㅡ'
    }

    CHOSUNG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    JUNGSUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
    JONGSUNG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

    COMPOUND_VOWELS = {
        ('ㅗ', 'ㅏ'): 'ㅘ', ('ㅗ', 'ㅐ'): 'ㅙ', ('ㅗ', 'ㅣ'): 'ㅚ',
        ('ㅜ', 'ㅓ'): 'ㅝ', ('ㅜ', 'ㅔ'): 'ㅞ', ('ㅜ', 'ㅣ'): 'ㅟ',
        ('ㅡ', 'ㅣ'): 'ㅢ'
    }
    COMPOUND_CONSONANTS = {
        ('ㄱ', 'ㅅ'): 'ㄳ', ('ㄴ', 'ㅈ'): 'ㄵ', ('ㄴ', 'ㅎ'): 'ㄶ',
        ('ㄹ', 'ㄱ'): 'ㄺ', ('ㄹ', 'ㅁ'): 'ㄻ', ('ㄹ', 'ㅂ'): 'ㄼ', ('ㄹ', 'ㅅ'): 'ㄽ', ('ㄹ', 'ㅌ'): 'ㄾ', ('ㄹ', 'ㅍ'): 'ㄿ', ('ㄹ', 'ㅎ'): 'ㅀ',
        ('ㅂ', 'ㅅ'): 'ㅄ', ('ㅅ', 'ㅅ'): 'ㅆ', ('ㄱ', 'ㄱ'): 'ㄲ'
    }

    @classmethod
    def convert_token(cls, token: str) -> str:
        normalized = "".join([ch if ch in "QWERTOP" else ch.lower() for ch in token])
        jamos = [cls.ENG_KEY_TO_JAMO.get(ch, ch) for ch in normalized]

        merged_v = []
        i = 0
        while i < len(jamos):
            if i + 1 < len(jamos) and (jamos[i], jamos[i + 1]) in cls.COMPOUND_VOWELS:
                merged_v.append(cls.COMPOUND_VOWELS[(jamos[i], jamos[i + 1])])
                i += 2
            else:
                merged_v.append(jamos[i])
                i += 1

        result = []
        idx = 0
        n = len(merged_v)
        while idx < n:
            ch = merged_v[idx]
            if ch in cls.CHOSUNG and idx + 1 < n and merged_v[idx + 1] in cls.JUNGSUNG:
                cho = cls.CHOSUNG.index(ch)
                jung = cls.JUNGSUNG.index(merged_v[idx + 1])
                jong = 0
                idx += 2

                if idx < n and merged_v[idx] in cls.JONGSUNG:
                    if idx + 1 < n and (merged_v[idx], merged_v[idx + 1]) in cls.COMPOUND_CONSONANTS:
                        if idx + 2 < n and merged_v[idx + 2] in cls.JUNGSUNG:
                            jong = cls.JONGSUNG.index(merged_v[idx])
                            idx += 1
                        else:
                            comp_c = cls.COMPOUND_CONSONANTS[(merged_v[idx], merged_v[idx + 1])]
                            jong = cls.JONGSUNG.index(comp_c)
                            idx += 2
                    elif idx + 1 < n and merged_v[idx + 1] in cls.JUNGSUNG:
                        pass
                    else:
                        jong = cls.JONGSUNG.index(merged_v[idx])
                        idx += 1

                result.append(chr(0xAC00 + (cho * 21 + jung) * 28 + jong))
            else:
                result.append(ch)
                idx += 1

        return "".join(result)


# =====================================================================
# [2] 조사 맞춤 / 구간 표시 / 선택지 만들기
# =====================================================================
def fit_josa(word: str, josa: str) -> str:
    """대체어의 받침 유무에 맞게 조사를 고른다. 표에 없는 조사(에서, 도, 만 ...)는 그대로 둔다."""
    pair = JOSA_PAIRS.get(josa)
    if not pair or not word:
        return josa
    last = word[-1]
    if not ("가" <= last <= "힣"):
        return pair[1]
    jong = (ord(last) - 0xAC00) % 28
    if pair[0] == "으로":                       # ㄹ 받침은 '로'
        return "로" if jong in (0, 8) else "으로"
    return pair[0] if jong else pair[1]


def split_josa(text: str, end: int) -> str:
    m = re.match(JOSA_RE, text[end:])
    return m.group(1) if m else ""


def build_options(text: str, span: Dict[str, Any]) -> List[Dict[str, Any]]:
    """한 구간에 대한 선택지. label은 아이가 보는 모양(조사 포함), replacement는 구간+조사를 대신할 글(None이면 지우기)."""
    josa = split_josa(text, span["end"])
    opts = []
    nxt = text[span["end"] + len(josa):].lstrip()
    for c in PII_CHOICES.get(span["kind"], []):
        words = c.split()
        if not josa and len(words) > 1 and nxt.startswith(words[-1]):
            c = " ".join(words[:-1])                        # '친구 번호' 뒤에 '번호로'가 이어지면 '친구'만 넣어 '친구 번호 번호로'를 막는다
        piece = c + (fit_josa(c, josa) if josa else "")
        opts.append({"label": piece, "replacement": piece})
    opts.append({"label": "(지우기: 이 부분을 빼요)", "replacement": None})
    return opts


def apply_choices(text: str, spans: List[Dict[str, Any]], picks: List[Dict[str, Any]]) -> str:
    """고른 결과를 반영한다. 뒤쪽 구간부터 바꿔서 앞쪽 위치가 어긋나지 않게 한다."""
    for sp, pk in sorted(zip(spans, picks), key=lambda x: -x[0]["start"]):
        josa = split_josa(text, sp["end"])
        left, rest = text[:sp["start"]], text[sp["end"] + len(josa):]
        if pk["replacement"] is None:                       # 지우기: 붙어 있던 조사도 함께 뺀다
            if left.endswith(" ") and rest.startswith(" "):
                rest = rest.lstrip(" ")
            text = left + rest
        else:
            text = left + pk["replacement"] + rest
    return re.sub(r"\s{2,}", " ", text).strip()


# =====================================================================
# [3] 규칙 전처리기 (예외가 적은 규칙만)
# =====================================================================
@dataclass
class PreprocessInspection:
    raw_input: str                                         # 입력창에 있던 글 (user_input)
    original_sentence: str = ""                            # 통과하면 나가는 글 (앞뒤 공백만 정리, 그대로)
    check_text: str = ""                                   # 규칙 확인용 (판정에만 사용)
    pii_spans: List[Dict[str, Any]] = field(default_factory=list)         # {kind, start, end, text}
    injection_spans: List[Dict[str, Any]] = field(default_factory=list)
    eng_candidate: Optional[str] = None                    # 한/영 자판 오타로 보일 때 한글로 바꾼 글
    pure_korean_char_count: int = 0
    word_count: int = 0
    is_empty_or_gibberish: bool = False
    is_numeric_only_attempt: bool = False
    is_copied_from_prev: bool = False
    too_long: bool = False
    profanity_suspected: bool = False
    passed_ignoring_pii: bool = False                      # 개인정보 구간을 짧은 낱말로 쳤을 때 나머지 규칙을 통과하는가
    passed: bool = False
    applied_rules_log: List[str] = field(default_factory=list)

    def highlights(self) -> List[Dict[str, Any]]:
        """화면용: 하이라이트할 구간(위치는 raw_input 기준)과 선택지."""
        out = []
        for sp in sorted(self.pii_spans + self.injection_spans, key=lambda s: s["start"]):
            h = dict(sp)
            h["choices"] = [o["label"] for o in build_options(self.original_sentence, sp)] if sp["kind"] in PII_CHOICES else []
            out.append(h)
        return out


class Stage1RulePreprocessor:
    def __init__(self, previous_sentences: Optional[List[str]] = None, min_chars: Optional[int] = None,
                 min_words: Optional[int] = None, max_chars: Optional[int] = None, kind: Optional[str] = None):
        # 주의: `or []`를 쓰면 빈 리스트가 새 리스트로 바뀌어 참조가 끊긴다 -> None 비교로 처리
        self.previous_sentences = previous_sentences if previous_sentences is not None else []
        # 값을 안 주면 [0] 설정 구역의 현재 값을 쓴다 (정의 시점에 굳지 않게 None으로 받는다)
        self.kind = kind                 # 글 종류 (일기/동화). 기준값은 rule(kind, 이름) 으로 읽는다
        self.min_chars = rule(kind, "MIN_HANGUL_CHARS") if min_chars is None else min_chars
        self.min_words = rule(kind, "MIN_WORDS") if min_words is None else min_words
        self.max_chars = rule(kind, "MAX_CHARS") if max_chars is None else max_chars

    # ---------- 구간 찾기 ----------
    @staticmethod
    def find_pii_spans(text: str) -> List[Dict[str, Any]]:
        found = []
        for kind, pat, grp in PII_PATTERNS:
            for m in re.finditer(pat, text):
                s, e = m.span(grp)
                found.append({"kind": kind, "start": s, "end": e, "text": text[s:e]})
        found.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
        out, last_end = [], -1
        for f in found:                                       # 겹치면 앞의 것(더 긴 것)만 둔다
            if f["start"] >= last_end:
                out.append(f)
                last_end = f["end"]
        return out

    @staticmethod
    def find_injection_spans(text: str) -> List[Dict[str, Any]]:
        """공백을 모두 떼고 좁은 패턴을 찾은 뒤, 찾은 구간을 원문 위치로 되돌린다."""
        idx_map, chars = [], []
        for i, ch in enumerate(text):
            if ch.isspace():
                continue
            lo = ch.lower()
            idx_map.append(i)
            chars.append(lo if len(lo) == 1 else ch)
        compact = "".join(chars)
        spans: List[Tuple[int, int]] = []
        for p in INJECTION_PATTERNS:
            for m in re.finditer(p, compact):
                s, e = m.span("x") if "x" in m.re.groupindex and m.group("x") is not None else m.span()
                if e > s:
                    spans.append((idx_map[s], idx_map[e - 1] + 1))
        if not spans:
            return []
        spans.sort()
        merged = [list(spans[0])]
        for s, e in spans[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return [{"kind": "인젝션", "start": s, "end": e, "text": text[s:e]} for s, e in merged]

    @staticmethod
    def _is_profanity(text: str) -> bool:
        """음절 욕설은 띄어쓰기를 유지한 채 검사하고(어절 경계를 넘는 오탐 방지), 자모가 섞인 욕설은 어절 단위로 본다.
        어느 쪽이든 쓰지 못하는 글(난타 포함)이 '욕설'로 잘못 분류돼도 결과(사용 안 함)는 같으므로 놓치지 않는 쪽을 택한다."""
        spaced = re.sub(r"[^가-힣ㄱ-ㅎㅏ-ㅣ\s]", "", text)
        if any(re.search(p, spaced) for p in PROFANITY_PATTERNS):
            return True
        edge = r"(?<![ㄱ-ㅎㅏ-ㅣ])(?:" + PROFANITY_JAMO + r")(?![ㄱ-ㅎㅏ-ㅣ])"      # 앞뒤가 자모가 아닌 곳 ('ㅈㄹ하네')
        for t in spaced.split():
            if re.search(PROFANITY_MIXED, t):
                return True
            if re.fullmatch(r"[ㄱ-ㅎ]+", t):                      # 자음만 쓴 덩어리
                hits = len(re.findall(PROFANITY_JAMO, t))
                if (len(t) <= 4 and hits) or (len(t) > 4 and (re.match(PROFANITY_JAMO, t) or re.search("(?:" + PROFANITY_JAMO + ")$", t) or hits >= 2)):
                    return True
                continue
            if re.search(edge, t):
                return True
            for a, b in zip(t, t[1:]):                               # 받침 + 이어 친 자음 ('아닛ㅂ' = ㅅㅂ)
                if "가" <= a <= "힣" and "ㄱ" <= b <= "ㅎ":
                    jong = (ord(a) - 0xAC00) % 28
                    if jong and re.fullmatch(PROFANITY_JAMO, JONG[jong] + b):
                        return True
        return False

    @staticmethod
    def _eng_candidate(curr: str, logs: List[str]) -> Optional[str]:
        """영어 비율이 높고 한글로 바꿨을 때 글자가 되면 변환 후보를 돌려준다."""
        non_space = re.sub(r"\s+", "", curr)
        eng_chars = re.findall(r"[a-zA-Z]", non_space)
        if not non_space or (len(eng_chars) / len(non_space)) < 0.4 or len(eng_chars) < 4:
            return None
        conv_tokens, conv_sylls, leftover = [], [], []
        for tok in curr.split():
            if re.search(r"[a-zA-Z]{2,}", tok):
                c_tok = EngToKorKeyboardConverter.convert_token(tok)
                conv_tokens.append(c_tok)
                conv_sylls.extend([c for c in c_tok if "가" <= c <= "힣"])
                leftover.extend(re.findall(r"[ㄱ-ㅎㅏ-ㅣ]", c_tok))
            else:
                conv_tokens.append(tok)
        if len(conv_sylls) >= 2 and len(leftover) <= 1:
            cand = " ".join(conv_tokens)
            logs.append(f"한/영 오타 의심: '{curr}' -> 한글 후보 '{cand}'")
            return cand
        return None

    # ---------- 규칙 확인용 글 만들기 + 분량 판정 ----------
    def _judge(self, probe: str, insp: PreprocessInspection, logs: List[str]) -> bool:
        curr = probe
        # 이 글 종류(일기/동화)의 기준값. 이름은 [0] 설정 구역과 같다
        SIMILARITY_LIMIT, LONG_SINGLE_WORD_CHARS = rule(self.kind, "SIMILARITY_LIMIT"), rule(self.kind, "LONG_SINGLE_WORD_CHARS")
        LOW_DIVERSITY_MIN_LEN, LOW_DIVERSITY_RATIO = rule(self.kind, "LOW_DIVERSITY_MIN_LEN"), rule(self.kind, "LOW_DIVERSITY_RATIO")
        SPACED_OUT_MIN_WORDS, SPACED_OUT_RATIO = rule(self.kind, "SPACED_OUT_MIN_WORDS"), rule(self.kind, "SPACED_OUT_RATIO")
        # [a] 분리 자모 난타 제거
        proc = []
        for token in curr.split():
            if re.fullmatch(r"([ㅋㅎㅠㅜ])\1+", token) or not re.search(r"[ㄱ-ㅎㅏ-ㅣ]", token):
                proc.append(token)
                continue
            m_tail = re.search(r"([ㅋㅎㅠㅜ]{2,}[.!?,~]*)$", token)
            core = token[:m_tail.start()] if m_tail else token
            tail = m_tail.group(1) if m_tail else ""
            jamo = re.findall(r"[ㄱ-ㅎㅏ-ㅣ]", core)
            syll = re.findall(r"[가-힣]", core)
            if not jamo:
                proc.append(core + tail)
            elif len(jamo) == 1 and len(syll) >= 2:
                fixed = re.sub(r"[ㄱ-ㅎㅏ-ㅣ]", "", core)
                logs.append(f"[확인용] 단일 오타 자모 복원: '{core}' -> '{fixed}'")
                proc.append(fixed + tail)
            else:
                logs.append(f"[확인용] 자모 혼합 난타 어절 제거: '{core}'")
                if tail:
                    proc.append(tail)
        curr = " ".join(proc).strip()

        # [b] 동일 문자/어절 반복 축약
        before = curr
        curr = re.sub(r"([가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9])\1{2,}", r"\1\1", curr)
        curr = re.sub(r"([가-힣]{2,})\1{2,}", r"\1\1", curr)
        curr = re.sub(r"(\b\S+\b)(?:\s+\1){2,}", r"\1 \1", curr)
        if before != curr:
            logs.append(f"[확인용] 반복 2회 축약: '{before}' -> '{curr}'")

        # [c] 기호 정리 (기호는 공백으로 바꿔 괄호 안 말이 앞 말에 붙지 않게 한다)
        before = curr
        curr = re.sub(r"(?<=\d)-(?=\d)", "\x00", curr)
        curr = re.sub(r"[^\w\s.!?,~\x00]", " ", curr)
        curr = re.sub(r"([.!?,~])\1{2,}", r"\1\1", curr).replace("\x00", "-")
        if not re.search(r"[가-힣a-zA-Z0-9]", curr):
            curr = ""
        curr = re.sub(r"\s{2,}", " ", curr).strip()
        if before != curr:
            logs.append(f"[확인용] 기호 정리: '{before}' -> '{curr}'")
        insp.check_text = curr

        # [d] 직전 문장과 너무 비슷하면 복붙
        sim = bool(curr) and any(difflib.SequenceMatcher(None, curr, p).ratio() >= SIMILARITY_LIMIT for p in self.previous_sentences)
        if sim:
            logs.append(f"유사도 {int(SIMILARITY_LIMIT * 100)}% 이상(복붙 감지)")

        # [e] 최소 분량
        pure_len = len(re.findall(r"[가-힣]", curr))
        words = [w for w in curr.split() if re.search(r"[가-힣]", w)]
        word_cnt = len(words)
        low_div = pure_len >= LOW_DIVERSITY_MIN_LEN and len(set(re.findall(r"[가-힣]", curr))) / pure_len <= LOW_DIVERSITY_RATIO   # '오늘오늘오늘오늘'
        if low_div:
            logs.append(f"같은 글자 반복(글자 종류 {int(LOW_DIVERSITY_RATIO * 100)}% 이하)")
        spaced_out = word_cnt >= SPACED_OUT_MIN_WORDS and len([w for w in words if len(re.findall(r"[가-힣]", w)) == 1]) / word_cnt >= SPACED_OUT_RATIO
        if spaced_out:
            logs.append(f"글자마다 띄어 쓴 글(한 글자 어절이 {int(SPACED_OUT_RATIO * 100)}% 이상)")
        # 저학년은 띄어쓰기를 안 하는 경우가 많아서, 한글이 LONG_SINGLE_WORD_CHARS자 이상이면 1어절이어도 분량 충족으로 본다
        short = low_div or spaced_out or pure_len < self.min_chars or (word_cnt < self.min_words and pure_len < LONG_SINGLE_WORD_CHARS)
        logs.append(f"분량 {'미달' if short else '충족'}: 한글 {pure_len}자(기준 {self.min_chars}), {word_cnt}어절(기준 {self.min_words})")
        insp.pure_korean_char_count, insp.word_count = pure_len, word_cnt
        insp.is_empty_or_gibberish = pure_len <= 1
        insp.is_copied_from_prev = sim
        return not short and not sim

    # ---------- 본체 ----------
    def inspect_and_clean(self, raw_text: str, check_eng: bool = True) -> PreprocessInspection:
        logs: List[str] = []
        curr = raw_text.strip()
        insp = PreprocessInspection(raw_input=raw_text, original_sentence=curr, applied_rules_log=logs)

        if re.fullmatch(r"\d+", curr):
            insp.is_numeric_only_attempt = True
            logs.append("숫자단독입력: 작문 단계에서는 번호 선택 불가(직접 글자 작성 필요)")
            return insp
        if len(curr) > self.max_chars:
            insp.too_long = True
            logs.append(f"{self.max_chars}자 초과({len(curr)}자): 자르지 않고 되묻기")
            return insp

        # 한/영 자판 오타 후보 (선택지로 확인하므로 여기서 멈춘다)
        if check_eng:
            insp.eng_candidate = self._eng_candidate(curr, logs)
            if insp.eng_candidate:
                return insp

        # 욕설/비속어: 이 입력은 사용하지 않는다
        if self._is_profanity(curr):
            insp.profanity_suspected = True
            logs.append("욕설/비속어 의심: 이 입력은 사용하지 않음")
            return insp

        # 인젝션/개인정보 구간 (위치는 curr 기준)
        insp.injection_spans = self.find_injection_spans(curr)
        insp.pii_spans = self.find_pii_spans(curr)
        if insp.injection_spans:
            logs.append("인젝션 의심 구간: " + ", ".join(f"'{s['text']}'" for s in insp.injection_spans))
        if insp.pii_spans:
            logs.append("개인정보 구간: " + ", ".join(f"{s['kind']}'{s['text']}'" for s in insp.pii_spans))

        # 판정용 글: 개인정보 구간은 2글자 낱말로 쳐서 '나머지 문제'만 본다 (고른 뒤 길이가 모자라지 않도록 보수적으로)
        probe = curr
        for sp in sorted(insp.pii_spans, key=lambda s: -s["start"]):
            probe = probe[:sp["start"]] + "학교" + probe[sp["end"]:]
        basic = self._judge(probe, insp, logs)
        insp.passed_ignoring_pii = basic
        insp.passed = basic and not insp.pii_spans and not insp.injection_spans
        return insp


# =====================================================================
# [4] 되묻기 문구 (규칙으로 정하는 문구. 입력 종류에 따라 다르게 나간다)
# =====================================================================
def next_question(insp: PreprocessInspection, kind: Optional[str] = None) -> str:
    if insp.profanity_suspected:
        return say(kind, "profanity", "예쁜 말로 바꿔서 오늘 있었던 일을 한 문장으로 적어볼까요?")
    if insp.too_long:
        return f"글이 {rule(kind, 'MAX_CHARS')}자를 넘었어요. 조금 짧게 나눠서 적어볼까요?"
    if insp.injection_spans:
        quote = insp.injection_spans[0]["text"]
        quote = quote if len(quote) <= 20 else quote[:20] + "…"
        return f"표시된 '{quote}' 부분을 요정이 잘 못 알아들었어요. 이 부분을 다른 말로 바꿔서 다시 적어볼까요?"
    if insp.pii_spans:
        kinds = ", ".join(dict.fromkeys(PII_LABEL[s["kind"]] for s in insp.pii_spans))
        return say(kind, "pii", "개인정보({kinds})는 일기에 쓰지 않아요. 표시된 부분을 빼거나 다른 말로 바꿔서 다시 적어볼까요?").format(kinds=kinds)
    if insp.is_copied_from_prev:
        return say(kind, "copied", "방금 쓴 문장과 아주 비슷해요. 그다음에는 어떤 일이 있었는지 적어볼까요?")
    text = insp.original_sentence
    if not insp.check_text:
        return say(kind, "nothing", "오늘 떠오르는 장면이 있나요? 누구와 무엇을 했는지 한 문장으로 편하게 적어볼까요?")
    if len(text) <= 12 and re.fullmatch(r"[가-힣 ]+", text):
        return say(kind, "more_about", "'{text}'에 대해 조금 더 적어볼까요? 누구와, 무엇을 했는지 한 문장으로 써보세요.").format(text=text)
    return say(kind, "default", "그때 어떤 일이 있었고 기분은 어땠는지 한 문장으로 적어볼까요?")


# =====================================================================
# [5] 노드 인터페이스 (LangGraph State / 노드 / 분기)
# =====================================================================
class ValidationState(TypedDict, total=False):
    """유효성 검사 노드가 읽고 쓰는 State 키. 팀 공용 State에 이 키들을 그대로 합치면 된다.

    ── 데이터 명세(엑셀)에 있는 키 ──────────────────────────────
    user_input         : 사용자가 적은 원본 문장 (입력)
    original_sentence  : 통과한 원문 문장 (출력). 통과하지 못하면 ""

    ── 노드 동작에 필요해서 추가한 키 (명세에 없음. 팀원과 합의 필요) ──
    is_valid           : 통과 여부. 분기(route_after_validation)가 이 값을 본다
    retry_message      : 불통과일 때 '다시 입력 안내'에 띄울 문구
    highlights         : 화면에 표시할 구간 [{kind,start,end,text,choices}]. 위치는 display_text 기준
    display_text       : highlights가 가리키는 글 (user_input을 다듬은 것, 한/영 선택 후에는 선택 결과)
    awaiting_choice    : True면 '선택지 팝업'을 띄우고, 아이가 고른 번호(0부터)를 choice_picks에 담아 다시 호출
    line_skipped       : True면 3번 안에 못 써서 이 줄을 건너뜀
    validation_attempt : 이 문장에 쓴 입력 횟수 (통과/건너뜀이면 0으로 초기화). 선택지 고르기는 세지 않는다
    previous_sentences : 이미 통과한 문장들 (직전 문장 복붙 비교용). 통과할 때마다 하나씩 늘어난다
    choice_picks       : 선택지에서 고른 번호 목록 (입력용. 노드가 쓰고 나면 []로 비운다)
    validation_log     : 어떤 규칙이 작동했는지 (확인용)
    kind               : 글 종류 "diary"(일기, 기본) / "fairy"(동화). 종류별 기준은 [0]의 KIND_RULES (입력용, 없어도 된다)
    """
    user_input: str
    original_sentence: str
    is_valid: bool
    retry_message: str
    highlights: list[dict]
    display_text: str
    awaiting_choice: bool
    line_skipped: bool
    validation_attempt: int
    previous_sentences: list[str]
    choice_picks: list[int]
    validation_log: list[str]
    kind: str


def _result(**kw) -> Dict[str, Any]:
    """노드가 돌려주는 값의 기본형. 이전 호출의 값이 남지 않도록 매번 모든 출력 키를 채운다."""
    base = {"is_valid": False, "original_sentence": "", "retry_message": "", "highlights": [], "display_text": "",
            "awaiting_choice": False, "line_skipped": False, "choice_picks": [], "validation_log": []}
    base.update(kw)
    return base


def _judge_attempt(insp: PreprocessInspection, sn: int, allow_choice: bool = True) -> str:
    """'pass' | 'choose'(개인정보 선택지) | 'retry'. sn은 이번 입력이 몇 번째인지(1부터)."""
    if insp.profanity_suspected or insp.too_long or insp.injection_spans or insp.is_empty_or_gibberish:
        return "retry"
    if insp.pii_spans:
        if allow_choice and sn >= PII_CHOICE_FROM_ATTEMPT and insp.passed_ignoring_pii:
            return "choose"
        return "retry"
    return "pass" if insp.passed else "retry"


def _valid_picks(picks: List[Any], sizes: List[int]) -> bool:
    return len(picks) >= len(sizes) and all(isinstance(p, int) and not isinstance(p, bool) and 0 <= p < n
                                            for p, n in zip(picks, sizes))


def validate_sentence(user_input: str, validation_attempt: int = 0, previous_sentences: Optional[List[str]] = None,
                      choice_picks: Optional[List[int]] = None, kind: Optional[str] = None) -> Dict[str, Any]:
    """유효성 검사 1회. 전달받은 값을 바꾸지 않고, 노드가 새로 만든 State 키만 dict로 돌려준다.
    kind 는 글 종류("diary"/"fairy"). 안 주거나 모르는 종류면 일기 기준으로 검사한다."""
    kind = kind if kind in KIND_RULES else DEFAULT_KIND
    max_steps = rule(kind, "MAX_STEPS")
    used = max(0, int(validation_attempt or 0))
    sn = used + 1                                            # 이번 입력이 몇 번째인지
    prev = list(previous_sentences or [])
    picks = list(choice_picks or [])
    text = (user_input or "").strip()
    log: List[str] = []

    # 복붙 비교용: 이미 통과한 문장들의 '규칙 확인용 글'
    cleaner = Stage1RulePreprocessor(kind=kind)
    pre = Stage1RulePreprocessor(previous_sentences=[cleaner.inspect_and_clean(p, check_eng=False).check_text for p in prev], kind=kind)

    if not text:
        return _result(retry_message=say(kind, "empty", "글이 비어 있어요. 오늘 있었던 일을 한 문장으로 적어볼까요?"), validation_attempt=used,
                       validation_log=["빈 입력: 횟수에 포함 안 됨"])
    insp = pre.inspect_and_clean(text)
    if insp.is_numeric_only_attempt:
        return _result(retry_message=say(kind, "numeric", "숫자만으로는 일기를 쓸 수 없어요. 한글로 직접 적어볼까요?"), display_text=text,
                       validation_attempt=used, validation_log=insp.applied_rules_log + ["횟수에 포함 안 됨"])

    # ── 한/영 자판 오타 선택 (횟수에 안 센다) ──
    if insp.eng_candidate:
        cand = insp.eng_candidate
        if not picks or not _valid_picks(picks[:1], [2]):
            msg = "한/영 키가 눌린 것 같아요. 어느 쪽이 맞나요?" if not picks else "1번이나 2번 중에서 골라주세요."
            hl = [{"kind": "한영변환", "start": 0, "end": len(text), "text": text,
                   "choices": [f"한글로 바꾼 글: {cand}", f"영어 그대로: {text}"]}]
            return _result(retry_message=msg, highlights=hl, display_text=text, awaiting_choice=True,
                           validation_attempt=used, validation_log=insp.applied_rules_log)
        pk = picks.pop(0)
        log.append(f"한/영 선택: {'한글로 바꾼 글' if pk == 0 else '영어 그대로'}")
        if pk == 0:
            text = cand
        insp = pre.inspect_and_clean(text, check_eng=False)

    verdict = _judge_attempt(insp, sn)

    # ── 개인정보 선택지 (개인정보 말고는 문제가 없을 때) ──
    if verdict == "choose":
        spans = sorted(insp.pii_spans, key=lambda s: s["start"])
        opts = [build_options(insp.original_sentence, sp) for sp in spans]
        if not _valid_picks(picks, [len(o) for o in opts]):
            hl = []
            for sp, o in zip(spans, opts):
                h = dict(sp)
                h["choices"] = [x["label"] for x in o]
                hl.append(h)
            msg = say(kind, "pii_choice", "표시된 부분은 개인정보라서 일기에 쓰지 않아요. 어떤 말로 바꿀까요?") if not picks else "번호를 다시 골라주세요."
            return _result(retry_message=msg, highlights=hl, display_text=insp.original_sentence, awaiting_choice=True,
                           validation_attempt=used, validation_log=log + insp.applied_rules_log)
        chosen = [o[p] for o, p in zip(opts, picks)]
        log.append("개인정보 선택: " + ", ".join(f"'{sp['text']}' -> '{c['label']}'" for sp, c in zip(spans, chosen)))
        new_text = apply_choices(insp.original_sentence, spans, chosen)
        insp = pre.inspect_and_clean(new_text, check_eng=False)           # 바뀐 문장을 규칙으로 한 번 더 검사
        verdict = _judge_attempt(insp, sn, allow_choice=False)

    log += insp.applied_rules_log

    # ── 통과 ──
    if verdict == "pass":
        return _result(is_valid=True, original_sentence=insp.original_sentence, display_text=insp.original_sentence,
                       validation_attempt=0, previous_sentences=prev + [insp.original_sentence], validation_log=log)

    # ── 불통과 ──
    highlights = [dict(h, choices=[]) for h in insp.highlights()]
    if sn >= max_steps:                                                    # 3번째도 못 넘으면 이 줄은 건너뜀
        extra = "예쁜 말로 적어주면 좋겠어요. " if insp.profanity_suspected else ""
        return _result(line_skipped=True, retry_message=f"{extra}괜찮아요, 이 줄은 저장하지 않았어요. 다시 써볼까요?",
                       highlights=highlights, display_text=insp.original_sentence, validation_attempt=0, validation_log=log)
    q = next_question(insp, kind)
    if sn + 1 == max_steps:
        q = "마지막이에요! " + q
    return _result(retry_message=q, highlights=highlights, display_text=insp.original_sentence, validation_attempt=sn,
                   validation_log=log)


def validate_node(state: ValidationState) -> Dict[str, Any]:
    """LangGraph 노드: State를 받아 바뀐 키만 돌려준다."""
    return validate_sentence(state.get("user_input", ""), state.get("validation_attempt", 0),
                             state.get("previous_sentences"), state.get("choice_picks"), state.get("kind"))


def route_after_validation(state: ValidationState) -> Literal["correction", "retry", "skipped"]:
    """조건부 간선. 통과 -> 문장 교정 / 불통과 -> 다시 입력 안내 / 3번 실패 -> 이 줄 건너뜀."""
    if state.get("is_valid"):
        return "correction"
    if state.get("line_skipped"):
        return "skipped"
    return "retry"


def build_graph(correction_node=None, state_schema=ValidationState):
    """langgraph가 설치돼 있을 때 '유효성 검사 -> (통과) 문장 교정' 그래프를 만든다.
    '문장 쓰기'는 그래프 밖(화면/API)이다: 제출할 때마다 graph.invoke(state)를 부르고, retry/skipped는 END로 나가 화면에 안내를 띄운다.
    correction_node가 없으면 통과 시 바로 END. 팀 공용 State를 쓰려면 state_schema로 넘긴다."""
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError as e:                                               # pragma: no cover
        raise RuntimeError("langgraph가 설치돼 있지 않습니다 (pip install langgraph)") from e
    g = StateGraph(state_schema)
    g.add_node("validate", validate_node)
    g.add_edge(START, "validate")
    if correction_node is not None:
        g.add_node("correction", correction_node)
        g.add_edge("correction", END)
        g.add_conditional_edges("validate", route_after_validation, {"correction": "correction", "retry": END, "skipped": END})
    else:
        g.add_conditional_edges("validate", route_after_validation, {"correction": END, "retry": END, "skipped": END})
    return g.compile()