# 북실북실 — 아이와 함께 쓰는 일기 · 동화 책

아이가 한 문장씩 일기와 동화를 쓰면, 맞춤법을 고쳐 주고 왜 고쳤는지 쉬운 말로 알려 주는 웹 앱입니다.
쓴 글은 목장의 동물(책)마다 모이고, 꾸준히 쓰면 캐릭터 옷을 선물로 받고, 다 쓴 책은 PDF로 저장해 인쇄할 수 있습니다.

| 폴더 | 내용 |
|---|---|
| `frontend/` | 화면 (React 19 + Vite). 자세한 구조는 [frontend/README.md](frontend/README.md) |
| `backend/` | 서버 (FastAPI + MySQL) 와 맞춤법 교정 파이프라인. 주소 · 설정 · 로그는 [backend/README.md](backend/README.md) |
| `analysis/` | 모델 평가 자료 (맞춤법 교정 모델 비교 · 근거 검색(RAG) · 동화 sLLM). 자세한 내용은 [analysis/README.md](analysis/README.md) |

## 화면 미리보기

<p align="center"><img src="docs/screenshots/00-farm.jpg" width="640" alt="일기 책은 양, 동화 책은 알파카로 목장에 모여 있는 첫 화면"></p>
<p align="center">목장: 책 한 권이 동물 한 마리 (일기는 양, 동화는 알파카). '새 책 만들기'와 '나의 기록'으로 들어갑니다</p>

| 일기 · 맞춤법 교정 | 문장 쓰기 · 입력 검사 |
|---|---|
| <img src="docs/screenshots/01-diary-correction.jpg" width="420" alt="고친 곳을 표시하고 맞춤법 규정에 근거한 이유를 보여 주는 일기 쓰기 화면"> | <img src="docs/screenshots/01-write-guardrail.jpg" width="420" alt="쓸 수 없는 말이 표시되고 다시 쓰도록 안내하는 문장 쓰기 화면"> |
| 한 문장씩 쓰면 고친 곳을 표시하고, 맞춤법 규정을 근거로 왜 고쳤는지 쉬운 말로 알려 줍니다 | 대필 요청 · 프롬프트 무시 같은 말은 그 부분만 표시하고 다시 쓰게 합니다 |
| **동화 · 다른 표현 고르기** | **표현을 고른 뒤 이어 쓰기** |
| <img src="docs/screenshots/02-fairy-expression.jpg" width="420" alt="내가 쓴 문장과 다른 표현 중에서 고르는 동화 쓰기 화면"> | <img src="docs/screenshots/03-fairy-picked.jpg" width="420" alt="고른 표현이 반영되고 다음 문장을 쓰는 화면"> |
| 고칠 곳이 없으면 더 생생한 표현을 제안하고, 아이가 고르거나 원래 문장을 지킵니다 | 고른 문장이 책에 들어가고 다음 문장을 이어 씁니다 |
| **책 출력 · 표지** | **책 출력 · 본문** |
| <img src="docs/screenshots/05-book-cover.jpg" width="420" alt="동화책 표지와 이야기 주제 쪽"> | <img src="docs/screenshots/06-book-pages.jpg" width="420" alt="장 제목과 문장이 쪽마다 나뉜 동화책 본문"> |
| 표지 · 주제 쪽부터 펼친 책으로 넘겨 보고, 'PDF로 저장'으로 A4 에 인쇄합니다 | 문장이 쪽 크기에 맞춰 나뉘고, 장(날짜)마다 새 쪽에서 시작합니다 |

<p align="center"><img src="docs/screenshots/04-records.jpg" width="640" alt="이번 주 일기 · 선물 · 다시 살펴볼 맞춤법을 보여 주는 나의 기록 화면"></p>
<p align="center">나의 기록: 이번 주 일기 · 선물 진행, 다시 살펴볼 맞춤법, 내가 골라 쓴 표현, 옷장</p>

## 데이터 구조 (ERD)

<p align="center"><a href="docs/erd.png"><img src="docs/erd.png" width="900" alt="users → books → entries → sentences → corrections 와 동화 주제 · 보상 표의 관계를 보여 주는 ERD"></a></p>

사용자 → 책(동물 한 마리) → 글(일기 하루 · 동화 한 장) → 문장 → 교정 순으로 이어지고, 보상 표(reward_claims · user_clothes · user_equipped_clothes)는 사용자 · 책 · 의상(clothes)을 가리킵니다. 그림을 누르면 크게 볼 수 있습니다.

> 아래 '실행 순서'가 **권장 실행 방법**입니다. 우리 팀이 발표 · 시연에 쓴 환경은 [팀 시연 환경 (참고)](#팀-시연-환경-참고)에 따로 적었습니다.

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
| 2 | `schema_rewards.sql` | 보상 표(옷 · 받은 기록 · 가진 옷 · 입은 옷)를 만듭니다. 팀 DB 의 보상 표를 코드(`rewards_repo.py`)에 맞춰 다시 적은 정의라, 길이 · 키 이름 같은 세부 조건은 팀 DB 와 조금 다를 수 있습니다 |
| 3 | `seed_clothes.sql` | 선물로 줄 옷 43벌을 넣습니다 (마지막 줄 결과가 diary 10, fairy 33 이면 성공) |
| (선택) | `seed_dummy.sql` | 목록 · 쪽 넘기기를 시험할 더미 사용자와 책 |

> `schema.sql` · `schema_rewards.sql` 은 표를 지우고 다시 만듭니다. **이미 쓰고 있는 DB 에서는 실행하지 마세요** (쓴 글 · 받은 옷이 모두 지워집니다).
> 처음부터 다시 만들 때는 보상 표가 사용자 · 책 표를 가리키고 있어서, `schema_rewards.sql` 맨 위의 `DROP TABLE` 네 줄을 먼저 실행한 뒤 1 → 2 → 3 순서로 실행합니다.

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
2. 맞춤법 근거 검색 DB `backend/chroma_db/` 는 저장소에 들어 있어 따로 만들 필요가 없습니다 (다른 곳에 두면 `.env` 의 `DIARY_DB_PATH`)
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

## 팀 시연 환경 (참고)

위 '실행 순서'와 같은 방법이고, 발표 · 시연 때 아래 값으로 켰습니다. 처음 실행한다면 위의 권장 방법(기본값)을 먼저 따라 해 주세요.

| 항목 | 권장(기본) | 팀 시연 |
|---|---|---|
| 서버 컴퓨터 | 아무 컴퓨터 (모델은 GPU · 맥 권장) | Apple Silicon 맥 (모델은 맥 GPU `mps` 로 자동 선택) |
| 모델 | `USE_MODELS=0` (임시 응답) | `USE_MODELS=1` |
| 설명 모델 | `EXPLAIN_LLM=small` (Kanana 1.5 2.1B) | `EXPLAIN_LLM=large` (Kanana 2 3B) |
| 백엔드 | `uvicorn main:app --reload` | 같음 |
| 프론트 | `npm run dev` | 같음 |
| 접속 기기 | 같은 컴퓨터의 브라우저 (`http://localhost:5173`) | 같음 |
| 입력 | 키보드 | 키보드 + 태블릿 펜(윈도우 필기 입력) |

- 시연 전에는 시연용 별명으로 새로 시작합니다. 같은 별명을 다시 쓰려면 DB 에서 그 별명의 사용자 · 책 · 글을 지우고, 브라우저에서는 시크릿 창을 쓰거나 개발자 도구 콘솔에서 `localStorage.removeItem('booksil_token')` 을 실행합니다.
- `EXPLAIN_LLM=large` 는 아래 [라이선스](#사용한-모델--데이터--에셋과-라이선스)의 표기 의무가 있습니다.

## 자주 생기는 문제

| 증상 | 확인할 것 |
|---|---|
| "서버에 연결하지 못했어요" | 백엔드(④)가 켜져 있는지 |
| "(오류 코드: DB-…)" · 503 | MySQL 이 켜져 있는지, `.env` 의 `DATABASE_URL` 주소 · 비밀번호 · 포트 |
| 옷장 · 선물이 비어 있음 | ②의 `schema_rewards.sql` · `seed_clothes.sql` 을 실행했는지 |
| 교정이 너무 느림 / 메모리 부족 | `EXPLAIN_LLM=small`, 첫 요청은 모델을 불러오느라 느립니다 |
| `.env` 를 고쳤는데 그대로 | 백엔드를 껐다 켜기 (`--reload` 는 `.env` 를 다시 읽지 않습니다) |

## 팀

| GitHub | 맡은 일 |
|---|---|
| [@shyewons](https://github.com/shyewons) | 팀장 · 일정과 팀 진행, 프로젝트 기본 구조(프론트 · 백엔드 시작), 화면 디자인 · 에셋 · 화면별 스타일, 별명 화면 연결, 문서 작성 |
| [@hihiimj](https://github.com/hihiimj) | 맞춤법 교정 파이프라인(et5 교정 · 근거 검색(RAG) · 설명 생성), 모델 평가(`analysis/`), 문서 작성 |
| [@taekgeun0816-creator](https://github.com/taekgeun0816-creator) | 별명 · 토큰, 별명 · 목장(책장) · 새 책 화면, 나의 기록(대시보드) · 의상 보상 · 옷장 |
| [@SnNiFe](https://github.com/SnNiFe) | 입력 검사(`input_validation.py`), 책 · 글 · 문장 백엔드와 DB 설계, 글 목록 · 글 보기 · 글쓰기 화면, 책 출력, 통합 · 문서 |

그 밖에도 기획 · 요구사항 정리 · 발표 준비 등은 함께 나눠 맡았습니다.

## 사용한 모델 · 데이터 · 에셋과 라이선스

이 저장소의 코드에는 아직 별도 라이선스를 정하지 않았습니다. 아래 외부 모델 · 데이터 · 에셋은 각각의 라이선스를 따릅니다 (2026-11-23 각 배포처에서 확인).

| 구분 | 이름 | 만든 곳 | 라이선스 |
|---|---|---|---|
| 맞춤법 교정 | [j5ng/et5-typos-corrector](https://huggingface.co/j5ng/et5-typos-corrector) | j5ng | Apache-2.0 |
| 설명 · 표현 추천 (small, 기본) | [kakaocorp/kanana-1.5-2.1b-instruct-2505](https://huggingface.co/kakaocorp/kanana-1.5-2.1b-instruct-2505) | 카카오 | Apache 2.0 |
| 설명 · 표현 추천 (large) | [kakaocorp/kanana-2-3b-instruct](https://huggingface.co/kakaocorp/kanana-2-3b-instruct) | 카카오 | [Kanana Open License](https://huggingface.co/kakaocorp/kanana-2-3b-instruct/blob/main/LICENSE) |
| 근거 검색 임베딩 | [nlpai-lab/KURE-v1](https://huggingface.co/nlpai-lab/KURE-v1) | 고려대학교 NLP&AI 연구실 (BAAI/bge-m3 기반) | MIT |
| 벡터 DB 만들 때 문장 나누기 | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | BAAI | MIT |
| 근거 문서 (chroma_db 의 원문) | [「'한글 맞춤법', '표준어 규정' 해설」(2018)](https://korean.go.kr/kornorms/refr/refrList.do) | 국립국어원 | `backend/chroma_db/` 에 해설서 문장 조각과 임베딩이 들어 있습니다 (원문 PDF 는 넣지 않음). 비영리 교육 목적으로 출처를 밝혀 사용 |
| 형태소 분석 | [Kiwi (kiwipiepy)](https://github.com/bab2min/kiwipiepy) | bab2min | 배포처 라이선스를 따름 |
| 글꼴 | [Paperlogy(페이퍼로지)](https://www.sandollcloud.com/free-font/21071/Paperlogy) | 이주임 · 김도균 / 피티앤 | SIL Open Font License 1.1 |
| 그림 (배경 · 캐릭터 · 아이콘 등, `frontend/src/assets/`) | 팀 디자인 | 팀 (AI 이미지 생성 도구를 활용해 제작 · 편집) | 팀 제작물 |
| 평가 데이터 (`analysis/`) | 맞춤법 평가 문장 | 팀 | 직접 만든 합성 문장 (실제 아동의 글 · 개인정보 없음) |

- **Kanana 2 (`EXPLAIN_LLM=large`)**: Kanana Open License 에 따라 이 모델로 만든 서비스는 웹사이트 · 화면 · 문서에 **"Powered by Kanana"** 를 표시해야 합니다. 또한 API · 온디바이스 등으로 제3자에게 제공 · 판매하려면 카카오의 별도 상업 라이선스가 필요합니다. 기본값 `small`(Kanana 1.5, Apache 2.0)에는 이 조건이 없습니다.
- 그 밖의 파이썬 · 자바스크립트 라이브러리(FastAPI, React, transformers, ChromaDB 등)는 각 패키지의 라이선스를 따릅니다 (`backend/requirements*.txt`, `frontend/package.json`).

Powered by Kanana

## 개인정보

- `backend/logs/` 에는 아이가 쓴 문장이 그대로 남습니다(`writing_날짜.log`). Git 과 제출 파일에 넣지 않습니다.
- 사용자는 별명 + 브라우저에 보관하는 토큰으로 구분하고, DB 에는 토큰의 해시만 저장합니다.
