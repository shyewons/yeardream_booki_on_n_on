"""DB 접속 (MySQL). 책·글 목록을 불러오는 쪽(books_repo.py)에서만 쓴다.

접속 정보는 환경변수 DATABASE_URL 에서 읽는다. 이 폴더에 .env 파일을 만들어 적어 둬도 된다.
    DATABASE_URL=mysql+pymysql://DB사용자:DB비밀번호@127.0.0.1:3307/app_db
SSH 터널이 켜져 있어야 한다 (README_UI.md 참고).

sqlalchemy 는 실제로 DB를 부를 때만 불러온다.
→ 설치돼 있지 않아도 화면·교정 데모는 그대로 뜨고, DB 주소(/api/...)만 503 으로 안내한다.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


class DBNotConfigured(RuntimeError):
    """접속 정보나 라이브러리가 없을 때."""


_UNAVAILABLE = "DB에 연결하지 못했습니다. SSH 터널이 켜져 있는지, DATABASE_URL이 맞는지 확인하세요."   # 개발자용 (로그 · 콘솔)


class DBUnavailable(RuntimeError):
    """DB 를 쓰지 못할 때. 화면에 보일 문구가 메시지이고, status 는 돌려줄 HTTP 코드다 (books_api._guard).
    접속 정보는 있는데 DB에 닿지 못하거나(터널이 꺼진 경우 등), 아래 DBError 처럼 SQL 이 실패한 경우."""
    status = 503
    code = None


# ── DB 오류 나누기 (2026-11-19) ──
# 예전에는 SQL 오류가 모두 '연결하지 못했습니다'로 보여서, 칸이 없는 경우(Unknown column)도 터널 문제처럼 보였다.
# MySQL 오류 번호로 나눠 아이에게는 쉬운 문구와 짧은 오류 코드(예: DB-1054)만 보이고, 원문은 로그(error 파일)와 서버 콘솔에 남긴다.
_KINDS = {
    "connect":  (503, "서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요."),           # 터널 · 서버 꺼짐, 접속 정보 틀림
    "busy":     (503, "다른 저장과 겹쳤어요. 잠시 뒤 다시 해 주세요."),                # 잠금 대기 · 교착
    "mismatch": (500, "지금은 이 기능을 쓸 수 없어요. 어른께 알려 주세요."),           # DB 와 코드가 안 맞음 (칸 · 표 없음, SQL 문법)
    "other":    (500, "문제가 생겼어요. 다시 해 주세요."),                             # 그 밖
}
_CODES = {
    "connect": {1044, 1045, 1049, 2002, 2003, 2005, 2006, 2013, 2055},   # 권한 · 비밀번호 · DB 없음 · 서버에 못 닿음 · 연결 끊김
    "busy": {1205, 1213},                                                # 잠금 대기 시간 초과 · 교착
    "mismatch": {1054, 1064, 1136, 1146, 1364},                          # 칸 없음 · SQL 문법 · 칸 수 · 표 없음 · 기본값 없는 칸
}


class DBError(DBUnavailable):
    """SQL 이 실패했을 때. kind: connect / busy / mismatch / other, code: 'DB-1054' 같은 짧은 코드, raw: DB 가 준 원문 (로그용)."""

    def __init__(self, kind, number, raw):
        self.kind, self.raw = kind, raw
        self.status, text = _KINDS[kind]
        self.code = f"DB-{number}" if number else ("DB-연결" if kind == "connect" else "DB-기타")
        super().__init__(f"{text} (오류 코드: {self.code})")


def _db_error(e):
    """sqlalchemy 오류를 DBError 로 바꾼다. 연결 문제면 개발자용 안내(_UNAVAILABLE)를 콘솔에도 찍는다."""
    from sqlalchemy.exc import InterfaceError
    orig = getattr(e, "orig", None)
    args = getattr(orig, "args", ()) or ()
    number = args[0] if args and isinstance(args[0], int) else None
    kind = next((k for k, codes in _CODES.items() if number in codes), None)
    if kind is None:
        kind = "connect" if isinstance(e, InterfaceError) or number is None and "connect" in str(e).lower() else "other"
    raw = str(orig if orig is not None else e)[:500]
    print(f"[db] {kind} {number or ''} {raw}" + (f"\n     {_UNAVAILABLE}" if kind == "connect" else ""))
    return DBError(kind, number, raw)


def _load_dotenv():
    """같은 폴더의 .env 를 읽어 환경변수로 넣는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = re.split(r"\s+#", val, maxsplit=1)[0]   # 값 뒤 주석 ( #...) 은 뗀다. 비밀번호 안의 # 처럼 붙어 있는 건 그대로
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise DBNotConfigured("DATABASE_URL이 설정되지 않았습니다 (.env 파일 또는 환경변수).")
        try:
            from sqlalchemy import create_engine
        except ImportError as e:
            raise DBNotConfigured("sqlalchemy가 설치돼 있지 않습니다: pip install sqlalchemy pymysql cryptography") from e
        kwargs = dict(pool_pre_ping=True, pool_recycle=280)
        if url.startswith("mysql"):
            # DB 서버는 UTC 라서, 이 접속에서 NOW() 같은 자동값이 한국 시간으로 나오게 한다
            kwargs["connect_args"] = {"connect_timeout": 10, "init_command": "SET time_zone = '+09:00'"}
        _engine = create_engine(url, **kwargs)
    return _engine


def query(sql, params=None):
    """SQL 을 실행해 행 목록(딕셔너리)을 돌려준다. 값은 :이름 으로 넣는다.
    예) query("SELECT * FROM books WHERE id = :id", {"id": 3})"""
    engine = get_engine()
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    try:
        with engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params or {})]
    except DBAPIError as e:                          # 연결 · SQL 오류 모두 (나누기는 _db_error)
        raise _db_error(e) from e


class Conflict(RuntimeError):
    """같은 값이 이미 있어서 넣지 못할 때 (UNIQUE 중복)."""


class _Tx:
    """run_in_transaction 안에서 쓰는 도구. 안에서 한 일은 모두 성공하면 함께 저장되고, 하나라도 실패하면 함께 취소된다."""

    def __init__(self, conn, text, integrity_error):
        self._conn, self._text, self._integrity = conn, text, integrity_error

    def query(self, sql, params=None):
        return [dict(r._mapping) for r in self._conn.execute(self._text(sql), params or {})]

    def execute(self, sql, params=None):
        """INSERT/UPDATE/DELETE. 바뀐 행 수를 돌려준다."""
        try:
            return self._conn.execute(self._text(sql), params or {}).rowcount
        except self._integrity as e:
            raise Conflict(str(e)) from e

    def insert(self, sql, params=None):
        """INSERT. 새로 생긴 행의 번호(id)를 돌려준다."""
        try:
            return self._conn.execute(self._text(sql), params or {}).lastrowid
        except self._integrity as e:
            raise Conflict(str(e)) from e


def run_in_transaction(fn):
    """fn(tx) 를 한 묶음(트랜잭션)으로 실행한다. 중간에 오류가 나면 그 안에서 바꾼 것을 모두 되돌린다.
    예) run_in_transaction(lambda tx: tx.insert("INSERT INTO ...", {...}))"""
    engine = get_engine()
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, IntegrityError
    try:
        with engine.begin() as conn:
            return fn(_Tx(conn, text, IntegrityError))
    except DBAPIError as e:                          # 연결 · SQL 오류 모두 (UNIQUE 중복은 위 _Tx 가 Conflict 로 바꾼다)
        raise _db_error(e) from e
