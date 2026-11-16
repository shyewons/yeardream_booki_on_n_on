// 글 리스트 화면 (요구사항정의서 차트 - 화면ID 시트 - 04번 화면)
// GET /api/books/{책}/entries?page=N → 한 쪽 10개 (일기: 최신 날짜부터).
// 일기: '새 일기 쓰기'(오늘) + 쓰던 일기가 있으면 '이어서 쓰기', 날짜로 찾기.  동화: 책 하나에 이야기 한 편.
//
// 화면을 바꾸는 일은 App.jsx 가 한다. 이 화면은 아래 함수(props)를 부르기만 한다.
//   onPageChange(쪽)   다른 쪽 보기
//   onOpenEntry(글 번호)   글 보기 화면으로
//   onWrite(날짜 또는 null)   글쓰기 화면으로 (동화는 날짜 없음)
//   onHome()   목장으로
//   onAuthError()   토큰이 틀림 → 별명 화면으로

import { useEffect, useState } from 'react'
import { api } from './api.js'
import { COVER, KIND_LABEL, fmtDate, todayKST } from './format.js'
import { useLoad } from './useLoad.js'
import LoadError from './LoadError.jsx'
import Pager from './Pager.jsx'

// 날짜로 일기 찾기: 있으면 그 글로, 없으면 '이 날짜로 쓰기'를 권한다
function DateFinder({ bookId, onOpenEntry, onWrite, onAuthError }) {
    const [value, setValue] = useState('')
    const [hint, setHint] = useState(null) // null | { text, writeDate }

    async function find() {
        if (!value) {
            setHint({ text: '날짜를 골라 주세요.' })
            return
        }
        setHint(null)
        try {
            const d = await api(`/api/books/${bookId}/diary/${value}`)
            onOpenEntry(d.entry.id)
        } catch (err) {
            if (err.status === 401) onAuthError()
            else if (err.status === 404) {
                // 앞으로 올 날짜에는 쓸 수 없으므로 쓰기 버튼을 내지 않는다
                setHint({ text: '그 날짜에는 일기가 없어요. ', writeDate: value <= todayKST() ? value : null })
            } else setHint({ text: err.message })
        }
    }

    return (
        <div className="finder">
            <input type="date" aria-label="날짜 선택" value={value} onChange={(e) => setValue(e.target.value)} />{' '}
            <button type="button" onClick={find}>날짜로 찾기</button>{' '}
            <span className="hint" role="status">
                {hint && hint.text}
                {hint && hint.writeDate && (
                    <button type="button" onClick={() => onWrite(hint.writeDate)}>이 날짜로 쓰기</button>
                )}
            </span>
        </div>
    )
}

export default function PostListPage({ bookId, page, onPageChange, onOpenEntry, onWrite, onHome, onAuthError }) {
    const { data, error, retry } = useLoad(`/api/books/${bookId}/entries?page=${page}`, onAuthError)

    // 범위를 벗어난 쪽 번호면 마지막 쪽으로 보낸다 (예: 다른 기기에서 글이 줄었을 때)
    const lastPage = data ? data.total_pages : 0
    useEffect(() => {
        if (lastPage && page > lastPage) onPageChange(lastPage)
    }, [page, lastPage, onPageChange])

    const back = <button type="button" onClick={onHome}>← 목장으로</button>
    if (error) return <div>{back}<LoadError error={error} what="책" onRetry={retry} onHome={onHome} /></div>
    if (!data) return <div>{back}<p>불러오는 중...</p></div>

    const { book } = data
    const isDiary = book.kind === 'diary'
    const today = todayKST()
    const writing = data.writing // 쓰는 중인 글 (없으면 null)
    const writingDate = writing && writing.date ? String(writing.date).slice(0, 10) : null

    return (
        <div>
            {back}
            <h1>
                {COVER[book.cover] || '📖'} {book.title}에게 들려준 이야기 [{KIND_LABEL[book.kind] ?? book.kind}]
            </h1>
            {data.total > 0 && <p>{isDiary ? '읽고 싶은 날짜를 눌러 주세요.' : '이야기를 눌러 읽어 보세요.'}</p>}

            <p className="start">
                {isDiary ? (
                    <>
                        <button type="button" onClick={() => onWrite(today)}>
                            {writingDate === today ? '오늘 일기 이어서 쓰기' : '새 일기 쓰기'}
                        </button>
                        {writing && writingDate !== today && (
                            <>
                                {' '}
                                <button type="button" onClick={() => onWrite(writingDate)}>
                                    이어서 쓰기 ({fmtDate(writingDate)})
                                </button>
                            </>
                        )}
                    </>
                ) : (
                    <button type="button" onClick={() => onWrite(null)}>
                        {data.total ? '이야기 이어서 쓰기' : '이야기 쓰기'}
                    </button>
                )}
            </p>

            {isDiary && (
                <DateFinder bookId={bookId} onOpenEntry={onOpenEntry} onWrite={onWrite} onAuthError={onAuthError} />
            )}

            {data.items.length ? (
                <ul className="rows">
                    {data.items.map((e) => (
                        <li key={e.id}>
                            <button type="button" onClick={() => onOpenEntry(e.id)}>
                                {fmtDate(e.date)} · {e.status === 'done' ? '완성' : '쓰는 중'} · 문장 {e.sentence_count}개
                            </button>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="empty">아직 들려준 이야기가 없어요.</p>
            )}

            <Pager page={data.page} totalPages={data.total_pages} total={data.total}
                   unit={isDiary ? '일' : '편'} onGo={onPageChange} />
        </div>
    )
}
