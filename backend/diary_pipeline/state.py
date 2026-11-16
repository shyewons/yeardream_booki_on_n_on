# -*- coding: utf-8 -*-
"""그래프 전체가 쓰는 State 정의. 노드끼리는 이 키들로만 값을 주고받는다.
노드 파일 안의 코드나 모델을 바꿔도, 아래 키 이름과 타입만 지키면 다른 노드에는 영향이 없다."""
from typing import TypedDict

from .input_validation import ValidationState


class DiffItem(TypedDict):        # difference 변수의 항목 (difflib으로 추출한 차이 1건)
    before: str                   # 원래 표현 (원문에서 바뀌기 전, 어절 단위)
    after: str                    # 고친 표현 (교정 문장에서 바뀐 뒤, 어절 단위)
    start: int                    # 원문 속 시작 위치 (0부터 셈)
    end: int                      # 원문 속 끝 위치 (이 위치 글자는 포함하지 않음)


class EvidenceDoc(TypedDict):     # evidence_docs 변수의 항목 (쿼리 1개당 근거 문서)
    doc_id: str                   # 청크 번호 (예: 한글 맞춤법-제35항-0132)
    content: str                  # 근거 문서 본문 (청크 내용)
    score: float                  # 쿼리와의 코사인 유사도
    article: str                  # 청크가 속한 조항 (예: 제35항)
    page: int                     # PDF 쪽 번호


class DiaryState(TypedDict, total=False):
    original_sentence: str                 # 원문 문장 (유효성 검사를 통과한 아이 문장)
    revised_sentence: str                  # 교정 문장 (① spell_correct)
    difference: list[DiffItem]             # 바뀐 부분 (② extract_diff)
    rewritten_queries: list[str]           # 재작성 쿼리 (③ rewrite_queries, difference 1건마다 1개)
    evidence_docs: list[EvidenceDoc]       # 근거 문서 (④ retrieve_evidence, 쿼리 1개마다 1개)
    explanations: list[str]                # 아이용 설명문 (⑤ explain, difference 1건마다 1개)
    compliment: str                        # 칭찬 안내문 (고칠 곳이 없을 때)
    response: dict                         # 백엔드로 넘길 최종 결과 (build_response, JSON으로 바꿀 수 있는 dict)


class PipelineState(ValidationState, DiaryState, total=False):
    """유효성 검사 키(input_validation.ValidationState) + 교정 단계 키(DiaryState)."""
