# -*- coding: utf-8 -*-
"""설정 모음. 모델·DB·규칙 값을 바꿀 때는 이 파일만 고친다."""
import os

# ① 맞춤법 교정 (et5, seq2seq)
SPELL_MODEL_ID = "j5ng/et5-typos-corrector"
SPELL_PROMPT_PREFIX = "맞춤법을 고쳐주세요: "          # et5 모델 카드의 입력 형식
IGNORE_PUNCT_ONLY = True                               # ② 문장부호만 바뀐 수정(예: et5가 끝에 붙인 마침표)은 교정으로 보지 않음
COMPLIMENT = "맞춤법을 올바르게 썼네요, 참 잘했어요!"     # 고칠 곳이 없을 때

# ④ 근거 검색 (벡터 DB를 만들 때와 검색할 때 반드시 같은 임베딩 모델)
EMBED_MODEL_ID = "nlpai-lab/KURE-v1"
SEM_SPLIT_MODEL_ID = "BAAI/bge-m3"                     # 벡터 DB 만들 때 semantic 청킹의 문장 유사도에만 사용
DB_PATH = os.environ.get("DIARY_DB_PATH", "chroma_db")
COLLECTION = "spelling_rules_kure_std"                 # 검색 방식이 바뀌었으므로 예전 DB와 다른 이름
RAG_PARTS = ("한글 맞춤법", "표준어 사정 원칙")          # 벡터 DB에 넣을 구간 (두 구간 모두 같은 조항 번호가 있어 (구간, 조항)으로 구별)
TOP_K = 10                                             # 쿼리 1개당 검색할 청크 수 (근거 후보)
EVIDENCE_MAX = 3                                       # 수정 1건당 최종 근거 조항 수 (최대)
RULE_PART, RULE_ARTICLE = "한글 맞춤법", "제2항"         # 띄어쓰기 판정이면 규칙으로 붙이는 조항 (띄어쓰기 대원칙)

# 구조+semantic 청킹: 조항 경계로 나눈 뒤, 조항 안에서 이웃 문장 유사도가 하위 SEM_PCT%(구간마다 따로 계산)인 곳에서 자름
SEM_PCT, SEM_MIN, SEM_MAX = 10, 200, 800               # 하위 몇 %, 청크 최소·최대 글자 수

# ⑤ 설명문 LLM
EXPLAIN_LLM_ID = "kakaocorp/kanana-1.5-2.1b-instruct-2505"
