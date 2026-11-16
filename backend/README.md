# Backend

FastAPI 서버. 책·글 목록과 저장(`/api/...`), 글쓰기 검사·교정·질문(`/validate` 등)을 맡는다.

## 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload        # http://127.0.0.1:8000  (API 문서: /docs)
```

- 기본은 **모델 없이** 임시 노드(`demo_nodes.py`)로 돈다. 교정 모델까지 돌리려면 `pip install -r requirements-models.txt` 후 `USE_MODELS=1`.
- DB 주소(`/api/...`)는 `backend/.env`가 있어야 한다. `.env.example`을 `.env`로 복사해 `DATABASE_URL`을 채운다. 없으면 그 주소들만 503.
  - 학습용 클라우드 DB는 SSH 터널을 먼저 켠다: `ssh -N -L 3307:127.0.0.1:3306 이름@주소 -p 포트`
- 프론트(React)는 `frontend`에서 `npm run dev`. `vite.config.js`의 프록시가 API 요청을 이 서버로 넘긴다.

## 파일

| 파일 | 하는 일 |
|---|---|
| `main.py` | 서버 시작점. 아래 라우터를 붙인다 |
| `books_api.py` | `/api/...` 주소 (책·글 목록, 글 열기, 문장 저장·끼워 넣기·순서 바꾸기, 이야기 저장) |
| `books_repo.py` | 위 주소가 쓰는 DB 쿼리. 쪽당 개수, 더미 사용자, 시간(KST) 규칙 |
| `db.py` | `.env` 읽기, DB 접속 |
| `writing_api.py` | `/question` `/topics` `/validate` `/correct` `/suggest` (예전 시연용 `app.py`) |
| `demo_nodes.py` | 모델 없이 돌릴 때 쓰는 임시 노드, 동화 표현 추천 임시 낱말표 |
| `diary_pipeline/` | 유효성 검사(`input_validation.py`)와 교정 파이프라인 |
| `proto_pages.py` | **임시**: `frontend/temp`의 시험용 화면을 `/`, `/books`로 내보냄. React 화면이 완성되면 삭제 |
| `temp/schema.sql`, `temp/seed_dummy.sql`, `temp/db_check.py` | 테이블 만들기, 더미 데이터, 접속 확인 |

## 주소

| 주소 | 설명 |
|---|---|
| `GET /health` | 상태 확인 |
| `GET /api/books?page=1` | 목장(책 목록, 최근에 만든 책부터, 한 쪽 6권). 응답에 별명 `owner` |
| `POST /api/books` | 책 만들기 `{"kind": "diary"\|"fairy", "title": "몽실"}` |
| `GET /api/books/{책}/entries?page=1` | 글 목록(최신 날짜부터, 한 쪽 10개). `writing`: 쓰던 글 |
| `GET /api/entries/{글}` | 글 하나(문장·고친 곳·이전/다음 글 번호) |
| `GET /api/books/{책}/diary/{날짜}` | 그 날짜의 일기 |
| `POST /api/books/{책}/entries` | 글 열기(없으면 만들기) `{"date": "2026-11-16"}`, 동화는 생략 |
| `PUT /api/entries/{글}/sentences/{번호}` | 문장 저장(같은 번호는 덮어쓰기) |
| `POST /api/entries/{글}/sentences/{번호}/insert` | 문장 끼워 넣기 |
| `POST /api/entries/{글}/sentences/{번호}/move` | 문장 순서 바꾸기 `{"to": 3}` |
| `POST /api/entries/{글}/complete` | 이야기 저장하기(완성) |
| `GET /question?passed=0&kind=fairy&topic=고양이` | 입력칸 위 질문 |
| `GET /topics?exclude=고양이,용` | 동화 주제 추천 |
| `POST /validate` | 유효성 검사 `{"user_input", "validation_attempt", "previous_sentences", "choice_picks", "kind"}` |
| `POST /correct` | 교정(단계별 NDJSON) `{"original_sentence"}` |
| `POST /suggest` | 동화 표현 추천(임시) `{"sentence"}` |

공통: 없는 것·남의 것 404, 잘못된 요청 400, DB 미설정·접속 실패 503. 사용자는 지금 더미 한 명(`dummy_user`)이고, 로그인이 붙으면 `books_repo.current_user_id()`만 바꾼다.

## 설정을 고치는 곳

- 쪽당 개수, 더미 별명: `.env` 또는 `books_repo.py` 위쪽
- 유효성 기준(일기/동화): `diary_pipeline/input_validation.py` 맨 위 `KIND_RULES`, `KIND_MESSAGES`
- 동화 주제·질문 문구: `writing_api.py`의 `FAIRY_TOPICS`, `FAIRY_FIRST`, `FAIRY_NEXT`
- RAG 벡터 DB 위치: `DIARY_DB_PATH` (예: `../analysis/chroma_db`)
- 개발용 로그: `logs/dev_날짜.log` (아이가 쓴 문장이 들어가므로 올리지 않는다. 끄려면 `DEV_LOG=0`)
