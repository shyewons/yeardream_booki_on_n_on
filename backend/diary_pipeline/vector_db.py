# -*- coding: utf-8 -*-
"""근거 문서(해설서 PDF) → 청킹 → 벡터 DB(Chroma) 만들기와 검색.
처음 한 번 실행:  python -m diary_pipeline.vector_db "한글맞춤법 표준어규정 해설.pdf" [--db chroma_db]

  load_parts()            PDF 읽기 (머리말·쪽 번호 정리, 쪽·조항 위치)      ← 다른 문서를 쓰면 여기
  chunk_struct_semantic() 구조+semantic 청킹 (조항 경계 + 의미 경계)        ← 청킹 방식을 바꾸면 여기
  build_vector_db() / search() / get_article_doc()                         ← 다른 벡터 DB로 바꾸면 여기 (돌려주는 형식만 지키면 됨)"""
import bisect
import re

from . import config
from .models import embed

# 벡터 DB에 넣을 구간 (PDF 쪽 번호, 양 끝 포함). 표지·머리말·차례·간지는 뺌
PARTS = {
    "한글 맞춤법": (13, 146),
    "표준어 사정 원칙": (151, 214),
    # "표준 발음법": (215, 264),     # 맞춤법 교정과 거리가 있어 기본으로 제외
}

# 매 쪽 위의 머리말과 쪽 번호 줄
HEADER = re.compile(r"^(‘한글 맞춤법’, ‘표준어 규정’ 해설|Ⅰ\. ‘한글 맞춤법’ 해설\s*\d*|Ⅱ\. ‘표준어 규정’ 해설\s*\d*|\d+)$")
ARTICLE = re.compile(r"^제\s*(\d+)\s*항$")          # 조항 제목 줄 (예: '제35항')


def load_parts(pdf_path: str) -> list[dict]:
    """구간마다 {name, text, page_at[(시작 위치, 쪽)], articles[(시작 위치, 조항 번호)]} 를 돌려준다."""
    import pymupdf  # PDF 읽기 (예전 이름: fitz)
    doc = pymupdf.open(pdf_path)
    parts = []
    for name, (first, last) in PARTS.items():
        text, page_at, articles = "", [], []
        for pno in range(first, last + 1):
            page_at.append((len(text), pno))
            for line in doc[pno - 1].get_text().splitlines():
                s = line.strip()
                if not s or HEADER.match(s):
                    continue
                m = ARTICLE.match(s)
                if m:
                    articles.append((len(text), int(m.group(1))))
                text += s + "\n"
        parts.append({"name": name, "text": text, "page_at": page_at, "articles": articles})
    return parts


# ---------------------------------------------------------------------------
# 구조+semantic 청킹
#   1) 조항 경계로 먼저 나눈다 (청크마다 조항이 하나로 정해짐)
#   2) 조항 안을 문장으로 나누고, 이웃 문장끼리 임베딩 유사도를 잰다
#   3) 유사도가 하위 SEM_PCT% 이하인 곳(내용이 바뀌는 곳)에서 자른다. 청크는 SEM_MIN~SEM_MAX 글자
#      하위 SEM_PCT% 기준(커트라인)은 구간마다 그 구간의 이웃 쌍만으로 따로 계산한다
#      (구간을 섞으면 표준어 사정 원칙을 넣었을 때 한글 맞춤법 청크의 경계까지 달라지기 때문)
#   PDF는 한 문장이 여러 줄로 꺾여 있어, 문장 끝(. ! ?)이나 목록 기호(• ① 등)로 시작하는 줄에서만 문장을 나눈다.
# ---------------------------------------------------------------------------
_SENT_END = re.compile(r"(?<=[.!?。”’])\s+|\n(?=\s*[•※①-⑳㉠-㉭\-\d(])")


def _article_spans(p: dict) -> list[tuple]:
    """구간 글을 조항 경계로 나눈 (시작, 끝, 조항 이름). 첫 조항 앞부분은 '총칙'."""
    spans, arts = [], p["articles"]
    if arts and arts[0][0] > 0:
        spans.append((0, arts[0][0], "총칙"))
    for k, (a_start, num) in enumerate(arts):
        a_end = arts[k + 1][0] if k + 1 < len(arts) else len(p["text"])
        spans.append((a_start, a_end, f"제{num}항"))
    return spans


def _sentences(text: str, start: int, end: int) -> list[tuple]:
    """[start, end) 를 문장으로 나눈 (시작, 끝) 위치 목록 (구간 글 기준 위치)."""
    out, s = [], start
    for m in _SENT_END.finditer(text, start, end):
        if text[s:m.start()].strip():
            out.append((s, m.start()))
        s = m.end()
    if text[s:end].strip():
        out.append((s, end))
    return out


def chunk_struct_semantic(parts: list[dict], embed_fn=None, pct: int = None, mn: int = None, mx: int = None) -> list[dict]:
    """조항 경계 + 의미 경계로 자른 청크. embed_fn(texts) → 정규화된 벡터 (기본: config.SEM_SPLIT_MODEL_ID)."""
    import numpy as np
    if embed_fn is None:
        embed_fn = lambda texts: embed(config.SEM_SPLIT_MODEL_ID, texts)
    pct = config.SEM_PCT if pct is None else pct
    mn = config.SEM_MIN if mn is None else mn
    mx = config.SEM_MAX if mx is None else mx

    # 1) 조항마다 문장과 이웃 문장 유사도
    per_art = []                                   # (구간, 조항, [(문장 시작, 끝)], 유사도 배열)
    for p in parts:
        for a_start, a_end, article in _article_spans(p):
            sents = _sentences(p["text"], a_start, a_end)
            if len(sents) >= 2:
                E = np.asarray(embed_fn([p["text"][s:e] for s, e in sents]), dtype=np.float32)
                sim = (E[:-1] * E[1:]).sum(1)
            else:
                sim = np.array([])
            per_art.append((p, article, sents, sim))
    thr = {}                                       # 구간 이름 → 그 구간 이웃 쌍 중 하위 pct%
    for p in parts:
        sims = [s for q, _, _, s in per_art if q is p and len(s)]
        thr[p["name"]] = np.percentile(np.concatenate(sims), pct) if sims else -1.0

    # 2) 조항 안에서 자르기
    chunks = []

    def add(p, article, s, e):
        page_pos = [pos for pos, _ in p["page_at"]]
        page = p["page_at"][bisect.bisect_right(page_pos, s) - 1][1]
        chunks.append({"doc_id": f"{p['name']}-{article}-{len(chunks):04d}", "content": p["text"][s:e].strip(),
                       "part": p["name"], "article": article, "page": page})

    for p, article, sents, sim in per_art:
        cur_s = cur_e = None
        for i, (s, e) in enumerate(sents):
            while e - s > mx:                                   # 한 문장이 최대 길이보다 길면 잘라서 따로
                if cur_s is not None:
                    add(p, article, cur_s, cur_e); cur_s = None
                add(p, article, s, s + mx); s += mx
            if cur_s is not None and e - cur_s > mx:            # 이 문장을 더하면 너무 길어지면 먼저 끊음
                add(p, article, cur_s, cur_e); cur_s = None
            cur_s = s if cur_s is None else cur_s
            cur_e = e
            if i < len(sim) and sim[i] <= thr[p["name"]] and cur_e - cur_s >= mn:   # 내용이 바뀌는 곳 + 최소 길이 이상
                add(p, article, cur_s, cur_e); cur_s = None
        if cur_s is not None:                                   # 조항 끝에 남은 짧은 조각은 같은 조항의 앞 청크에 붙임
            last = chunks[-1] if chunks else None
            if (last and last["article"] == article and last["part"] == p["name"] and cur_e - cur_s < mn
                    and len(last["content"]) + (cur_e - cur_s) + 1 <= mx):
                last["content"] = (last["content"] + "\n" + p["text"][cur_s:cur_e].strip()).strip()
            else:
                add(p, article, cur_s, cur_e)
    return chunks


# ---------------------------------------------------------------------------
# 벡터 DB (Chroma)
# ---------------------------------------------------------------------------
_collection = {}


def build_vector_db(pdf_path: str, db_path: str = None) -> int:
    """PDF → 청킹 → 임베딩 → Chroma 저장. 저장한 청크 수를 돌려준다."""
    import chromadb
    db_path = db_path or config.DB_PATH
    parts = [p for p in load_parts(pdf_path) if p["name"] in config.RAG_PARTS]
    for p in parts:
        nums = [n for _, n in p["articles"]]
        print(f"{p['name']}: {len(p['text']):,}자, 조항 제{nums[0]}~{nums[-1]}항 ({len(nums)}개)")
    chunks = chunk_struct_semantic(parts)
    print(f"청크 {len(chunks)}개 (평균 {sum(len(c['content']) for c in chunks) / len(chunks):.0f}자)")

    vectors = embed(config.EMBED_MODEL_ID, [c["content"] for c in chunks], show_progress=True)
    client = chromadb.PersistentClient(path=db_path)
    if config.COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(config.COLLECTION)               # 다시 실행하면 새로 만듦
    col = client.create_collection(config.COLLECTION, configuration={"hnsw": {"space": "cosine"}})
    col.add(
        ids=[c["doc_id"] for c in chunks],
        embeddings=vectors.tolist(),
        documents=[c["content"] for c in chunks],
        metadatas=[{"part": c["part"], "article": c["article"], "page": c["page"]} for c in chunks],
    )
    _collection.clear()
    print(f"저장 완료: {col.count()}개 청크 → {db_path}")
    return col.count()


def get_collection():
    """저장된 Chroma 컬렉션을 한 번만 연다."""
    if "col" not in _collection:
        import chromadb
        client = chromadb.PersistentClient(path=config.DB_PATH)
        if config.COLLECTION not in [c.name for c in client.list_collections()]:     # 예전 DB만 있을 때 알아보기 쉽게
            raise RuntimeError(f"벡터 DB에 '{config.COLLECTION}' 컬렉션이 없습니다. 검색 방식이 바뀌었으니 다시 만드세요: "
                               f"python -m diary_pipeline.vector_db \"한글맞춤법 표준어규정 해설.pdf\"")
        _collection["col"] = client.get_collection(config.COLLECTION)
    return _collection["col"]


def get_article_doc(article: str, part: str = "한글 맞춤법") -> dict:
    """조항의 첫 청크를 검색 없이 가져온다 (판정 규칙으로 붙이는 제2항용). 형식은 search() 의 항목과 같다."""
    if ("art", part, article) not in _collection:
        res = get_collection().get(where={"$and": [{"article": article}, {"part": part}]},
                                   include=["documents", "metadatas"])
        if not res["ids"]:
            raise RuntimeError(f"벡터 DB에 {part} {article} 청크가 없습니다.")
        k = min(range(len(res["ids"])), key=lambda i: res["ids"][i][-4:])        # 청크 번호가 가장 앞선 것 = 조항 첫머리
        _collection[("art", part, article)] = {"doc_id": res["ids"][k], "content": res["documents"][k], "score": None,
                                         "part": res["metadatas"][k]["part"],
                                         "article": res["metadatas"][k]["article"], "page": res["metadatas"][k]["page"]}
    return dict(_collection[("art", part, article)])


def search(query_vectors, k: int = 1) -> list[list[dict]]:
    """쿼리 벡터마다 코사인 유사도가 높은 순으로 k개.
    돌려주는 형식: [[{doc_id, content, score, part, article, page}, ...], ...]  (쿼리 순서 그대로)"""
    res = get_collection().query(query_embeddings=[list(map(float, v)) for v in query_vectors], n_results=k,
                                 include=["documents", "metadatas", "distances"])
    out = []
    for i in range(len(res["ids"])):
        hits = []
        for j in range(len(res["ids"][i])):
            meta = res["metadatas"][i][j]
            hits.append({"doc_id": res["ids"][i][j], "content": res["documents"][i][j],
                         "score": round(1 - res["distances"][i][j], 4),          # 코사인 거리 → 유사도
                         "part": meta["part"],
                         "article": meta["article"], "page": meta["page"]})
        out.append(hits)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="맞춤법 해설 PDF → Chroma 벡터 DB")
    ap.add_argument("pdf")
    ap.add_argument("--db", default=None, help=f"저장 폴더 (기본: {config.DB_PATH})")
    a = ap.parse_args()
    build_vector_db(a.pdf, a.db)
