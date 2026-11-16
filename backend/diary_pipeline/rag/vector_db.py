# -*- coding: utf-8 -*-
"""벡터 DB (Chroma) 만들기와 검색.
다른 벡터 DB(Qdrant 등)로 바꿀 때는 이 파일의 build_vector_db() / search() 만 바꾸면 된다
(search 가 돌려주는 형식만 지키면 ④ 근거 검색 노드는 그대로).

처음 한 번 실행:  python -m diary_pipeline.rag.vector_db "한글맞춤법 표준어규정 해설.pdf" [--db chroma_db]"""
from .. import config
from ..models import embedding
from .pdf_loader import load_parts
from .chunker import chunk_by_length

CHUNKER = chunk_by_length          # 청킹 방식을 바꿀 때 여기만 바꾼다

_collection = {}


def build_vector_db(pdf_path: str, db_path: str = None) -> int:
    """PDF → 청킹 → 임베딩 → Chroma 저장. 저장한 청크 수를 돌려준다."""
    import chromadb
    db_path = db_path or config.DB_PATH
    parts = load_parts(pdf_path)
    for p in parts:
        nums = [n for _, n in p["articles"]]
        print(f"{p['name']}: {len(p['text']):,}자, 조항 제{nums[0]}~{nums[-1]}항 ({len(nums)}개)")
    chunks = CHUNKER(parts)
    print(f"청크 {len(chunks)}개 (평균 {sum(len(c['content']) for c in chunks) / len(chunks):.0f}자)")

    vectors = embedding.embed(config.EMBED_MODEL_ID, [c["content"] for c in chunks], show_progress=True)
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
        _collection["col"] = chromadb.PersistentClient(path=config.DB_PATH).get_collection(config.COLLECTION)
    return _collection["col"]


def search(query_vectors, k: int = 1) -> list[list[dict]]:
    """쿼리 벡터마다 코사인 유사도가 높은 순으로 k개.
    돌려주는 형식: [[{doc_id, content, score, article, page}, ...], ...]  (쿼리 순서 그대로)"""
    res = get_collection().query(query_embeddings=[list(map(float, v)) for v in query_vectors], n_results=k,
                                 include=["documents", "metadatas", "distances"])
    out = []
    for i in range(len(res["ids"])):
        hits = []
        for j in range(len(res["ids"][i])):
            meta = res["metadatas"][i][j]
            hits.append({"doc_id": res["ids"][i][j], "content": res["documents"][i][j],
                         "score": round(1 - res["distances"][i][j], 4),          # 코사인 거리 → 유사도
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
