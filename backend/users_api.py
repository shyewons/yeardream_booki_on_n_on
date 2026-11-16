"""별명 · 토큰 주소들 (/api/users...). 실제 처리는 users_repo.py 가 한다.

  POST /api/users        별명 만들기 + 토큰 발급   body: {"nickname": "몽실이"}
                         → {"token": "...", "nickname": "몽실이"}  화면은 token 을 보관했다가 요청마다 X-User-Token 헤더로 보낸다
  GET  /api/users/me     토큰 확인 (재접속 시 기존 목장으로 들어갈지 판단)  → {"nickname": "몽실이"}

별명 규칙에 안 맞으면 400, 이미 있는 별명이면 409, 토큰이 없거나 틀리면 401, DB에 닿지 못하면 503.
"""
from fastapi import APIRouter, Body, HTTPException

import auth
import db
import users_repo

router = APIRouter(prefix="/api/users")


@router.post("")
def create_user(body: dict = Body(...)):
    try:
        return users_repo.create_user((body or {}).get("nickname"))
    except users_repo.BadNickname as e:
        raise HTTPException(status_code=400, detail=str(e))
    except users_repo.DuplicateNickname as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (db.DBNotConfigured, db.DBUnavailable) as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/me")
def me():
    token = auth.current_token()
    if not token:                                  # 여기는 더미 사용자로 대신하지 않는다 (토큰 확인이 목적)
        raise HTTPException(status_code=401, detail="별명을 먼저 만들어 주세요.")
    try:
        user = auth.find_user_by_token(token)
    except (db.DBNotConfigured, db.DBUnavailable) as e:
        raise HTTPException(status_code=503, detail=str(e))
    if user is None:
        raise HTTPException(status_code=401, detail="별명 정보를 찾을 수 없어요. 별명을 다시 만들어 주세요.")
    return {"nickname": user["nickname"]}
