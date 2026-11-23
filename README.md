# 북실북실 — 아이와 함께 쓰는 일기 · 동화 책

아이가 한 문장씩 일기와 동화를 쓰면, 맞춤법을 고쳐 주고 왜 고쳤는지 쉬운 말로 알려 주는 웹 앱입니다.
쓴 글은 목장의 동물(책)마다 모이고, 꾸준히 쓰면 캐릭터 옷을 선물로 받고, 다 쓴 책은 PDF로 저장해 인쇄할 수 있습니다.

| 폴더 | 내용 |
|---|---|
| `frontend/` | 화면 (React 19 + Vite). 자세한 구조는 [frontend/README.md](frontend/README.md) |
| `backend/` | 서버 (FastAPI + MySQL) 와 맞춤법 교정 파이프라인. 주소 · 설정 · 로그는 [backend/README.md](backend/README.md) |
| `analysis/` | 맞춤법 근거 검색용 벡터 DB(chroma_db)를 만들 때 쓴 분석 자료 |

## 한눈에 보는 실행 순서

```
① MySQL 에 app_db 만들기 → ② 표 만들기 SQL 실행 → ③ backend/.env 채우기
→ ④ 백엔드 켜기 (터미널 1) → ⑤ 프론트 켜기 (터미널 2) → ⑥ 브라우저로 http://localhost:5173
```

준비물: **Python 3.10 이상**, **Node.js 22 이상** (Vite 8: 20.19 이상), **MySQL 8**.
교정 모델까지 돌리려면 메모리 16GB 이상과 GPU(엔비디아) 또는 Apple Silicon 맥을 권장합니다. 모델 없이도 화면 흐름은 모두 돌아갑니다(아래 '모델 없이 실행').

### ① DB 만들기

MySQL 에 접속해 데이터베이스를 하나 만듭니다.

```sql
CREATE DATABASE app_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### ② 표 만들기 (처음 한 번)

`backend/temp/` 의 SQL 을 **이 순서대로** 실행합니다 (DBeaver · MySQL Workbench 에서 파일을 열어 실행하거나, 터미널에서 `mysql -u 사용자 -p app_db < 파일`).

| 순서 | 파일 | 하는 일 |
|---|---|---|
| 1 | `schema.sql` | 사용자 · 책 · 글 · 문장 · 교정 · 동화 주제 표를 만들고 동화 주제 10개를 넣습니다 |
| 2 | `schema_rewards.sql` | 보상 표(옷 · 받은 기록 · 가진 옷 · 입은 옷)를 만듭니다 |
| 3 | `seed_clothes.sql` | 선물로 줄 옷 43벌을 넣습니다 (마지막 줄 결과가 diary 10, fairy 33 이면 성공) |
| (선택) | `seed_dummy.sql` | 목록 · 쪽 넘기기를 시험할 더미 사용자와 책 |

> `schema.sql` 은 표를 지우고 다시 만듭니다. **이미 쓰고 있는 DB 에서는 실행하지 마세요.**

### ③ 백엔드 설정 (`backend/.env`)

`backend/.env.example` 을 같은 폴더에 `.env` 로 복사하고 `DATABASE_URL` 을 내 MySQL 에 맞게 고칩니다.

```
DATABASE_URL=mysql+pymysql://사용자:비밀번호@127.0.0.1:3306/app_db
```

- 비밀번호에 `@ : / #` 같은 기호가 있으면 `%40` 처럼 바꿔 적습니다.
- 그 밖의 값(모델 켜기, 모델 크기 등)은 `.env.example` 에 설명이 있습니다. 값 뒤에 ` # 주석` 을 붙여도 됩니다.
- `.env` 는 비밀번호가 들어 있어 Git · 제출 파일에 넣지 않습니다.

### ④ 백엔드 켜기 (터미널 1)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload           # http://127.0.0.1:8000 (API 문서: /docs)
```

`http://127.0.0.1:8000` 을 열어 "백엔드 서버가 작동 중이에요"가 보이면 됩니다.

### ⑤ 프론트 켜기 (터미널 2)

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

### ⑥ 써 보기

브라우저로 **http://localhost:5173** 을 엽니다.
시작하기 → 별명 만들기 → 목장에서 '새 책 만들기'(일기 / 동화) → 한 문장씩 쓰기 → 목록의 '책 출력하기'로 책 보기 · PDF 저장.
'나의 기록'에서 이번 주 기록, 최근 고친 문장, 옷장을 볼 수 있습니다.

## 모델 켜기 (맞춤법 교정 · 설명 · 표현 추천)

기본은 **모델 없이** 임시 응답으로 돕니다 (`USE_MODELS=0`). 화면에 '모델이 꺼져 있다'는 안내가 나옵니다.
진짜 교정을 보려면:

1. `pip install -r requirements-models.txt` (Windows 는 먼저 `$env:PYTHONUTF8="1"`)
2. 맞춤법 근거 검색 DB `chroma_db/` 를 `backend/` 안에 둡니다 (제출 파일에 들어 있습니다. 다른 곳이면 `.env` 의 `DIARY_DB_PATH`)
3. `.env` 에 `USE_MODELS=1`
4. 설명 모델 크기: `EXPLAIN_LLM=small`(기본, Kanana 1.5 2.1B) 또는 `large`(Kanana 2 3B, GPU · 맥 권장)
5. 백엔드를 다시 켭니다. **처음 켤 때 모델을 내려받느라 몇 분 걸립니다** (터미널에 `[preload] … 완료` 가 나오면 준비 끝)

장치는 엔비디아 GPU → 맥 GPU(mps) → CPU 순서로 알아서 고릅니다. 문제가 있으면 `.env` 에 `MODEL_DEVICE=cpu`.

| 단계 | 하는 일 | 모델 |
|---|---|---|
| ① 교정 | 맞춤법 고친 문장 만들기 | `j5ng/et5-typos-corrector` |
| ② 바뀐 곳 찾기 | 원문과 비교해 고친 곳 뽑기 (아이 문장부호는 그대로) | 규칙 |
| ③ 유형 구분 | 띄어쓰기 · 표기 등 유형과 검색어 | 규칙 · 형태소 분석(Kiwi) |
| ④ 근거 찾기 | 한글 맞춤법 조항 검색 | `nlpai-lab/KURE-v1` + chroma_db |
| ⑤ 설명 · 표현 추천 | 아이용 설명, 동화 다른 표현 2개 | Kanana (small / large) |

## 다른 기기(태블릿)에서 열기

같은 네트워크(또는 Tailscale 같은 사설 연결)에 있는 기기에서 열 수 있습니다. 백엔드 · DB · 모델은 켠 컴퓨터에서 돌고, 그 기기는 화면만 띄웁니다.

```bash
npm run dev -- --host               # 터미널에 나오는 Network 주소(http://IP:5173)로 접속
```

태블릿의 필기 입력(아이패드 스크리블, 윈도우 펜, S펜)으로 글쓰기 칸에 손글씨를 쓸 수 있습니다.

## 자주 생기는 문제

| 증상 | 확인할 것 |
|---|---|
| "서버에 연결하지 못했어요" | 백엔드(④)가 켜져 있는지 |
| "(오류 코드: DB-…)" · 503 | MySQL 이 켜져 있는지, `.env` 의 `DATABASE_URL` 주소 · 비밀번호 · 포트 |
| 옷장 · 선물이 비어 있음 | ②의 `schema_rewards.sql` · `seed_clothes.sql` 을 실행했는지 |
| 교정이 너무 느림 / 메모리 부족 | `EXPLAIN_LLM=small`, 첫 요청은 모델을 불러오느라 느립니다 |
| `.env` 를 고쳤는데 그대로 | 백엔드를 껐다 켜기 (`--reload` 는 `.env` 를 다시 읽지 않습니다) |

## 개인정보

- `backend/logs/` 에는 아이가 쓴 문장이 그대로 남습니다(`writing_날짜.log`). Git 과 제출 파일에 넣지 않습니다.
- 사용자는 별명 + 브라우저에 보관하는 토큰으로 구분하고, DB 에는 토큰의 해시만 저장합니다.
