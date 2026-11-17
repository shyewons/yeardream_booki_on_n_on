import { useCallback, useEffect, useState } from "react";
import { api, clearToken, getToken } from "./api.js";
import NicknamePage from "./NicknamePage.jsx";      // 별명설정 페이지
import HomeListPage from "./HomeListPage.jsx";      // 목장(메인) 페이지
import CreateBookPage from "./CreateBookPage.jsx";  // 새 책 만들기 페이지
import PostListPage from "./PostListPage.jsx";      // 글 리스트 페이지
import DashboardPage from "./DashboardPage.jsx";    // 대시보드 페이지


export default function App() {

    // [page, setPage] → 현재 보여줄 화면
    // checking: 사용자 확인 중
    // nickname: 별명 설정
    // home: 목장
    // createBook: 새 책 만들기
    const [page, setPage] = useState("checking");
    
    // 앱 시작 시 서버 연결 등에 문제가 생기면 표시할 메시지
    const [startupError, setStartupError] = useState("");

    // 인증에 실패했을 때 실행할 공통 함수
    // 브라우저의 토큰을 지우고 별명 설정 화면으로 전환한다.
    const handleAuthError = useCallback(() => {
        clearToken();
        setPage("nickname");
    }, []);


    // 앱이 처음 표시될 때 기존 사용자인지 확인한다.
    // handleAuthError가 useCallback으로 유지되므로
    // page가 바뀔 때마다 이 검사를 다시 실행하지는 않는다.
    useEffect(() => {
        let ignore = false;

        async function checkUser() {
            // 저장된 토큰이 없으면 별명 설정부터 시작한다.
            if (!getToken()) {
                setPage("nickname");
                return;
            }

            try {
                // 토큰이 있다는 것만으로는 유효한 사용자인지 알 수 없다.
                // api()가 저장된 토큰을 요청 헤더에 넣어 보내면
                // 서버가 해당 토큰의 사용자를 확인한다.                
                await api("/api/users/me");

                if (!ignore) {
                    setPage("home");
                }
            } catch (error) {
                if (ignore) return;

                if (error.status === 401) {
                    clearToken();
                    setPage("nickname");
                } else {
                    setStartupError(
                        "사용자 정보를 확인하지 못했어요. 서버 연결을 확인하고 다시 시도해 주세요."
                    );
                }
            }
        }

        checkUser();

        return () => {
            ignore = true;
        };
    }, []);

    return (
        <>
            {/* 1. 사용자 확인 중: 안내 또는 오류 메시지 표시 */}
            {page === "checking" && (
                <div>
                    {startupError ? (
                        <>
                            <p role="alert">{startupError}</p>
                            <button
                                type="button"
                                onClick={() => window.location.reload()}
                            >
                                다시 시도
                            </button>
                        </>
                    ) : (
                        <p>사용자 정보를 확인하고 있어요...</p>
                    )}
                </div>
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
                    // 현재는 글쓰기 화면 대신 임시 알림만 표시한다.
                    onOpenBook={(book) => {
                        alert(`${book.title}: 글쓰기 화면은 아직 연결 전이에요.`);
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
        </>
    );
}