# Frontend

아이가 쓰는 화면 (React 19 + Vite 8). 실행은 저장소 맨 위 [README](../README.md) 의 ⑤를 봅니다.

```bash
npm install
npm run dev            # http://localhost:5173  (다른 기기에서 열 때: npm run dev -- --host)
npm run lint           # 코드 검사
npm run build          # 배포용 파일 (dist/)
```

백엔드 주소는 쓰지 않습니다. `vite.config.js` 의 프록시가 `/api`, `/validate`, `/correct`, `/suggest`, `/question`, `/log` 요청을 `http://127.0.0.1:8000` 으로 넘깁니다.

## 화면

화면 전환은 모두 `App.jsx` 가 합니다 (`page` 값 하나로 지금 화면을 고르고, 각 화면은 받은 함수(props)만 부릅니다).

| 화면 | 파일 | 하는 일 |
|---|---|---|
| 시작 | `StartPage.jsx` | 토큰 확인하는 동안 게이지, 끝나면 '시작하기' |
| 별명 | `NicknamePage.jsx` | 처음 들어온 아이의 별명 만들기 (토큰 발급) |
| 목장 | `HomeListPage.jsx` | 내 책(동물) 목록, 새 책 만들기, 나의 기록 |
| 새 책 만들기 | `CreateBookPage.jsx` | 일기 / 동화 고르기 → 동화 주제(추천 3개 · 내가 정할래요) → 이름 |
| 글 목록 | `PostListPage.jsx` | 일기: 날짜 목록 · 오늘 일기 버튼 / 동화: 장 목록 · 선물 상자(3 · 6 · 10장) · 책 출력하기 |
| 글쓰기 | `WritePage.jsx` + `DiaryWriteView.jsx` | 한 문장씩 쓰기 → 검사 → 교정 → (동화) 표현 고르기. 왼쪽 쪽 '내가 쓴 글', 오른쪽 쪽 문장 쓰기 |
| 글 보기 | `PostDetailPage.jsx` | 쓴 글 읽기, 이전 · 다음, 고쳐쓰기 |
| 책 출력 | `BookPrintPage.jsx` | 책 한 권을 펼친 책으로 넘겨 보기, 'PDF로 저장'(브라우저 인쇄, A4 가로 한 장에 한 쪽) |
| 나의 기록 | `DashboardPage.jsx` | 이번 주 기록, 일기 주간 선물 받기, 고른 표현 · 다시 볼 맞춤법 |
| 최근 고친 문장 · 옷장 | `RecentFixesPage.jsx` · `WardrobePage.jsx` | 나의 기록 안에서 여는 화면 |

## 그 밖의 파일

| 파일 | 하는 일 |
|---|---|
| `writer.js` | 글쓰기 화면의 동작 전부 (검사 · 교정 · 저장 · 순서 · 임시저장 · 동화 장 · 표현 고르기). `WritePage.jsx` 는 이 상태를 그리기만 합니다 |
| `api.js` | 서버 요청 도우미 (토큰 헤더, 오류 코드 `서버-연결` · `HTTP-xxx` · `DB-xxxx`) |
| `useLoad.js` | 화면이 자료를 불러올 때 쓰는 공통 함수 (불러오는 중 · 실패 · 다시 시도) |
| `format.js` | 날짜 · 시각 · 장 번호 만들기 |
| `common.css` · `index.css` · `*.css` | 공통 모양과 화면별 모양 |
| `assets/` | 배경 · 캐릭터 · 아이콘 그림과 글꼴 (Paperlogy) |
