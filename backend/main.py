# -*- coding: utf-8 -*-
"""
백엔드 서버 시작점.

실행 (backend 폴더에서)
  pip install -r requirements.txt
  uvicorn main:app --reload            ->  http://127.0.0.1:8000   (API 문서: /docs)

  모델 없이 화면 흐름만 볼 때(기본값): 그대로 실행
  모델 사용: USE_MODELS=1 uvicorn main:app   (requirements-models.txt 설치, chroma_db 필요. writing_api.py 머리말 참고)
  DB 주소(/api/...)는 backend/.env 의 DATABASE_URL 이 있어야 동작한다 (.env.example 참고). 없으면 그 주소들만 503.

주소 묶음
  /health                      상태 확인
  /api/...                     책 · 글 목록과 저장 (books_api.py → books_repo.py → db.py)
  /question /topics /validate /correct /suggest      글쓰기: 질문 · 검사 · 교정 · 표현 추천 (writing_api.py)
  / , /books                   (임시) frontend/temp 의 시험용 화면. React 화면이 완성되면 proto_pages.py 와 아래 두 줄을 지운다
"""
from fastapi import FastAPI

import db                                  # 가장 먼저: backend/.env 를 읽어 환경변수로 넣는다 (아래 파일들이 불러올 때 설정을 읽는다)
from books_api import router as books_router
from writing_api import lifespan, router as writing_router

app = FastAPI(lifespan=lifespan)          # lifespan: 모델 사용 모드일 때 서버를 켜면서 모델을 미리 불러온다


# api 상태 확인용 테스트 코드
@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(books_router)          # /api/...
app.include_router(writing_router)        # /question /topics /validate /correct /suggest

from proto_pages import router as proto_router        # (임시) 시험용 화면  ← React 화면이 완성되면 이 두 줄과 proto_pages.py 삭제
app.include_router(proto_router)
