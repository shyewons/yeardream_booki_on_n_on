# -*- coding: utf-8 -*-
"""④ 근거 검색 (KURE 임베딩 + 벡터 검색 + 근거 결정기).
읽는 키: rewritten_queries, query_types  →  쓰는 키: evidence_docs, evidence_lists
쿼리마다 벡터 검색으로 청크 TOP_K(10)개를 찾고, 판정 유형에 따라 최종 근거 조항(최대 3개)을 고른다.
  ① 표기만             → 검색 상위 3개
  ② 띄어쓰기+구체 범주  → [제2항] + 검색 상위 2개 (제2항 제외)
  ③ 띄어쓰기+표기       → [제2항] + 검색 상위 2개 (제2항 제외)
  ④ 일반 띄어쓰기       → [제2항]만 (검색 결과 안 씀)
evidence_lists[i] = 최종 근거 전체(같은 조항은 한 번만), evidence_docs[i] = 그중 대표 1개(⑤ 설명문이 사용).
대표는 검색으로 찾은 첫 조항, 없으면(④) 제2항.
한글 맞춤법과 표준어 사정 원칙에 같은 조항 번호(제2항 등)가 있어, 조항은 (구간, 조항)으로 비교한다.
검색 방식을 바꿀 때는 이 파일만, 임베딩 모델은 config.EMBED_MODEL_ID, 벡터 DB 종류는 vector_db.py 를 바꾼다."""
from . import config, vector_db
from . import query as q
from .models import embed, load_embedder


def resolve_evidence(kind: str, rag_labels: list[tuple]) -> list[tuple]:
    """판정 유형 + 검색 결과((구간, 조항), 순위순) → 최종 근거 (구간, 조항) 목록 (평가 노트북과 같은 규칙)."""
    rag, rule, n = rag_labels or [], (config.RULE_PART, config.RULE_ARTICLE), config.EVIDENCE_MAX
    if kind == q.TYPE_SPELLING:
        return rag[:n]
    if kind == q.TYPE_SPACE_GENERAL:
        return [rule]
    return [rule] + [l for l in rag if l != rule][:n - 1]


def retrieve_evidence(state: dict) -> dict:
    queries = state["rewritten_queries"]
    kinds = state.get("query_types") or [q.TYPE_SPELLING] * len(queries)    # 판정이 없으면 검색 결과만 사용
    vectors = embed(config.EMBED_MODEL_ID, queries)
    hits = vector_db.search(vectors, k=config.TOP_K)

    docs, lists = [], []
    for kind, hs in zip(kinds, hits):
        chosen = []
        labels = [(h["part"], h["article"]) for h in hs]
        for lab in dict.fromkeys(resolve_evidence(kind, labels)):                       # 같은 조항은 한 번만
            if lab == (config.RULE_PART, config.RULE_ARTICLE) and kind != q.TYPE_SPELLING:
                chosen.append({**vector_db.get_article_doc(config.RULE_ARTICLE, config.RULE_PART), "source": "규칙"})
            else:
                chosen.append({**next(h for h in hs if (h["part"], h["article"]) == lab), "source": "검색"})   # 그 조항에서 가장 높은 청크
        if not chosen:                                   # 검색 결과가 하나도 없을 때(빈 DB 등) ⑤가 멈추지 않도록 제2항으로 대신
            chosen = [{**vector_db.get_article_doc(config.RULE_ARTICLE, config.RULE_PART), "source": "규칙"}]
        lists.append(chosen)
        docs.append(next((c for c in chosen if c["source"] == "검색"), chosen[0]))
    return {"evidence_docs": docs, "evidence_lists": lists}


def preload():
    load_embedder(config.EMBED_MODEL_ID)
    vector_db.get_collection()
