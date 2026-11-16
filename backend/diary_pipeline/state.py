# -*- coding: utf-8 -*-
"""그래프 전체가 쓰는 State 정의. 노드끼리는 이 키들로만 값을 주고받는다 (키 이름·타입만 지키면 노드 안은 자유롭게 바꿔도 된다)."""
from typing import TypedDict

from .input_validation import ValidationState


class DiffItem(TypedDict):        # difference 의 항목 (바뀐 곳 1건, 어절 단위)
    before: str                   # 원래 표현
    after: str                    # 고친 표현
    start: int                    # 원문 속 시작 위치 (0부터)
    end: int                      # 원문 속 끝 위치 (이 위치 글자는 포함하지 않음)


class EvidenceDoc(TypedDict, total=False):   # 근거 문서 (청크 1개)
    doc_id: str                   # 청크 번호 (예: 한글 맞춤법-제35항-0132)
    content: str                  # 청크 본문
    score: float                  # 쿼리와의 코사인 유사도 (규칙으로 붙인 제2항은 None)
    part: str                     # 구간 (한글 맞춤법 / 표준어 사정 원칙)
    article: str                  # 조항 (예: 제35항)
    page: int                     # PDF 쪽 번호
    source: str                   # "검색" 또는 "규칙"


class DiaryState(TypedDict, total=False):
    original_sentence: str                   # 유효성 검사를 통과한 원문
    revised_sentence: str                    # ① 교정 문장
    difference: list[DiffItem]               # ② 바뀐 곳
    rewritten_queries: list[str]             # ③ 검색 쿼리 (difference 1건마다 1개)
    query_types: list[str]                   # ③ 판정 유형: ①표기만 / ②띄어쓰기+구체 / ③띄어쓰기+표기 / ④일반 띄어쓰기
    evidence_docs: list[EvidenceDoc]         # ④ 대표 근거 (쿼리 1개마다 1개, ⑤가 사용)
    evidence_lists: list[list[EvidenceDoc]]  # ④ 최종 근거 전체 (쿼리 1개마다 최대 3개)
    explanations: list[str]                  # ⑤ 설명문 (difference 1건마다 1개)
    compliment: str                          # 고칠 곳이 없을 때 칭찬
    response: dict                           # 백엔드로 넘길 최종 결과


class PipelineState(ValidationState, DiaryState, total=False):
    """유효성 검사 키 + 교정 단계 키."""
