# -*- coding: utf-8 -*-
"""
[글쓰기 API] 파일명: writing_api.py   (diary_pipeline 위에서 동작. 예전 시연용 app.py 에서 화면 내보내기를 뺀 것)

주소 (main.py 가 app.include_router(writing_api.router) 로 붙인다)
  GET  /question   입력칸 위 안내 질문 (일기/동화, 동화는 고른 주제 반영)
  GET  /topics     동화 주제 추천
  POST /validate   유효성 검사만 (diary_pipeline/input_validation.py). 통과하면 route == "correction"
  POST /correct    교정 단계(diary_pipeline/nodes)를 한 단계씩 실행하고, 단계가 끝날 때마다 결과를 한 줄(NDJSON)씩 흘려보냄
  POST /suggest    동화 표현 추천 (지금은 demo_nodes.py 의 임시 낱말표)

실행은 main.py 를 본다 (uvicorn main:app). 이 파일은 서버를 직접 만들지 않고 router 와 lifespan 만 내놓는다.
  모델 없이(기본): 모델 노드 자리를 demo_nodes.py 의 임시 노드가 대신한다. 시험용 지연: DEMO_DELAY=1.5
  모델 사용:       USE_MODELS=1  (GPU·모델 라이브러리(requirements-models.txt)·chroma_db 필요)
                   서버를 켤 때 모델을 먼저 불러온다. 첫 요청 때 불러오게 하려면 PRELOAD=0

diary_pipeline/ 의 노드들을 '한 단계씩' 불러서 단계별 안내를 만든다.
"""
import asyncio
import importlib.util
import json
import os
import random
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterator

from diary_pipeline import config
from diary_pipeline.input_validation import validate_sentence, route_after_validation, OPENING_FIRST, OPENING_NEXT
from diary_pipeline.graph import NODES                            # 팀원이 정한 노드 목록 {이름: 함수}
from diary_pipeline.nodes.extract_diff import route_after_diff    # 바뀐 곳이 없으면 칭찬, 있으면 쿼리 재작성
from diary_pipeline.nodes import spell_correct as _spell, rewrite_queries as _rewrite, retrieve_evidence as _retrieve, explain as _explain
from diary_pipeline.models import llm as _llm, embedding as _embedding      # 모델 캐시(이미 불러왔는지 확인용)
from demo_nodes import DEMO_NODES, suggest_expressions
import devlog

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# ★ 수정해서 쓰는 설정 ★
# =====================================================================
USE_MODELS = os.environ.get("USE_MODELS", "0") == "1"        # True 면 실제 모델 사용 (환경변수 USE_MODELS=1 로도 켤 수 있다)
DEMO_DELAY = float(os.environ.get("DEMO_DELAY", "0"))        # 임시 모드에서 단계마다 늦추는 시간(초). 로딩 화면 시험용
                                                             # (개발용 로그 설정 DEV_LOG · LOG_DIR 은 devlog.py 에 있다)
PRELOAD = os.environ.get("PRELOAD", "1") == "1"              # True 면 서버를 켤 때 모델을 미리 불러온다 (첫 문장이 느려지지 않음). 모델 사용 모드일 때만 의미가 있다.
                                                             # 끄려면 PRELOAD=0 (그러면 첫 요청 때 불러오고, 화면에 '불러오는 중'이 나온다)

STAGE_LABELS = {                                             # 화면에 보여 줄 진행 안내 (아이 눈높이)
    "spell_correct": "맞춤법을 확인하고 있어요", "extract_diff": "바뀐 곳을 찾고 있어요",
    "rewrite_queries": "맞춤법 규칙을 찾을 준비를 하고 있어요", "retrieve_evidence": "맞춤법 규칙을 찾고 있어요",
    "explain": "설명을 쓰고 있어요",
}
MODEL_LIBS = ("torch", "transformers", "sentence_transformers", "chromadb")


# =====================================================================
# 입력칸 위에 보여 줄 안내 질문
# =====================================================================
# 동화 주제 (아이가 관심 가질 만한 동물 · 사물 · 상상 속 친구). 자유롭게 더하고 빼면 된다.
FAIRY_TOPICS = [
    "고양이", "강아지", "토끼", "공룡", "용", "곰", "펭귄", "고래", "다람쥐", "도깨비",
    "로봇", "우주선", "마법 지팡이", "보물 상자", "말하는 나무", "구름", "달", "무지개", "눈사람", "장난감 기차",
]
FAIRY_FIRST = [                       # {t} 자리에 고른 주제가 들어간다
    "「{t}」 이야기는 어떻게 시작될까요? 첫 문장을 적어보세요.",
    "「{t}」 이야기를 상상해 보세요. 어디에서 시작되나요?",
]
FAIRY_FIRST_FREE = [                  # 주제 없이 스스로 정해서 쓸 때
    "상상한 이야기의 첫 문장을 적어보세요. 누가 나오나요?",
    "옛날 옛날에 누가 살았을까요? 첫 문장을 적어보세요.",
]
FAIRY_NEXT = [
    "그다음에는 어떤 일이 벌어졌나요?",
    "주인공은 어떤 기분이었을까요?",
    "누가 새로 나타났나요?",
    "이야기는 어떻게 끝날까요?",
]


def get_topics(exclude=(), others: int = 3) -> Dict[str, Any]:
    """추천 주제 하나(pick)와 다른 주제 몇 개(others). exclude 에 적힌 주제는 되도록 빼고 고른다(다 빼면 처음부터 다시)."""
    pool = [x for x in FAIRY_TOPICS if x not in set(exclude)]
    if len(pool) < others + 1:
        pool = list(FAIRY_TOPICS)
    picked = random.sample(pool, others + 1)
    return {"pick": picked[0], "others": picked[1:]}


def get_question(passed_count: int = 0, kind: str = "diary", topic: str = "") -> str:
    """지금까지 통과한 문장 수에 맞는 질문. 0이면 OPENING_FIRST 중 무작위, 1 이상이면 OPENING_NEXT를 차례로.
    동화(kind="fairy")는 일기와 다른 문구를 쓰고, 고른 주제(topic)가 있으면 첫 질문에 넣는다."""
    if kind == "fairy":
        topic = " ".join(str(topic or "").split())[:20]
        if passed_count <= 0:
            return random.choice(FAIRY_FIRST).format(t=topic) if topic else random.choice(FAIRY_FIRST_FREE)
        return FAIRY_NEXT[(passed_count - 1) % len(FAIRY_NEXT)]
    if passed_count <= 0:
        return random.choice(OPENING_FIRST)
    return OPENING_NEXT[(passed_count - 1) % len(OPENING_NEXT)]


# =====================================================================
# 쓸 노드 고르기: 모델이 준비돼 있으면 팀원 노드, 아니면 임시 노드
# =====================================================================
def pick_nodes():
    """(노드 목록, 실행 모드 이름)을 돌려준다. 모델을 켰어도 준비가 안 됐으면 멈추지 않고 임시 노드로 대신한다."""
    if not USE_MODELS:
        return {**NODES, **DEMO_NODES}, "임시(모델 미연결)"
    if not all(importlib.util.find_spec(m) for m in MODEL_LIBS):
        print("[app] torch/transformers/sentence-transformers/chromadb 가 없어 임시 모드로 실행합니다.")
        return {**NODES, **DEMO_NODES}, "임시(라이브러리 없음)"
    nodes, mode = dict(NODES), "실제 모델"
    if not os.path.isdir(config.DB_PATH):                    # 벡터 DB 폴더가 없으면 근거 검색만 임시로
        print(f"[app] 벡터 DB 폴더({config.DB_PATH})가 없어 근거 검색만 임시로 대신합니다.")
        nodes["retrieve_evidence"] = DEMO_NODES["retrieve_evidence"]
        mode = "실제 모델 (근거 검색만 임시: DB 없음)"
    return nodes, mode


def _safe(fn):
    """캐시를 들여다보는 함수가 실패하면 '아직 안 불러옴'으로 보고 불러오기를 부른다 (preload 는 여러 번 불러도 안전하다)."""
    def run():
        try:
            return bool(fn())
        except Exception:
            return False
    return run


def model_loaders(n):
    """모델을 쓰는 단계 -> (화면에 보여 줄 모델 이름, 이미 불러왔는지 확인하는 함수, 불러오는 함수).
    실제 노드를 쓰는 단계만 넣는다 (임시 노드로 대신한 단계는 불러올 모델이 없다)."""
    L = {
        "spell_correct": ("맞춤법 교정 모델(et5)", _safe(lambda: "et5" in _spell._model), _spell.preload),
        "rewrite_queries": ("쿼리 재작성 모델(Kanana)", _safe(lambda: config.QUERY_LLM_ID in _llm._models), _rewrite.preload),
        "retrieve_evidence": ("근거 검색 모델(bge-m3)", _safe(lambda: config.EMBED_MODEL_ID in _embedding._models), _retrieve.preload),
        "explain": ("설명문 모델(Kanana)", _safe(lambda: config.EXPLAIN_LLM_ID in _llm._models), _explain.preload),
    }
    return {k: v for k, v in L.items() if n.get(k) is NODES.get(k)}


def preload_all():
    """쓸 모델을 미리 불러온다 (서버를 켤 때 한 번). 실패해도 서버는 켜지고, 그 모델은 첫 요청 때 다시 시도한다."""
    n, mode = pick_nodes()
    for name, (label, is_loaded, load) in model_loaders(n).items():
        if is_loaded():
            continue
        t0 = time.time()
        print(f"[preload] {label} 불러오는 중... (처음이면 내려받느라 몇 분 걸립니다)", flush=True)
        try:
            load()
            print(f"[preload] {label} 완료 ({time.time() - t0:.0f}초)", flush=True)
        except Exception as e:
            print(f"[preload] {label} 실패: {e}  (첫 요청 때 다시 시도합니다)", flush=True)
    print(f"[preload] 준비 완료 · 실행 모드: {mode}", flush=True)


@asynccontextmanager
async def lifespan(app):
    """서버가 켜질 때 한 번 실행된다. 모델을 다 불러온 뒤에야 요청을 받기 시작한다."""
    if PRELOAD:
        await asyncio.to_thread(preload_all)             # 서버 이벤트 루프를 막지 않도록 다른 스레드에서
    yield


# =====================================================================
# 요청 처리 (FastAPI 없이도 부를 수 있는 일반 함수)
# =====================================================================
def dev_log(label: str, data: Any) -> None:
    """검사 · 교정 · 표현 추천의 요청과 결과를 logs/writing_날짜.log 에 적는다 (아이가 쓴 문장이 들어간다). 다른 로그는 devlog.py 참고."""
    devlog.write("writing", label, data)


def handle_validate(payload: dict) -> dict:
    """유효성 검사만 한다. 통과하면 route 가 "correction"이고, 교정은 화면이 /correct 로 따로 요청한다."""
    result = validate_sentence(
        payload.get("user_input", ""),
        payload.get("validation_attempt", 0),
        payload.get("previous_sentences"),
        payload.get("choice_picks"),
        payload.get("kind"),                          # 글 종류 "diary"/"fairy" (없으면 일기 기준)
    )
    out = {**result, "route": route_after_validation(result)}       # "correction" / "retry" / "skipped"
    dev_log("validate", {"request": payload, "response": out})
    return out


def handle_suggest(payload: dict) -> dict:
    """동화 표현 추천: 문장을 다르게 쓴 예를 돌려준다 {"options": [문장, ...], "demo": True}. 추천할 것이 없으면 options 가 비어 있다.
    지금은 모델 사용 여부와 상관없이 demo_nodes.py 의 낱말표로 만든 임시 추천이다 (추천 모델이 정해지면 여기만 바꾼다)."""
    out = {"options": suggest_expressions(str((payload or {}).get("sentence", ""))[:200]), "demo": True}
    dev_log("suggest", {"request": payload, "response": out})
    return out


def iter_correction(original_sentence: str) -> Iterator[Dict[str, Any]]:
    """교정 단계를 한 단계씩 실행하며, 단계 시작과 새 결과마다 사건(dict)을 내준다.
      {"type": "stage",  "stage": "spell_correct", "label": "..."}      단계 시작
      {"type": "loading", "stage": "...", "model": "...", "label": "..."}  모델을 처음 불러오는 중 (다 불러오면 stage 가 다시 온다)
      {"type": "update", "data": {"revised_sentence": ...}}              새로 나온 값
      {"type": "done",   "correction": {...}, "mode": "..."}             끝. correction 은 build_response 의 correction 객체
    설명문(explain)은 수정 1건이 끝날 때마다 update 로 지금까지의 explanations 를 내준다."""
    n, mode = pick_nodes()
    wait = DEMO_DELAY if mode.startswith("임시") else 0.0
    state: Dict[str, Any] = {"original_sentence": original_sentence}
    loaders = model_loaders(n)
    began, timing = time.perf_counter(), {}                  # 단계별 걸린 시간(ms): 끝나면 logs/model_날짜.log 에 적는다

    def spent(key, since):
        timing[key] = round(timing.get(key, 0) + (time.perf_counter() - since) * 1000, 1)

    def stage(name):
        return {"type": "stage", "stage": name, "label": STAGE_LABELS[name]}

    def prepare(name):                                       # 모델이 아직 안 올라와 있으면 '불러오는 중'을 먼저 알리고 불러온다
        info = loaders.get(name)
        if info and not info[1]():
            yield {"type": "loading", "stage": name, "model": info[0], "label": f"{info[0]} 불러오는 중이에요"}
            t0 = time.perf_counter()
            info[2]()                                        # 처음이면 내려받기 때문에 몇 분 걸릴 수 있다
            spent("load:" + name, t0)
            yield stage(name)                                # 다 불러왔으니 원래 단계 안내로 되돌린다

    def step(name):                                          # 노드를 부르고, 새로 나온 키만 update 로 내준다
        if wait:                                             # (임시 모드 시험용) 안내 문구가 보이도록 일하기 전에 잠깐 기다린다
            time.sleep(wait)
        t0 = time.perf_counter()
        out = n[name](state)
        spent(name, t0)
        state.update(out)
        return {"type": "update", "data": out}

    yield stage("spell_correct");   yield from prepare("spell_correct");   yield step("spell_correct")
    yield stage("extract_diff");    yield step("extract_diff")
    if route_after_diff(state) == "compliment":
        yield step("compliment")
    else:
        yield stage("rewrite_queries");   yield from prepare("rewrite_queries");   yield step("rewrite_queries")
        yield stage("retrieve_evidence"); yield from prepare("retrieve_evidence"); yield step("retrieve_evidence")
        yield stage("explain");           yield from prepare("explain")
        exps = []
        for i in range(len(state["difference"])):            # 수정 1건씩 (explain 노드는 번호 짝으로 동작하므로 1건짜리 State 로 부른다)
            sub = {"difference": [state["difference"][i]], "rewritten_queries": [state["rewritten_queries"][i]],
                   "evidence_docs": [state["evidence_docs"][i]]}
            if wait:
                time.sleep(wait)
            t0 = time.perf_counter()
            exps += n["explain"](sub)["explanations"]
            spent("explain", t0)
            state["explanations"] = list(exps)
            yield {"type": "update", "data": {"explanations": list(exps)}}
    # 결과 묶기: build_response 는 유효성 검사 결과도 읽으므로, '통과한 문장'이라는 사실만 채워 준다
    response = n["build_response"]({**state, "is_valid": True, "line_skipped": False})["response"]
    devlog.write("model", "correct", {"mode": mode, "chars": len(original_sentence), "changes": len(state.get("difference") or []),
                                      "stages_ms": timing, "total_ms": round((time.perf_counter() - began) * 1000, 1)})
    yield {"type": "done", "correction": response["correction"], "mode": mode}


def stream_correction(payload: dict):
    """iter_correction 의 사건을 JSON 한 줄(NDJSON)씩 내준다. 오류가 나도 화면이 알 수 있게 error 사건으로 보낸다."""
    try:
        text = payload.get("original_sentence", "")
        if not text:
            raise ValueError("교정할 문장이 없습니다")
        for ev in iter_correction(text):
            if ev.get("type") == "done":
                dev_log("correct", ev)
            yield json.dumps(ev, ensure_ascii=False) + "\n"
    except Exception as e:                                   # 모델 오류, 벡터 DB 오류 등
        dev_log("correct_error", {"original_sentence": payload.get("original_sentence", ""), "error": str(e)})
        devlog.error("correct", e, {"chars": len(payload.get("original_sentence", "") or "")})
        yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"


# =====================================================================
# FastAPI (설치돼 있을 때만 만든다)
# =====================================================================
try:
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
except ImportError:                                          # fastapi 가 없으면 위의 일반 함수만 쓸 수 있다
    router = None
else:
    class ValidateRequest(BaseModel):
        user_input: str = ""
        validation_attempt: int = 0
        previous_sentences: list[str] = []
        choice_picks: list[int] = []
        kind: str = "diary"                                   # 글 종류 (일기/동화). 빠지면 동화 기준이 적용되지 않는다

    class CorrectRequest(BaseModel):
        original_sentence: str = ""

    router = APIRouter()                                      # main.py 가 app.include_router(router) 로 붙인다

    @router.get("/question")
    def question(passed: int = 0, kind: str = "diary", topic: str = ""):
        return {"question": get_question(passed, kind, topic)}

    @router.post("/suggest")                                     # 동화 표현 추천 (임시): {"sentence": "..."} → {"options": [...]}
    def suggest(payload: dict):
        return handle_suggest(payload)

    @router.get("/topics")                                       # 동화 주제 추천: {"pick": "고양이", "others": [3개]}
    def topics(exclude: str = ""):
        return get_topics([x for x in exclude.split(",") if x])

    @router.post("/validate")
    def validate(req: ValidateRequest):
        return handle_validate(req.model_dump())

    @router.post("/correct")
    def correct(req: CorrectRequest):
        return StreamingResponse(stream_correction(req.model_dump()), media_type="application/x-ndjson")
