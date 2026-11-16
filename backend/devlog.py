# -*- coding: utf-8 -*-
"""
개발용 로그. 화면에는 보이지 않고 backend/logs/ 폴더에 종류별 · 날짜별 파일로 쌓인다 (한 줄 = JSON 하나).

  파일                        무엇이 쌓이나                                              어디서 적나
  request_날짜.log   모든 요청: 방식 · 경로 · 응답 코드 · 걸린 시간(ms)                    RequestLog (main.py 가 붙임)
  error_날짜.log     오류: DB 접속 실패, 모델 오류, 처리 못 한 예외(traceback 포함)         books_api._guard, writing_api, RequestLog
  action_날짜.log    저장 동작: 책 만들기, 글 열기, 문장 저장 · 끼워 넣기 · 순서 바꾸기, 이야기 저장   books_api
  model_날짜.log     교정 한 번의 단계별 걸린 시간(ms)과 실행 모드                         writing_api.iter_correction
  ui_날짜.log        화면 동작: 화면 이동, 주제 고르기, 표현 선택, 다시쓰기 등              화면이 POST /log/ui 로 보냄
  server_날짜.log    서버가 켜질 때의 설정 (모델 모드, DB 설정 여부 등)                     main.py
  writing_날짜.log   검사 · 교정 · 표현 추천의 요청과 결과 (★ 아이가 쓴 문장이 그대로 들어간다)   writing_api

글 내용(문장)은 writing 파일에만 들어간다. 나머지 파일에는 번호와 개수만 적는다.
logs/ 는 .gitignore 에 있어 깃에 올라가지 않는다. 오래된 파일은 자동으로 지우지 않으니 필요할 때 직접 지운다.

설정 (환경변수 또는 backend/.env)
  DEV_LOG=0      로그를 전부 끈다 (기본 1)
  LOG_DIR=경로   로그 폴더를 바꾼다 (기본 backend/logs)
"""
import json
import os
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
CHANNELS = ("request", "error", "action", "model", "ui", "server", "writing")
MAX_UI_EVENT = 40          # 화면이 보내는 동작 이름 최대 글자 수
MAX_UI_DATA = 2000         # 화면이 보내는 덧붙임 자료 최대 글자 수 (JSON 으로 바꾼 길이)
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("DEV_LOG", "1") == "1"


def log_dir() -> str:
    return os.environ.get("LOG_DIR") or os.path.join(HERE, "logs")


def write(channel: str, label: str, data=None) -> None:
    """channel 파일에 한 줄 적는다. 로그를 못 써도 서비스는 계속되어야 하므로 오류는 삼킨다."""
    if not enabled() or channel not in CHANNELS:
        return
    now = time.time()
    line = json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + ".%03d" % (now % 1 * 1000),
                       "label": label, "data": data}, ensure_ascii=False, default=str)
    try:
        with _lock:
            os.makedirs(log_dir(), exist_ok=True)
            with open(os.path.join(log_dir(), f"{channel}_{time.strftime('%Y%m%d', time.localtime(now))}.log"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


def error(where: str, exc: BaseException, data=None) -> None:
    """오류를 error 파일에 적는다. where 는 어디서 났는지 (예: "db", "correct", "request")."""
    write("error", where, {"type": type(exc).__name__, "message": str(exc), "info": data,
                           "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:]})


def handle_ui(payload) -> dict:
    """화면이 보낸 동작 하나를 ui 파일에 적는다. payload: {"event": "topic_pick", "sid": "화면을 연 번호", "page": "write", "data": {...}}
    아무나 보낼 수 있는 주소라서 길이를 자른다. 문장 내용은 화면이 보내지 않는다."""
    p = payload if isinstance(payload, dict) else {}
    event = str(p.get("event") or "")[:MAX_UI_EVENT]
    if not event:
        return {"ok": False}
    data = p.get("data")
    try:
        if len(json.dumps(data, ensure_ascii=False, default=str)) > MAX_UI_DATA:
            data = {"cut": True}
    except (TypeError, ValueError):
        data = None
    write("ui", event, {"sid": str(p.get("sid") or "")[:40], "page": str(p.get("page") or "")[:20], "data": data})
    return {"ok": True}


class RequestLog:
    """모든 요청을 request 파일에 적는 미들웨어 (main.py: app.add_middleware(RequestLog)).
    경로와 응답 코드, 걸린 시간만 적는다 (요청 본문은 적지 않는다). 처리 못 한 예외는 error 파일에도 남긴다."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        start, seen = time.perf_counter(), {"status": None}

        async def send_and_note(message):
            if message.get("type") == "http.response.start":
                seen["status"] = message.get("status")
            await send(message)

        info = {"method": scope.get("method"), "path": scope.get("path"),
                "query": (scope.get("query_string") or b"").decode("utf-8", "replace")[:300]}
        try:
            await self.app(scope, receive, send_and_note)
        except Exception as e:
            seen["status"] = seen["status"] or 500
            error("request", e, info)
            raise
        finally:
            write("request", f"{info['method']} {info['path']}", {**info, "status": seen["status"], "ms": round((time.perf_counter() - start) * 1000, 1)})


try:
    from fastapi import APIRouter, Body
except ImportError:                                        # fastapi 가 없어도 위의 함수들은 쓸 수 있다
    router = None
else:
    router = APIRouter()

    @router.post("/log/ui", include_in_schema=False)       # 화면 동작 기록 (화면이 결과를 기다리지 않고 보낸다)
    def log_ui(body: dict = Body(...)):
        return handle_ui(body)
