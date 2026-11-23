"""의상 보상 · 옷장 주소. 실제 일은 rewards_repo.py 가 한다.

  일기 주간 보상 (FR-039) — 진행 · 상태는 GET /api/dashboard 의 diary_reward 로 받는다
  POST /api/rewards/diary/claim            body: {"week_start": "2026-11-16"} → {clothes, diary_reward, character}

  동화 구간 보상 (FR-040 · FR-045) — 동화 장 목록 화면에서 쓴다
  GET  /api/rewards/fairy/{book_id}        → {book_id, qualified, stages: [{order, chapters, status, clothes}], next}
  POST /api/rewards/fairy/{book_id}/claim  body: {"order": 1} → {clothes, fairy_reward}

  캐릭터 옷장 (FR-041)
  GET  /api/wardrobe                       → {equipped, slots: [{slot, label, items: [{id, name, status, condition, progress}]}]}
  PUT  /api/wardrobe/equip                 body: {"slot": "top", "clothes_id": 6 | null} → {character}

이미 받은 보상이면 409, 아직 받을 수 없거나 요청이 맞지 않으면 400, 내 동화책이 아니면 404.
토큰 · DB 오류는 books_api 와 같은 규칙 (_guard).
"""
from fastapi import APIRouter, Body, HTTPException

import devlog
import rewards_repo
from books_api import _act, _found, _guard, _user

router = APIRouter(prefix="/api")


def _call(fn, *args):
    """_guard 에 '이미 받음(409)'만 더한다."""
    try:
        return _guard(fn, *args)
    except rewards_repo.AlreadyClaimed as e:
        devlog.write("action", "rejected", {"call": fn.__name__, "reason": "already_claimed"})
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/rewards/diary/claim")
def claim_diary(body: dict = Body(...)):
    uid = _user()
    result = _call(rewards_repo.claim_diary, uid, body.get("week_start"))
    return _act("reward_diary_claim", result, week_start=body.get("week_start"), clothes_id=result["clothes"]["id"])


@router.get("/rewards/fairy/{book_id}")
def fairy_reward(book_id: int):
    uid = _user()
    return _found(_call(rewards_repo.fairy_reward, uid, book_id), "동화책")


@router.post("/rewards/fairy/{book_id}/claim")
def claim_fairy(book_id: int, body: dict = Body(...)):
    uid = _user()
    result = _found(_call(rewards_repo.claim_fairy, uid, book_id, body.get("order")), "동화책")
    return _act("reward_fairy_claim", result, book_id=book_id, order=body.get("order"), clothes_id=result["clothes"]["id"])


@router.get("/wardrobe")
def wardrobe():
    uid = _user()
    return _call(rewards_repo.wardrobe, uid)


@router.put("/wardrobe/equip")
def equip(body: dict = Body(...)):
    uid = _user()
    result = _call(rewards_repo.equip, uid, body.get("slot"), body.get("clothes_id"))
    return _act("wardrobe_equip", result, slot=body.get("slot"), clothes_id=body.get("clothes_id"))
