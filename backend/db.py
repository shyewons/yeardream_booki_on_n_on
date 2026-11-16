"""DB 접속 (MySQL). 책·글 목록을 불러오는 쪽(books_repo.py)에서만 쓴다.

접속 정보는 환경변수 DATABASE_URL 에서 읽는다. 이 폴더에 .env 파일을 만들어 적어 둬도 된다.
    DATABASE_URL=mysql+pymysql://DB사용자:DB비밀번호@127.0.0.1:3307/app_db
SSH 터널이 켜져 있어야 한다 (README_UI.md 참고).

sqlalchemy 는 실제로 DB를 부를 때만 불러온다.
→ 설치돼 있지 않아도 화면·교정 데모는 그대로 뜨고, DB 주소(/api/...)만 503 으로 안내한다.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


class DBNotConfigured(RuntimeError):
    """접속 정보나 라이브러리가 없을 때."""


_UNAVAILABLE = "DB에 연결하지 못했습니다. SSH 터널이 켜져 있는지, DATABASE_URL이 맞는지 확인하세요."


class DBUnavailable(RuntimeError):
    """접속 정보는 있는데 DB에 닿지 못할 때 (터널이 꺼진 경우 등)."""


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
    from sqlalchemy.exc import InterfaceError, OperationalError
    try:
        with engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params or {})]
    except (OperationalError, InterfaceError) as e:
        raise DBUnavailable(_UNAVAILABLE) from e


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
    from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
    try:
        with engine.begin() as conn:
            return fn(_Tx(conn, text, IntegrityError))
    except (OperationalError, InterfaceError) as e:
        raise DBUnavailable(_UNAVAILABLE) from e
