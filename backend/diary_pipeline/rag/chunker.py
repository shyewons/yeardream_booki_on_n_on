# -*- coding: utf-8 -*-
"""청킹. 지금은 길이 기반(500자, 100자 겹침).
semantic / 조항 단위 청킹 등으로 바꿀 때는 이 파일에 함수를 추가하고 vector_db.py 의 CHUNKER 만 바꾸면 된다.
청크 형식: {doc_id, content, part, article, page}"""
import bisect

CHUNK_SIZE, CHUNK_OVERLAP = 500, 100       # 글자 수


def main_article(p: dict, art_pos: list[int], start: int, end: int) -> str:
    """청크 [start, end) 안에서 가장 많은 글자를 차지하는 조항 (청크가 두 조항에 걸칠 때 대표 조항)."""
    best, best_len = "총칙", 0
    bounds = art_pos + [len(p["text"])]
    for k, (a_start, num) in enumerate(p["articles"]):
        overlap = min(end, bounds[k + 1]) - max(start, a_start)
        if overlap > best_len:
            best, best_len = f"제{num}항", overlap
    return best


def chunk_by_length(parts: list[dict], size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """구간마다 size 글자씩, overlap 만큼 겹치게 자름. 구간 경계는 넘지 않음. 청크마다 출처(구간·쪽·조항)를 붙임."""
    chunks = []
    for p in parts:
        text = p["text"]
        page_pos = [pos for pos, _ in p["page_at"]]
        art_pos = [pos for pos, _ in p["articles"]]
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            page = p["page_at"][bisect.bisect_right(page_pos, start) - 1][1]
            article = main_article(p, art_pos, start, end)
            chunks.append({
                "doc_id": f"{p['name']}-{article}-{len(chunks):04d}",
                "content": text[start:end],
                "part": p["name"], "article": article, "page": page,
            })
            if end == len(text):
                break
            start = end - overlap
    return chunks
