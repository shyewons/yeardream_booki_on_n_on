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
    // writeDate: 글쓰기 화면에서 쓸 일기 날짜("2026-11-16"). 동화는 장("ch3" = 3장, "new" = 새 장, null = 마지막 장. format.js 의 chapterTarget)
    // justSaved: 방금 '이야기 저장하기'를 누르고 글 조회로 왔는지 ('저장했어요' 안내 표시용)
    const [entryId, setEntryId] = useState(null);
    const [writeDate, setWriteDate] = useState(null);
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
    const handleWrite = useCallback((date) => {
        setWriteDate(date);
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
                    setStartup({
                        status: "error", destination: null,
                        error: "목장에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.",
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
                    // 새 책 만들기 버튼을 누르면 생성 화면으로 전환
                    onCreateBook={() => setPage("createBook")}

                    // 자식이 선택한 책 객체를 전달한다.
                    // 고른 책 번호를 기억하고 그 책의 글 리스트(1쪽)로 전환한다.
                    onOpenBook={(book) => {
                        setBookId(book.id);
                        setBookInfo(book);
                        setListPage(1);
                        setPage("postList");
                    }}

                    // 대시보드 버튼을 누르면 대시보드로 전환
                    onOpenDashboard={() => setPage("dashboard")}

                    // 목장 조회 중 인증 오류가 나면 공통 함수 실행
                    onAuthError={handleAuthError}
                />
            )}

            {/* 4. 새 책 만들기 화면 */}
            {page === "createBook" && (
                <CreateBookPage
                    // 책 생성 성공 후 목장으로 복귀
                    // 목장 컴포넌트가 다시 표시되면서 목록을 새로 조회한다.
                    onCreated={() => setPage("home")}
                    
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

                    onBack={() => setPage("postList")}
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

                    // 목록으로 버튼
                    onBack={() => setPage("postList")}

                    // '이야기 저장하기'가 끝나면 저장한 글의 조회 화면으로 전환
                    onSaved={(id) => {
                        setEntryId(id);
                        setJustSaved(true);
                        setPage("postDetail");
                    }}

                    // '날짜 바꾸기': 고른 날짜의 일기를 연다 (key 가 바뀌어 화면이 새로 만들어진다)
                    onDateChange={setWriteDate}

                    onAuthError={handleAuthError}
                />
            )}
        </>
    );
}
