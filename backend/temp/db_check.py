"""DB 연동 시험 스크립트.

1) 접속이 되는지 (SELECT 1)
2) 테이블 5개가 있는지
3) 사용자 → 책 → 글 → 문장 → 교정 순으로 한 줄씩 넣어 보고, 마지막에 ROLLBACK
   (연결 관계와 컬럼 이름이 맞는지만 보고, DB에는 아무것도 남기지 않습니다)

사용법 (Windows cmd):
    pip install sqlalchemy pymysql cryptography
    set DATABASE_URL=mysql+pymysql://사용자:비밀번호@127.0.0.1:3307/app_db
    python db_check.py
비밀번호에 @ : / 같은 기호가 있으면 %40 처럼 바꿔 넣어야 합니다.
"""
import os
import sys

from sqlalchemy import create_engine, inspect, text

url = os.environ.get("DATABASE_URL")
if not url:
    sys.exit("DATABASE_URL이 없습니다. set DATABASE_URL=mysql+pymysql://사용자:비밀번호@127.0.0.1:3307/app_db")

engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

# 1) 접속
with engine.connect() as conn:
    print("1) 접속 OK:", conn.execute(text("SELECT DATABASE(), VERSION()")).one())

# 2) 테이블
want = {"users", "books", "entries", "sentences", "corrections"}
have = set(inspect(engine).get_table_names())
print("2) 테이블:", sorted(want & have), "| 없음:", sorted(want - have) or "-")
if want - have:
    sys.exit("schema.sql을 먼저 실행하세요.")

# 3) 한 줄씩 넣어 보기 (끝에 ROLLBACK)
conn = engine.connect()
tx = conn.begin()
try:
    uid = conn.execute(text(
        "INSERT INTO users (nickname, token_hash) VALUES ('_check_', 'x')")).lastrowid
    bid = conn.execute(text(
        "INSERT INTO books (user_id, kind, title) VALUES (:u, 'diary', '몽실')"), {"u": uid}).lastrowid
    eid = conn.execute(text(
        "INSERT INTO entries (book_id, diary_date) VALUES (:b, CURDATE())"), {"b": bid}).lastrowid
    sid = conn.execute(text(
        "INSERT INTO sentences (entry_id, seq, original, revised, attempt_count, invalid_reasons, has_correction, correction_mode) "
        "VALUES (:e, 1, '오늘 학교에 갔다.', '오늘 학교에 갔다.', 1, JSON_ARRAY(), 0, 'none')"), {"e": eid}).lastrowid
    conn.execute(text(
        "INSERT INTO corrections (sentence_id, idx, start_pos, end_pos, before_text, after_text, explanation) "
        "VALUES (:s, 0, 0, 2, '오날', '오늘', '시험')"), {"s": sid})
    n = conn.execute(text("SELECT COUNT(*) FROM corrections WHERE sentence_id = :s"), {"s": sid}).scalar()
    print(f"3) 5개 표 입력 OK (교정 {n}줄) → ROLLBACK 합니다")
finally:
    tx.rollback()
    conn.close()
print("끝. DB에 남은 데이터는 없습니다.")
