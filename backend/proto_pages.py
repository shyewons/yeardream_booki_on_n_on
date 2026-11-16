# -*- coding: utf-8 -*-
"""
(임시) 시험용 화면 내보내기.  React 화면(frontend/src)이 완성되면 이 파일과 main.py 의 두 줄을 지운다.

  GET /                  frontend/temp/index.html  (글쓰기).  ?book= 이나 ?practice=1 없이 열면 /books 로 보낸다
  GET /books             frontend/temp/books.html  (목장 · 목록 · 글 보기)

화면 파일 위치는 환경변수 PROTO_DIR 로 바꿀 수 있다 (기본: 이 파일 기준 ../frontend/temp).
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO_DIR = os.environ.get("PROTO_DIR") or os.path.join(HERE, "..", "frontend", "temp")

router = APIRouter(include_in_schema=False)     # API 문서(/docs)에는 넣지 않는다


def _page(name: str) -> str:
    try:
        with open(os.path.join(PROTO_DIR, name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        raise HTTPException(404, f"시험용 화면 {name} 을 찾을 수 없습니다. (찾은 곳: {os.path.abspath(PROTO_DIR)})")


@router.get("/", response_class=HTMLResponse)
def index(book: str | None = None, practice: str | None = None):
    if book is None and practice is None:
        return RedirectResponse("/books")
    return _page("index.html")


@router.get("/books", response_class=HTMLResponse)
def books_page():
    return _page("books.html")
