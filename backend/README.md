# Backend

FastAPI 서버. 책·글 목록과 저장(`/api/...`), 글쓰기 검사·교정·질문(`/validate` 등), 보상·옷장·나의 기록, 책 출력을 맡는다.

처음 받아서 DB 만들기부터 실행까지는 저장소 맨 위 [README](../README.md) 를 따라 하면 된다. 아래는 서버만 켤 때.

## 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload        # http://127.0.0.1:8000  (API 문서: /docs)
```

화면은 `frontend` 폴더에서 `npm install` 후 `npm run dev` → http://localhost:5173 에서 봅니다. `http://127.0.0.1:8000` 을 열면 서버가 작동 중이라는 안내만 나옵니다.

- 기본은 **모델 없이** 임시 노드(`demo_nodes.py`)로 돈다. 교정 모델까지 돌리려면 `pip install -r requirements-models.txt` 후 `USE_MODELS=1`.
- 동화 표현 추천(`/suggest`): 모델을 켜면 `diary_pipeline/explain.py` 의 표현 생성(Kanana, 설명문과 같은 모델)으로 새 표현 2개와 한 줄 설명을 만든다.
  모델이 꺼져 있으면 `demo_nodes.py` 의 낱말표로 임시 예시를 주고, 화면에 "모델이 꺼져 있어 임의로 바꾼 예시"라는 안내가 나온다.
  언제 추천할지는 `STORY_SUGGEST_ON`(`all` 기본: 고친 문장에도 / `no_correction`: 맞춤법이 맞은 문장에만)으로 정한다.
- 설명문 · 표현 추천 모델 크기: `.env` 의 `EXPLAIN_LLM=small`(기본, Kanana 1.5 2.1B) / `large`(Kanana 2 3B). 장치는 cuda → mps(맥) → cpu 순서로 자동, `MODEL_DEVICE=cpu` 로 강제 (`diary_pipeline/config.py` · `models.py`).
- DB 주소(`/api/...`)는 `backend/.env`가 있어야 한다. `.env.example`을 `.env`로 복사해 `DATABASE_URL`을 채운다. 없으면 그 주소들만 503. 값 뒤에 ` # 주석`을 붙여도 된다(`db.py` 가 뗀다).
  - 학습용 클라우드 DB는 SSH 터널을 먼저 켠다: `ssh -N -L 3307:127.0.0.1:3306 이름@주소 -p 포트`
- 프론트(React)는 `frontend`에서 `npm run dev`. `vite.config.js`의 프록시가 API 요청을 이 서버로 넘긴다.

## 파일

| 파일 | 하는 일 |
|---|---|
| `main.py` | 서버 시작점. 아래 라우터를 붙인다 |
| `auth.py` | 요청 헤더 `X-User-Token`으로 지금 사용자 정하기 (토큰은 해시로만 저장) |
| `users_api.py` · `users_repo.py` | `/api/users` 별명 만들기·토큰 확인, 별명 검사 |
| `books_api.py` | `/api/...` 주소 (책·글 목록, 글 열기, 문장 저장·끼워 넣기·순서 바꾸기, 이야기 저장) |
| `books_repo.py` | 위 주소가 쓰는 DB 쿼리. 지금 사용자(토큰 주인 또는 더미), 쪽당 개수, 시간(KST) 규칙, 문장마다 동화 주제 저장, 일기 하루치 달성(`day_done_at`) |
| `reward_rules.py` | 보상 기준 숫자 (일기 하루 3문장 · 지난 날짜 3일 · 주 5일, 동화 장 3문장 · 장 보상 3·6·10 · 끝내기 3장 · 중간 묻기 없음(100장에서만) · 최대 100장 · 장 목록 한 쪽 10장) |
| `progress_repo.py` | 보상 코드가 부르는 세는 함수 (주간 하루치, 동화 장 보상 구간 · 완성, 주제별 문장 수). 판단 · 받기는 하지 않는다 |
| `rewards_api.py` · `rewards_repo.py` | 일기 주간 선물 · 동화 장 선물 받기, 옷장(가진 옷 · 입히기). 두 번 받기는 409 |
| `dashboard_api.py` · `dashboard_repo.py` | 나의 기록(이번 주 일기 날 수 · 고른 표현 · 다시 볼 맞춤법 · 캐릭터), 최근 고친 문장 |
| `db.py` | `.env` 읽기(값 뒤 주석은 뗌), DB 접속, DB 오류 나누기(연결 · 잠깐 막힘 503 / 코드와 DB 불일치 500, 화면에 `DB-번호`) |
| `writing_api.py` | `/question` `/topics` `/validate` `/correct` `/suggest` (예전 시연용 `app.py`) |
| `demo_nodes.py` | 모델 없이 돌릴 때 쓰는 임시 노드, 동화 표현 추천 임시 낱말표 |
| `diary_pipeline/` | 유효성 검사(`input_validation.py`)와 교정 파이프라인 |
| `devlog.py` | 개발용 로그 (아래 '로그' 참고), `POST /log/ui` |
| `temp/schema.sql` · `temp/schema_rewards.sql` | 표 만들기 (글쓰기 쪽 + 동화 주제 / 보상 쪽. 보상 쪽은 팀 DB 를 `rewards_repo.py` 에 맞춰 다시 적은 정의) |
| `temp/seed_clothes.sql` · `temp/seed_dummy.sql` · `temp/db_check.py` | 선물 옷 43벌, 더미 데이터, 접속 확인 |

## 주소

| 주소 | 설명 |
|---|---|
| `GET /health` | 상태 확인 |
| `POST /api/users` | 별명 만들기 + 토큰 발급 `{"nickname": "몽실이"}` → `{"token", "nickname"}`. 규칙 위반 400, 중복 409 |
| `GET /api/users/me` | 토큰 확인 → `{"nickname"}`. 토큰 없음·틀림 401 |
| `GET /api/books?page=1` | 목장(책 목록, 최근에 만든 책부터, 한 쪽 6권). 응답에 별명 `owner` |
| `POST /api/books` | 책 만들기 `{"kind": "diary"\|"fairy", "title": "몽실", "fairy_topic_id": 3}`. 동화 주제가 `null` 이면 자유 주제 (DB 에는 `자유 주제` 줄 번호) |
| `PUT /api/books/{책}/topic` | 동화 주제 바꾸기 `{"fairy_topic_id": 3\|null}`. 첫 문장을 쓰기 전에만 (`books_repo.py` 의 `TOPIC_CHANGE_MAX_SENTENCES`) |
| `GET /api/books/{책}/entries?page=1` | 글 목록(최신 날짜부터, 한 쪽 10개). `writing`: 쓰던 글, `today`: 오늘 일기 `{id, status}`(없으면 null). 동화는 장 목록(1장부터 한 쪽 10장)과 `story`(모든 장의 문장 수 · 보상 진행 · 끝내기 정보) |
| `GET /api/books/{책}/print` | 책 출력: 책 한 권의 보이는 글과 문장을 한 번에 (동화는 1장부터, 일기는 오래된 날부터) + 주제 · 지은이 · 기간. 쪽 나누기는 화면이 한다 |
| `GET /api/entries/{글}` | 글 하나(문장·고친 곳·이전/다음 글 번호) |
| `GET /api/books/{책}/diary/{날짜}` | 그 날짜의 일기 |
| `POST /api/books/{책}/entries` | 글 열기(없으면 만들기) `{"date": "2026-11-16"}`. 동화는 장: `{"chapter": 3}` / `{"new_chapter": true}` / `{}` 마지막 장 |
| `PUT /api/entries/{글}/sentences/{번호}` | 문장 저장(같은 번호는 덮어쓰기). 동화 문장의 주제는 서버가 책에서 넣는다. 일기는 3문장째에 `day_done: true` |
| `POST /api/entries/{글}/sentences/{번호}/insert` | 문장 끼워 넣기 |
| `POST /api/entries/{글}/sentences/{번호}/move` | 문장 순서 바꾸기 `{"to": 3}` |
| `POST /api/entries/{글}/complete` | 이야기 저장하기(완성). 일기용 |
| `POST /api/books/{책}/finish` | 동화 이야기 끝내기 (3문장 이상 쓴 장이 3개 이상. 끝낸 뒤에는 다시쓰기만) |
| `POST /api/books/{책}/finish-later` | 동화: 끝낼지 물었을 때 '다음에 이어 쓸래요' `{"upto": 3}` (그 구간은 다시 묻지 않음) |
| `GET /api/topics?exclude=토끼,작은 용&others=2` | 동화 주제 추천 (DB `fairy_topics` 의 켜진 주제) → `{"pick", "others", "ids", "items": [{id, title, prompt, opening}]}` |
| `GET /question?passed=0&kind=fairy&topic=토끼&chapter=2` | 입력칸 위 질문 (동화 2장부터는 첫 문장도 앞 장에 이어서 묻는다) |
| `GET /topics?exclude=토끼,작은 용` | 동화 주제 추천 (코드 안 목록. 화면은 `/api/topics` 를 쓴다) |
| `POST /validate` | 유효성 검사 `{"user_input", "validation_attempt", "previous_sentences", "choice_picks", "kind"}` |
| `POST /correct` | 교정(단계별 NDJSON) `{"original_sentence"}` |
| `POST /suggest` | 동화 표현 추천(임시) `{"sentence"}` |
| `POST /log/ui` | 화면 동작 기록 `{"event", "sid", "page", "data"}` |
| `GET /api/dashboard` | 나의 기록 (이번 주 일기 날 수는 하루치 달성 `day_done_at` 기준, 일기 주간 선물 상태, 고른 표현, 다시 볼 맞춤법, 캐릭터) |
| `GET /api/dashboard/recent-fixes` | 최근 고친 문장 (교정을 받고 아이가 직접 다시 쓴 기록) |
| `POST /api/rewards/diary/claim` | 일기 주간 선물 받기 `{"week_start": "2026-11-16"}` |
| `GET /api/rewards/fairy/{책}` | 동화 장 선물 상자 `stages [{order, chapters, status locked\|claimable\|claimed, clothes}]` |
| `POST /api/rewards/fairy/{책}/claim` | 동화 장 선물 받기 `{"order": 1}` → `{clothes, fairy_reward}` |
| `GET /api/wardrobe` · `PUT /api/wardrobe/equip` | 옷장 보기 · 입히기 `{"slot": "hat", "clothes_id": 3\|null}` |

공통: 없는 것·남의 것 404, 잘못된 요청 400, 토큰 틀림 401, DB 미설정·접속 실패 503.
사용자: 요청 헤더 `X-User-Token`의 토큰 주인(`auth.py`)이고, 자기 목장·책만 보인다. 토큰 없이 오면 더미 한 명(`dummy_user`)으로 처리한다(시험용 화면 호환). 끄려면 `ALLOW_DUMMY_USER=0`.

## 설정을 고치는 곳

- 쪽당 개수, 더미 별명: `.env` 또는 `books_repo.py` 위쪽
- 유효성 기준(일기/동화): `diary_pipeline/input_validation.py` 맨 위 `KIND_RULES`, `KIND_MESSAGES`
- 동화 주제: DB `fairy_topics` 표 (요구사항정의서 '동화주제' 10개. `prompt` 쓰기 안내, `opening` 시작 상황, `is_active = 0` 이면 추천에서 빠진다). '내가 정할래요'는 `자유 주제` 줄(꺼져 있음)을 가리킨다. 표가 비면 `writing_api.py`의 `FAIRY_TOPICS`
- 동화 주제를 바꿀 수 있는 때: `books_repo.py`의 `TOPIC_CHANGE_MAX_SENTENCES` (0 = 첫 문장 전에만, `None` = 언제나)
- 동화 질문 문구: `writing_api.py`의 `FAIRY_FIRST`, `FAIRY_FIRST_FREE`(자유 주제), `FAIRY_CHAPTER_START`(2장부터 첫 문장), `FAIRY_NEXT`
- 설명문 · 표현 추천 모델: `.env` 의 `EXPLAIN_LLM` (목록은 `diary_pipeline/config.py` 의 `EXPLAIN_LLMS`), 장치 `MODEL_DEVICE`
- 검사에서 되묻는 문구(욕설 · 개인정보 · 인젝션 등): `diary_pipeline/input_validation.py` 의 `next_question`
- 보상 기준 숫자: `reward_rules.py`
- RAG 벡터 DB 위치: `DIARY_DB_PATH` (예: `../analysis/chroma_db`)
- 개발용 로그: 아래 '로그' 참고

## 로그

화면에는 보이지 않고 `backend/logs/`에 종류별·날짜별 파일로 쌓인다 (한 줄 = JSON 하나, `{"time", "user", "label", "data"}`). 깃에는 올라가지 않는다.

`user`는 그 요청을 보낸 사용자의 번호(`users.id`)다. 별명은 적지 않는다. 서버 시작 기록이나 사용자를 알기 전의 요청은 `null`이다. 토큰 없이 온 요청은 더미 사용자 번호가, 토큰이 있는 요청은 사용자를 찾은 뒤(`books_api` · `users_api`의 `devlog.set_user`) 그 번호가 붙는다. 별명 만들기 요청처럼 사용자를 찾기 전에 끝나는 요청은 `null`이다.

| 파일 | 내용 |
|---|---|
| `request_날짜.log` | 모든 요청: 방식, 경로, 응답 코드, 걸린 시간(ms). 요청 본문은 없음 |
| `error_날짜.log` | DB 접속 실패, 모델 오류, 처리 못 한 예외(traceback) |
| `action_날짜.log` | 저장 동작: 책 만들기, 글 열기, 문장 저장·끼워 넣기·순서 바꾸기, 이야기 저장, 거절된 요청. 번호·상태·개수만 |
| `model_날짜.log` | 교정 한 번의 실행 모드와 단계별 걸린 시간(ms) |
| `ui_날짜.log` | 화면 동작: 화면 이동, 주제 고르기, 표현 선택, 다시쓰기, 끼워 넣기, 순서 바꾸기, 저장 실패 등. `sid`로 화면을 연 한 번을 묶는다 |
| `server_날짜.log` | 서버가 켜질 때의 설정(모델 모드, DB 설정 여부 등) |
| `writing_날짜.log` | 검사·교정·표현 추천의 요청과 결과. **아이가 쓴 문장이 그대로 들어가는 유일한 파일** |

- 전부 끄기: `DEV_LOG=0`. 폴더 바꾸기: `LOG_DIR=경로`.
- 오래된 파일은 자동으로 지우지 않는다.
- 화면 동작 이름은 `frontend/src` 의 `track("이름", {...})`(`api.js`)에서 찾을 수 있다. 예전 시험용 화면 `frontend/temp` 도 같은 주소(`POST /log/ui`)로 보낸다.
