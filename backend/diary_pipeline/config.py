# -*- coding: utf-8 -*-
"""설정 모음. 모델을 바꿀 때는 대부분 이 파일의 이름 한 줄만 고치면 된다."""
import os

# ① 맞춤법 교정 모델 (seq2seq)
SPELL_MODEL_ID = "j5ng/et5-typos-corrector"
SPELL_PROMPT_PREFIX = "맞춤법을 고쳐주세요: "          # et5 모델 카드의 입력 형식

# ③ 쿼리 재작성 / ⑤ 설명문 LLM (같은 이름이면 한 번만 불러와 함께 씀, 다르게 적으면 따로 불러옴)
QUERY_LLM_ID = "kakaocorp/kanana-1.5-2.1b-instruct-2505"
EXPLAIN_LLM_ID = "kakaocorp/kanana-1.5-2.1b-instruct-2505"

# ④ 임베딩 모델 (벡터 DB를 만들 때와 검색할 때 반드시 같은 모델)
EMBED_MODEL_ID = "BAAI/bge-m3"

# 벡터 DB
DB_PATH = os.environ.get("DIARY_DB_PATH", "chroma_db")
COLLECTION = "spelling_rules"
TOP_K = 1                       # 쿼리 1개당 가져올 근거 문서 수 (지금은 Top1)

# ② diff 추출
IGNORE_PUNCT_ONLY = True        # 문장부호만 바뀐 수정(예: et5가 끝에 붙인 마침표)은 교정으로 보지 않음

# 칭찬 (고칠 곳이 없을 때)
COMPLIMENT = "맞춤법을 올바르게 썼네요, 참 잘했어요!"
