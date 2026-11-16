# -*- coding: utf-8 -*-
"""국립국어원 「한글 맞춤법, 표준어 규정 해설」(2018) PDF 읽기.
머리말·쪽 번호를 지우고, 글자 위치별 쪽 번호와 조항 제목 위치를 함께 돌려준다.
다른 문서를 쓰게 되면 이 파일만 바꾸면 된다 (돌려주는 형식만 지키면 청킹·DB 코드는 그대로)."""
import re

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
