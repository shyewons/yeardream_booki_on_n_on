# -*- coding: utf-8 -*-
"""
[글쓰기 API] 파일명: writing_api.py   (diary_pipeline 위에서 동작. 예전 시연용 app.py 에서 화면 내보내기를 뺀 것)

주소 (main.py 가 app.include_router(writing_api.router) 로 붙인다)
  GET  /question   입력칸 위 안내 질문 (일기/동화, 동화는 고른 주제 반영 · chapter 2 이상이면 장 첫 문장도 이어지는 질문)
  GET  /topics     동화 주제 추천 (코드 안 목록 FAIRY_TOPICS. 화면은 DB 의 주제를 쓰는 /api/topics 를 부른다)
  POST /validate   유효성 검사만 (diary_pipeline/input_validation.py). 통과하면 route == "correction"
  POST /correct    교정 단계(diary_pipeline/nodes)를 한 단계씩 실행하고, 단계가 끝날 때마다 결과를 한 줄(NDJSON)씩 흘려보냄
  POST /suggest    동화 표현 추천. 모델을 켜면 diary_pipeline/explain.py 의 표현 생성(Kanana), 끄면 demo_nodes.py 의 임시 낱말표
                   (임시일 때는 응답에 demo=True 와 안내 문구를 넣어, 화면이 '모델이 꺼져 있다'고 알리게 한다)

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
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterator

from diary_pipeline import config
from diary_pipeline.input_validation import validate_sentence, route_after_validation, OPENING_FIRST, OPENING_NEXT
from diary_pipeline.graph import NODES                            # 팀원이 정한 노드 목록 {이름: 함수}
from diary_pipeline import correct as _correct, query as _query, retrieve as _retrieve, explain as _explain   # 단계별 파일 (preload · 캐시 확인용)
from diary_pipeline import models as _models                      # 모델 캐시(이미 불러왔는지 확인용)
from diary_pipeline.correct import route_after_diff               # 바뀐 곳이 없으면 칭찬, 있으면 쿼리 재작성
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
    "rewrite_queries": "어떤 규칙인지 살펴보고 있어요", "retrieve_evidence": "맞춤법 규칙을 찾고 있어요",
    "explain": "설명을 쓰고 있어요",
}
MODEL_LIBS = ("torch", "transformers", "sentence_transformers", "chromadb", "kiwipiepy")

# 동화 표현 추천을 언제 할지 (환경변수 STORY_SUGGEST_ON 으로도 바꿀 수 있다)
#   "all"           : 맞춤법을 고친 문장에도 추천한다 (고친 문장을 바탕으로). 기본값
#   "no_correction" : 맞춤법이 맞은 문장에만 추천한다 (팀원 파이프라인의 run_story 와 같은 기준)
STORY_SUGGEST_ON = os.environ.get("STORY_SUGGEST_ON", "all").strip().lower()
STORY_SUGGEST_CHOICES = ("all", "no_correction")

# 교정 문장의 문장부호는 아이가 쓴 그대로 둔다 (끄려면 False).
#   교정 모델(et5)이 문장부호를 제멋대로 바꾸는 버릇이 있다:
#     끝: "맞나?" → "맞나?.", "맞을지...." → "맞을지~~."      가운데: "아니... 왜" → "아니 왜"
#   ② 바뀐 곳 찾기는 문장부호만 바뀐 것을 교정으로 치지 않으므로(config.IGNORE_PUNCT_ONLY), 화면에는 '고친 곳 없음'인데 문장부호만 사라진다.
#   그래서 교정 문장을 '아이가 쓴 문장에 진짜로 고친 곳(difference)만 바꿔 넣은 것'으로 다시 만든다 (keep_child_punct).
#   아이가 끝에 문장부호를 안 썼으면 교정 모델이 붙인 마침표는 그대로 둔다 ("놀았다" → "놀았다.").
KEEP_END_MARKS = True
_END_MARKS = re.compile(r"[.?!~…]+\s*$")


def tidy_end(original: str, revised: str) -> str:
    """교정 문장(revised)의 끝 문장부호를 아이가 쓴 문장(original)의 끝 문장부호로 맞춘다."""
    if not KEEP_END_MARKS or not isinstance(original, str) or not isinstance(revised, str):
        return revised
    mine = _END_MARKS.search(original.rstrip())
    if not mine:                                          # 아이가 끝에 문장부호를 안 썼다 → 교정 모델 것 그대로
        return revised
    body = _END_MARKS.sub("", revised.rstrip())
    return body + mine.group(0).strip() if body else revised


def keep_child_punct(original: str, revised: str, difference: list) -> str:
    """아이가 쓴 문장(original)에 진짜로 고친 곳(difference: before → after, 원문 위치 start~end)만 바꿔 넣는다.
    교정 모델이 문장부호만 바꾼 곳은 아이 것이 그대로 남는다. 끝 문장부호는 tidy_end 와 같은 규칙.
    위치가 맞지 않는 등 문제가 있으면 교정 모델 문장을 그대로 돌려준다."""
    if not KEEP_END_MARKS or not isinstance(original, str) or not isinstance(revised, str):
        return revised
    try:
        out = original
        for d in sorted(difference or [], key=lambda d: d["start"], reverse=True):   # 뒤에서부터 바꿔야 앞 위치가 안 밀린다
            if out[d["start"]:d["end"]] != d["before"]:
                return revised
            out = out[:d["start"]] + d["after"] + out[d["end"]:]
    except (KeyError, TypeError):
        return revised
    out = out.rstrip()
    if not _END_MARKS.search(out):                        # 아이가 끝에 문장부호를 안 썼다 → 교정 모델이 붙인 것을 붙인다
        added = _END_MARKS.search(revised.rstrip())
        if added:
            out += added.group(0).strip()
    return out


# 모델이 꺼져 있을 때 임시 추천에 붙이는 안내 (아이와 선생님이 '모델이 만든 문장'으로 오해하지 않게)
DEMO_SUGGEST_NOTICE = "지금은 표현 추천 모델이 꺼져 있어요. 아래 문장은 모델이 만든 것이 아니라 임의로 바꿔 본 예시예요."
DEMO_SUGGEST_POINT = "(임시 예시) 낱말 하나를 비슷한 말로 바꿔 본 문장이에요."


# =====================================================================
# 입력칸 위에 보여 줄 안내 질문
# =====================================================================
# 동화 주제 (아이가 관심 가질 만한 동물 · 사물 · 상상 속 친구).
# 실제 화면은 DB 의 fairy_topics 표를 쓴다 (/api/topics). 이 목록은 표가 비어 있을 때 대신 쓰는 예비이고,
# 요구사항정의서 '동화주제' 시트의 주제 10개와 같다 (2026-11-19. 처음 20개에서 바꿨다).
FAIRY_TOPICS = [
    "토끼", "마법 가방", "구름 마을", "말하는 나무", "작은 용",
    "비밀 문", "바닷속 학교", "길 잃은 별", "장난감 로봇", "하늘을 나는 신발",
]
FAIRY_FIRST = [                       # {t} 자리에 고른 주제가 들어간다
    "「{t}」 이야기는 어떻게 시작될까요? 첫 문장을 적어보세요.",
    "「{t}」 이야기를 상상해 보세요. 어디에서 시작되나요?",
]
FAIRY_FIRST_FREE = [                  # 주제 없이 스스로 정해서 쓸 때
    "상상한 이야기의 첫 문장을 적어보세요. 누가 나오나요?",
    "옛날 옛날에 누가 살았을까요? 첫 문장을 적어보세요.",
]
FAIRY_CHAPTER_START = [               # 2장부터 장의 첫 문장 (앞 장에서 이어지는 이야기). {n} 자리에 장 번호
    "{n}장이 시작돼요. 앞 장에 이어서 어떤 일이 벌어질까요?",
    "{n}장에서는 주인공에게 무슨 일이 생길까요?",
]
FAIRY_NEXT = [
    "그다음에는 어떤 일이 벌어졌나요?",
    "주인공은 어떤 기분이었을까요?",
    "누가 새로 나타났나요?",
    "이야기는 어떻게 끝날까요?",
]


def get_topics(exclude=(), others: int = 3, pool=None) -> Dict[str, Any]:
    """추천 주제 하나(pick)와 다른 주제 몇 개(others). exclude 에 적힌 주제는 되도록 빼고 고른다(다 빼면 처음부터 다시).
    pool 을 주면 그 목록에서 고른다 (books_api 의 /api/topics 가 DB 의 fairy_topics 를 넘긴다). 없으면 FAIRY_TOPICS."""
    every = list(pool) if pool else list(FAIRY_TOPICS)
    others = min(others, len(every) - 1)
    pool = [x for x in every if x not in set(exclude)]
    if len(pool) < others + 1:
        pool = every
    picked = random.sample(pool, others + 1)
    return {"pick": picked[0], "others": picked[1:]}


def get_question(passed_count: int = 0, kind: str = "diary", topic: str = "", chapter: int = 1) -> str:
    """지금까지 통과한 문장 수에 맞는 질문. 0이면 OPENING_FIRST 중 무작위, 1 이상이면 OPENING_NEXT를 차례로.
    동화(kind="fairy")는 일기와 다른 문구를 쓰고, 고른 주제(topic)가 있으면 첫 질문에 넣는다.
    동화 2장부터(chapter >= 2)는 장의 첫 문장이어도 '이야기는 어떻게 시작될까요?' 대신 이어지는 질문(FAIRY_CHAPTER_START)을 쓴다."""
    if kind == "fairy":
        topic = " ".join(str(topic or "").split())[:20]
        if passed_count <= 0 and (chapter or 1) >= 2:
            return random.choice(FAIRY_CHAPTER_START).format(n=chapter)
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
        missing = [m for m in MODEL_LIBS if not importlib.util.find_spec(m)]
        print(f"[app] 모델 라이브러리({', '.join(missing)})가 없어 임시 모드로 실행합니다.  pip install -r requirements-models.txt")
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
        "spell_correct": ("맞춤법 교정 모델(et5)", _safe(lambda: "et5" in _correct._model), _correct.preload),
        "rewrite_queries": ("형태소 분석기(Kiwi)", _safe(lambda: "k" in _query._kiwi), _query.preload),
        "retrieve_evidence": ("근거 검색 모델(KURE)", _safe(lambda: ("emb", config.EMBED_MODEL_ID) in _models._cache), _retrieve.preload),
        "explain": ("설명문 모델(Kanana)", _safe(lambda: ("llm", config.EXPLAIN_LLM_ID) in _models._cache), _explain.preload),
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
    """동화 표현 추천. 받는 값: {"sentence": 문장, "has_correction": 맞춤법을 고쳤는지}
    돌려주는 값:
      {"options": [{"text": 바꾼 문장, "point": 무엇이 좋아졌는지 한 줄}, ...],   추천이 없으면 빈 목록
       "guide": 맨 위 안내, "original_point": '원래 문장' 보기 아래 문구,
       "demo": 임시 추천인지, "notice": 임시일 때 화면에 꼭 보여 줄 안내, "mode": 실행 모드, "skipped": 추천하지 않은 이유}
    모델을 켜면 explain.suggest_expressions(Kanana)로 새 표현 2개를 만들고, 만들지 못한 자리('원문 유지')는 빼고 돌려준다.
    모델이 꺼져 있으면 demo_nodes.py 의 낱말표로 만든 임시 문장을 demo=True 와 안내 문구를 붙여 돌려준다."""
    p = payload or {}
    sentence = str(p.get("sentence", "")).strip()[:200]
    has_correction = bool(p.get("has_correction"))
    rule = STORY_SUGGEST_ON if STORY_SUGGEST_ON in STORY_SUGGEST_CHOICES else "all"
    out = {"options": [], "guide": config.STORY_GUIDE, "original_point": config.STORY_ORIGINAL_POINT,
           "demo": False, "notice": "", "mode": "", "skipped": None}
    if not sentence:
        out["skipped"] = "empty"
    elif rule == "no_correction" and has_correction:
        out["skipped"] = "has_correction"                      # 맞춤법이 맞은 문장에만 추천하는 설정
    else:
        _, mode = pick_nodes()
        out["mode"] = mode
        if mode.startswith("실제"):                            # 모델 사용: 팀원 파이프라인의 ⑥ 표현 생성
            made = _explain.suggest_expressions({"original_sentence": sentence})["expressions"]
            out["options"] = [{"text": e["text"], "point": e["point"]} for e in made if e.get("source") == "생성"]
        else:                                                   # 모델 꺼짐: 임시 낱말표 (반드시 임시라고 알린다)
            out["demo"] = True
            out["notice"] = DEMO_SUGGEST_NOTICE
            out["guide"] = "다른 말로 쓸 수도 있어요."
            out["options"] = [{"text": t, "point": DEMO_SUGGEST_POINT} for t in suggest_expressions(sentence)]
    dev_log("suggest", {"request": p, "rule": rule, "response": out})
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

    yield stage("spell_correct");   yield from prepare("spell_correct")
    ev = step("spell_correct")
    tidy = tidy_end(original_sentence, state.get("revised_sentence"))   # 끝 문장부호는 아이 것 그대로 ("맞나?." → "맞나?", "맞을지~~." → "맞을지....").
                                                                         # 바뀐 곳 찾기 전에 고쳐서, 화면 · 저장 · 비교 모두 정리된 문장을 쓴다
    if tidy != state.get("revised_sentence"):
        state["revised_sentence"] = tidy
        ev = {**ev, "data": {**ev["data"], "revised_sentence": tidy}}
    yield ev
    yield stage("extract_diff");    yield step("extract_diff")
    kept = keep_child_punct(original_sentence, state.get("revised_sentence"), state.get("difference"))
    if kept != state.get("revised_sentence"):              # 문장부호를 아이 것으로 되돌린 교정 문장 (화면 · 저장에 쓰인다)
        state["revised_sentence"] = kept
        yield {"type": "update", "data": {"revised_sentence": kept}}
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
    def question(passed: int = 0, kind: str = "diary", topic: str = "", chapter: int = 1):
        return {"question": get_question(passed, kind, topic, chapter)}

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
