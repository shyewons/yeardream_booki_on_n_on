import {useState} from "react";
import PostListPage from "./PostListPage.jsx";
import NicknamePage from "./NicknamePage.jsx";

export default function App() {
    const [page, setPage] = useState('home');

    return (
        <>
            <nav>
                <button type="button" onClick={() => setPage('nickname')}>별명 설정 열기</button>
                <button type="button" onClick={() => setPage('posts')}>글 목록 열기</button>
            </nav>

            {page === 'home' && <p>안녕하세요 복실복실입니다.</p>}
            {page === 'nickname' && <NicknamePage />}
            {page === 'posts' && <PostListPage />}
        </>
    )
}