"""지금 요청을 보낸 사람이 누구인지 (별명 + 임시 토큰, 로그인 없음).

흐름
  1. 01번 화면에서 별명을 만들면 서버가 토큰을 하나 발급한다 (users_api.py).
  2. 화면은 그 토큰을 브라우저에 보관하고, 요청마다 헤더 X-User-Token 에 실어 보낸다.
  3. 아래 미들웨어가 헤더의 토큰을 꺼내 두면, books_repo.current_user_id() 가 그 토큰으로 사용자를 찾는다.
     → 기존 /api/... 주소들은 고칠 필요 없이 '토큰 주인의 책'만 보게 된다.

DB에는 토큰 원문을 저장하지 않고 해시(sha256)만 저장한다 (schema.sql 의 users.token_hash).

토큰 없이 온 요청
  ALLOW_DUMMY_USER=1(기본)  → 예전처럼 더미 사용자(dummy_user)로 처리한다. frontend/temp 시험용 화면이 그대로 돈다.
  ALLOW_DUMMY_USER=0        → 401. React 화면만 쓰게 되면 0 으로 바꾼다.
토큰은 왔는데 맞는 사용자가 없으면 → 항상 401 (화면은 토큰을 지우고 01번 별명 화면으로 보낸다).
"""
import contextvars
import hashlib
import os

import db

TOKEN_HEADER = b"x-user-token"           # 헤더 이름 (HTTP 헤더는 대소문자를 가리지 않고, ASGI 에서는 소문자로 온다)
ALLOW_DUMMY_USER = os.environ.get("ALLOW_DUMMY_USER", "1") == "1"

_token = contextvars.ContextVar("user_token", default=None)


class InvalidToken(Exception):
    """토큰이 없거나(더미 사용 안 함) 맞는 사용자가 없을 때 → 401."""


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_token():
    """이번 요청의 X-User-Token 값. 없으면 None."""
    return _token.get()


def find_user_by_token(token):
    """토큰 주인 {"id", "nickname"}. 없으면 None."""
    rows = db.query("SELECT id, nickname FROM users WHERE token_hash = :h", {"h": hash_token(token)})
    return rows[0] if rows else None


def token_from_scope(scope):
    """ASGI 요청(scope)의 헤더에서 X-User-Token 값을 꺼낸다. 없으면 None. (DB는 묻지 않는다)"""
    for key, value in scope.get("headers") or []:
        if key == TOKEN_HEADER:
            return value.decode("latin-1").strip() or None
    return None


class UserTokenMiddleware:
    """요청 헤더의 X-User-Token 을 꺼내 current_token() 으로 읽을 수 있게 해 둔다.
    (순수 ASGI 미들웨어: 요청 본문을 건드리지 않아서 /correct 같은 스트리밍 응답에도 영향이 없다)"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        reset = _token.set(token_from_scope(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            _token.reset(reset)
