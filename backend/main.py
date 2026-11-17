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
  /api/users                   별명 만들기 · 토큰 확인 (users_api.py → users_repo.py). 사용자 구분은 헤더 X-User-Token (auth.py)
  /api/...                     책 · 글 목록과 저장 (books_api.py → books_repo.py → db.py). 토큰 주인의 책만 보인다
  /api/dashboard               대시보드 메인: 이번 주 일기 작성 요일 · 내가 골라 쓴 표현 (dashboard_api.py → dashboard_repo.py)
  /question /topics /validate /correct /suggest      글쓰기: 질문 · 검사 · 교정 · 표현 추천 (writing_api.py)
  /log/ui                      화면 동작 기록 (devlog.py). 로그는 backend/logs/ 에 종류별로 쌓인다
  / , /books                   (임시) frontend/temp 의 시험용 화면. React 화면이 완성되면 proto_pages.py 와 아래 두 줄을 지운다
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

import db                                  # 가장 먼저: backend/.env 를 읽어 환경변수로 넣는다 (아래 파일들이 불러올 때 설정을 읽는다)
import auth
from auth import UserTokenMiddleware
from books_api import router as books_router
from dashboard_api import router as dashboard_router
from users_api import router as users_router
import books_repo
import devlog
import writing_api
from writing_api import router as writing_router


@asynccontextmanager
async def lifespan(app):
    """서버가 켜질 때: 그때의 설정을 logs/server_날짜.log 에 남기고, 모델 사용 모드면 모델을 미리 불러온다."""
    devlog.write("server", "start", {
        "use_models": writing_api.USE_MODELS, "preload": writing_api.PRELOAD, "demo_delay": writing_api.DEMO_DELAY,
        "mode": writing_api.pick_nodes()[1],                              # 실제로 돌게 될 모드 (라이브러리 · 벡터 DB 유무까지 반영)
        "database_url_set": bool(os.environ.get("DATABASE_URL")),         # 주소 자체는 적지 않는다 (비밀번호가 들어 있다)
        "nickname": os.environ.get("DUMMY_NICKNAME", "dummy_user"),
        "page_size": {"books": books_repo.PAGE_SIZE_BOOKS, "entries": books_repo.PAGE_SIZE_ENTRIES},
        "python": sys.version.split()[0], "log_dir": os.path.abspath(devlog.log_dir()),
    })
    async with writing_api.lifespan(app):
        yield
    devlog.write("server", "stop", None)


# 로그에 붙일 사용자 번호 (요청이 들어올 때 DB를 묻지 않는다).
#   토큰 없이 온 요청 → 이미 알아낸 더미 사용자 번호
#   토큰이 있는 요청  → 처음엔 '모름'. books_api / users_api 가 토큰으로 사용자를 찾은 뒤 devlog.set_user 로 채운다
devlog.user_lookup = lambda scope: None if auth.token_from_scope(scope) else books_repo.known_user_id()

app = FastAPI(lifespan=lifespan)
app.add_middleware(devlog.RequestLog)     # 모든 요청을 logs/request_날짜.log 에 적는다 (경로 · 응답 코드 · 걸린 시간)
app.add_middleware(UserTokenMiddleware)   # 요청 헤더 X-User-Token → auth.current_token() (books_repo 가 회원을 찾을 때 쓴다)


# api 상태 확인용 테스트 코드
@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(users_router)          # /api/users  (별명 만들기 · 토큰 확인)
app.include_router(books_router)          # /api/...
app.include_router(dashboard_router)      # /api/dashboard  (대시보드 메인)
app.include_router(writing_router)        # /question /topics /validate /correct /suggest
app.include_router(devlog.router)         # /log/ui

from proto_pages import router as proto_router        # (임시) 시험용 화면  ← React 화면이 완성되면 이 두 줄과 proto_pages.py 삭제
app.include_router(proto_router)
