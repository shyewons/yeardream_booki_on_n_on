import { useCallback, useEffect, useState } from "react";
import { api, clearToken, getToken } from "./api.js";
import NicknamePage from "./NicknamePage.jsx";      // 별명설정 페이지
import HomeListPage from "./HomeListPage.jsx";      // 목장(메인) 페이지
import CreateBookPage from "./CreateBookPage.jsx";  // 새 책 만들기 페이지
import PostListPage from "./PostListPage.jsx";      // 글 리스트 페이지
import DashboardPage from "./DashboardPage.jsx";    // 대시보드 페이지
import PostDetailPage from "./PostDetailPage.jsx";  // 작성한 글 조회 페이지
import WritePage from "./WritePage.jsx";            // 글쓰기 페이지
import StartPage from "./StartPage.jsx";            // 서비스 시작 화면


export default function App() {

    // [page, setPage] → 현재 보여줄 화면
    // checking: 서비스 시작 (사용자 확인 → 시작하기)
    // nickname: 별명 설정
    // home: 목장
    // createBook: 새 책 만들기
    // postList: 글 리스트 (책 한 권에 쓴 글 목록)
    // postDetail: 작성한 글 조회
    // write: 글쓰기
    const [page, setPage] = useState("checking");

    // 글 리스트 · 글 조회 · 글쓰기 화면이 쓰는 값
    // bookId: 목장에서 고른 책 번호
    // listPage: 글 리스트의 몇 번째 쪽인지 (글을 보고 돌아와도 보던 쪽이 유지된다)
    // entryId: 글 리스트에서 고른 글 번호
    const [bookId, setBookId] = useState(null);
    const [bookInfo, setBookInfo] = useState(null);
    const [listPage, setListPage] = useState(1);
    // homePage: 목장(책 목록)의 몇 번째 쪽인지 (책을 열었다가 목장으로 돌아와도 보던 쪽이 유지된다. 새 책 · 대시보드로 가면 1쪽)
    const [homePage, setHomePage] = useState(1);
    // writeDate: 글쓰기 화면에서 쓸 일기 날짜("2026-11-16"). 동화는 장("ch3" = 3장, "new" = 새 장, null = 마지막 장. format.js 의 chapterTarget)
    // justSaved: 방금 '이야기 저장하기'를 누르고 글 조회로 왔는지 ('저장했어요' 안내 표시용)
    const [entryId, setEntryId] = useState(null);
    const [writeDate, setWriteDate] = useState(null);
    // writeNote: 글쓰기 화면 맨 위에 한 번 띄울 안내 (날짜 바꾸기 전에 저장했으면 '○○ 일기를 저장했어요.'). 다른 길로 들어오면 비운다
    const [writeNote, setWriteNote] = useState(null);
    // writeHistory: 동화 '이전 장 · 다음 장'을 '내가 쓴 글' 쪽에서 눌렀으면 넘어간 장도 '내가 쓴 글'로 연다 (문장 쓰기에서 눌렀으면 문장 쓰기로). 다른 길로 들어오면 끈다
    const [writeHistory, setWriteHistory] = useState(false);
    // writeSpread: 쓴 문장이 있는 글을 연다고 알고 들어왔는지 (글 보기의 고쳐쓰기 · 이어서 쓰기). 참이면 불러오는 동안에도 일기를 펼친 책으로 그린다
    const [writeSpread, setWriteSpread] = useState(false);
    const [justSaved, setJustSaved] = useState(false);
    
    // 확인 완료 시 목적지만 기억하고, 시작하기를 눌렀을 때 이동한다.
    const [startup, setStartup] = useState({ status: "loading", destination: null, error: "" });
    const [startupAttempt, setStartupAttempt] = useState(0);

    function retryStartup() {
        setStartup({ status: "loading", destination: null, error: "" });
        setStartupAttempt((attempt) => attempt + 1);
    }

    // 인증에 실패했을 때 실행할 공통 함수
    // 브라우저의 토큰을 지우고 별명 설정 화면으로 전환한다.
    const handleAuthError = useCallback(() => {
        clearToken();
        setPage("nickname");
    }, []);


    // 글쓰기 버튼을 눌렀을 때 실행할 공통 함수 (글 리스트 · 글 조회 화면에서 같이 쓴다)
    // date: 일기 날짜("2026-11-16"), 동화는 장("ch3" · "new" · null)
    // 어느 책인지는 이미 기억해 둔 bookId 를 쓴다.
    // withPages: 쓴 문장이 있는 글인지 (모르면 false = 지금처럼 불러온 뒤 정한다)
    const handleWrite = useCallback((date, withPages = false) => {
        setWriteDate(date);
        setWriteNote(null);
        setWriteHistory(false);
        setWriteSpread(withPages === true);
        setPage("write");
    }, []);


    // 첫 접속과 재시도에만 확인한다. 페이지 이동으로는 다시 실행하지 않는다.
    useEffect(() => {
        let ignore = false;
        const controller = new AbortController();
        let timeout;

        async function checkUser() {
            // 토큰이 없어도 시작하기 화면을 거쳐 별명 설정으로 이동한다.
            if (!getToken()) {
                setStartup({ status: "ready", destination: "nickname", error: "" });
                return;
            }

            try {
                // 토큰이 있다는 것만으로는 유효한 사용자인지 알 수 없다.
                // api()가 저장된 토큰을 요청 헤더에 넣어 보내면
                // 서버가 해당 토큰의 사용자를 확인한다.                
                timeout = setTimeout(() => controller.abort(), 15000);
                await api("/api/users/me", { signal: controller.signal });

                if (!ignore) {
                    setStartup({ status: "ready", destination: "home", error: "" });
                }
            } catch (error) {
                if (ignore) return;

                if (error.status === 401) {
                    clearToken();
                    setStartup({ status: "ready", destination: "nickname", error: "" });
                } else {
                    // 서버가 준 문구(끝에 오류 코드, 예: '(오류 코드: DB-2003)')를 함께 보여 준다
                    setStartup({
                        status: "error", destination: null,
                        error: `목장에 연결하지 못했어요. ${error.message || "잠시 후 다시 시도해 주세요."}`,
                    });
                }
            } finally {
                clearTimeout(timeout);
            }
        }

        checkUser();

        return () => {
            ignore = true;
            clearTimeout(timeout);
            controller.abort();
        };
    }, [startupAttempt]);

    return (
        <>
            {/* 1. 사용자 확인 결과를 받은 뒤 시작하기로 다음 화면에 진입 */}
            {page === "checking" && (
                <StartPage
                    status={startup.status}
                    error={startup.error}
                    onStart={() => {
                        if (startup.status === "ready") setPage(startup.destination);
                    }}
                    onRetry={retryStartup}
                />
            )}

            {/* 2. 별명 설정 화면 */}
            {page === "nickname" && (
                <NicknamePage
                    // 자식이 별명 생성 후 onDone()을 호출하면 목장으로 전환
                    onDone={() => setPage("home")}
                />
            )}

            {/* 3. 목장 화면 */}
            {page === "home" && (
                <HomeListPage
                    // 보던 쪽 (목장으로 돌아와도 유지)
                    page={homePage}
                    onPageChange={setHomePage}

                    // 새 책 만들기 버튼을 누르면 생성 화면으로 전환
                    // 목장 쪽은 1쪽으로 (새 책은 최신순이라 1쪽 맨 앞에 보인다). 쪽을 기억하는 건 책을 열었다 돌아올 때뿐이다
                    onCreateBook={() => {
                        setHomePage(1);
                        setPage("createBook");
                    }}

                    // 자식이 선택한 책 객체를 전달한다.
                    // 고른 책 번호를 기억하고 그 책의 글 리스트(1쪽)로 전환한다.
                    onOpenBook={(book) => {
                        setBookId(book.id);
                        setBookInfo(book);
                        setListPage(1);
                        setPage("postList");
                    }}

                    // 대시보드 버튼을 누르면 대시보드로 전환 (돌아오면 목장 1쪽)
                    onOpenDashboard={() => {
                        setHomePage(1);
                        setPage("dashboard");
                    }}

                    // 목장 조회 중 인증 오류가 나면 공통 함수 실행
                    onAuthError={handleAuthError}
                />
            )}

            {/* 4. 새 책 만들기 화면 */}
            {page === "createBook" && (
                <CreateBookPage
                    // 책 생성 성공 후 바로 그 책의 글쓰기 화면으로 (요구사항정의서: 책 이름 설정 → 05번 글쓰기)
                    // writeDate 가 null 이면 일기는 오늘, 동화는 마지막 장(새 책이면 1장)을 연다.
                    // 글쓰기에서 '← 목록으로'를 누르면 이 책의 글 리스트(1쪽)로 간다.
                    onCreated={(book) => {
                        setBookId(book.id);
                        setBookInfo(book);      // 글쓰기 · 글 목록 화면이 책 종류 · 이름을 바로 쓴다 (예전 책 정보가 남지 않게)
                        setListPage(1);
                        setWriteDate(null);
                        setWriteNote(null);
                        setWriteHistory(false);
                        setWriteSpread(false);
                        setPage("write");
                    }}
                    
                    // 취소하면 목장으로 복귀
                    onCancel={() => setPage("home")}
                    
                    // 책 생성 중 인증 오류가 나면 별명 화면으로 전환
                    onAuthError={handleAuthError}
                />
            )}

            {/* 5. 대시보드 화면 */}
            {page === "dashboard" && (
                <DashboardPage
                    onBack={() => setPage("home")}
                    onAuthError={handleAuthError}
                />
            )}

            {/* 6. 글 리스트 화면 */}
            {page === "postList" && (
                <PostListPage
                    bookId={bookId}
                    bookInfo={bookInfo}
                    page={listPage}

                    // 쪽 번호를 누르면 그 쪽을 다시 조회한다.
                    onPageChange={setListPage}

                    // 글을 누르면 고른 글 번호를 기억하고 글 조회 화면으로 전환
                    onOpenEntry={(id) => {
                        setEntryId(id);
                        setJustSaved(false);
                        setPage("postDetail");
                    }}

                    // 글쓰기 버튼: date 는 일기 날짜("2026-11-16"), 동화는 장("ch3" · "new" · null)
                    onWrite={handleWrite}

                    onHome={() => setPage("home")}
                    onAuthError={handleAuthError}
                />
            )}

            {/* 7. 작성한 글 조회 화면 */}
            {page === "postDetail" && (
                <PostDetailPage
                    entryId={entryId}

                    // 글쓰기에서 방금 저장하고 왔으면 '저장했어요' 안내를 보여 준다.
                    saved={justSaved}

                    // 이전/다음 이야기: 글 번호만 바꾸면 같은 화면이 새 글을 조회한다.
                    onOpenEntry={(id) => {
                        setEntryId(id);
                        setJustSaved(false);
                    }}

                    // 고쳐쓰기 · 이어서 쓰기 버튼 (글 리스트의 글쓰기 버튼과 같은 동작)
                    onWrite={handleWrite}

                    // 동화는 이 장이 있는 장 목록 쪽을 알려 준다 (null 이면 보던 쪽 그대로)
                    onBack={(listAt) => {
                        if (listAt) setListPage(listAt);
                        setPage("postList");
                    }}
                    onHome={() => setPage("home")}
                    onAuthError={handleAuthError}
                />
            )}

            {/* 8. 글쓰기 화면 */}
            {page === "write" && (
                <WritePage
                    // key: 책이나 날짜가 바뀌면 화면을 새로 만들어 그 글을 다시 불러온다.
                    key={`${bookId}/${writeDate}`}
                    bookId={bookId}
                    date={writeDate}
                    bookKind={bookInfo?.kind}

                    // 목록으로 버튼 (동화는 지금 장이 있는 장 목록 쪽을 알려 준다. null 이면 보던 쪽 그대로)
                    onBack={(listAt) => {
                        if (listAt) setListPage(listAt);
                        setPage("postList");
                    }}

                    // '이야기 저장하기'가 끝나면 저장한 글의 조회 화면으로 전환
                    onSaved={(id) => {
                        setEntryId(id);
                        setJustSaved(true);
                        setPage("postDetail");
                    }}

                    // '날짜 바꾸기': 고른 날짜의 일기를 연다 (key 가 바뀌어 화면이 새로 만들어진다)
                    // history: 동화 장 이동을 '내가 쓴 글' 쪽에서 했는지 (넘어간 장도 같은 쪽으로 연다)
                    onDateChange={(date, note, history = false) => {
                        setWriteDate(date);
                        setWriteNote(note || null);
                        setWriteHistory(history);
                        setWriteSpread(false);
                    }}
                    note={writeNote}
                    startHistory={writeHistory}
                    startSpread={writeSpread}

                    onAuthError={handleAuthError}
                />
            )}
        </>
    );
}
