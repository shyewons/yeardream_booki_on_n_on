// 글 리스트 화면 (요구사항정의서 차트 - 화면ID 시트 - 04번 화면)
// GET /api/books/{책}/entries?page=N → 한 쪽 10개 (일기: 최신 날짜부터).
// 일기: '새 일기 쓰기'(오늘) + 쓰던 일기가 있으면 '이어서 쓰기', 날짜로 찾기.
// 동화: 책 하나 = 이야기 하나, 이야기는 장(1~10장)으로 나뉜다 (디자인 04C). 장 목록(장 번호 + 첫 문장)을 보여 준다.
//       '새 장 쓰기' · '이어서 쓰기'(마지막 장) · 보상 진행(3문장 이상 쓴 장 수와 3·6·10 구간) · '이야기 끝내기'.
//       마지막 장을 다른 날 이어 쓰려 하면 '이어 쓸지 · 새 장을 쓸지' 묻는다.
//       POST /api/books/{책}/finish → 이야기 끝내기 (끝낸 뒤에는 장을 읽고 고쳐 쓰기만 한다)
//
// 화면을 바꾸는 일은 App.jsx 가 한다. 이 화면은 아래 함수(props)를 부르기만 한다.
//   onPageChange(쪽)   다른 쪽 보기
//   onOpenEntry(글 번호)   글 보기 화면으로
//   onWrite(날짜 · 장 · null)   글쓰기 화면으로 (동화는 chapterTarget(3) · NEW_CHAPTER · null = 마지막 장)
//   onHome()   목장으로
//   onAuthError()   토큰이 틀림 → 별명 화면으로

import { useEffect, useState } from 'react'
import { api } from './api.js'
import { COVER, KIND_LABEL, NEW_CHAPTER, chapterTarget, fmtDate, todayKST } from './format.js'
import { useLoad } from './useLoad.js'
import LoadError from './LoadError.jsx'
import Pager from './Pager.jsx'

// 동화 장 목록 (04C). data.story 는 서버 books_repo._story
function StoryChapters({ data, back, onOpenEntry, onWrite, onAuthError, reload }) {
    const { book, story } = data
    const chapters = data.items
    const [ask, setAsk] = useState(null) // null | 'resume' (이어 쓸지 묻기) | 'finish' (끝낼지 확인)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState('')

    const last = story.chapters.length ? story.chapters[story.chapters.length - 1] : null
    const steps = data.rules ? data.rules.story_reward_chapters : [3, 6, 10]        // 선물 구간 (reward_rules.py)
    const minSentences = data.rules ? data.rules.story_chapter_min_sentences : 3     // 보상에 세는 장의 문장 수
    const nextGift = steps.find((m) => m > story.qualified) || null                 // 다음 선물 구간 (없으면 다 모음)
    const lastNo = story.last_chapter        // DB 번호 (글을 열 때)
    const lastShown = story.last_display     // 화면 번호 (빈 장을 건너뛰고 센다)
    // 마지막 장을 다른 날 이어 쓸 때: 그 장이 이미 채워졌고(3문장 이상) 새 장을 쓸 수 있으면 묻는다
    const lastDay = last && last.last_written ? String(last.last_written).slice(0, 10) : null
    const askResume = !!last && last.qualified && !!lastDay && lastDay < todayKST() && story.written_chapters < story.max_chapters

    function continueStory() {
        if (askResume) setAsk('resume')
        else onWrite(lastNo ? chapterTarget(lastNo) : null)
    }

    async function finish() {
        setSending(true)
        setError('')
        try {
            await api(`/api/books/${book.id}/finish`, { method: 'POST' })
            setAsk(null)
            reload()
        } catch (err) {
            if (err.status === 401) {
                onAuthError()
                return
            }
            setError(err.message)
        }
        setSending(false)
    }

    return (
        <div>
            {back}
            {/* 동화 책 이름은 주제 이름 · 문장일 수 있어서 '○○에게 들려준 이야기' 대신 『책 이름』 으로 쓴다 */}
            <h1>
                {COVER[book.cover] || '📖'} 『{book.title}』 [{KIND_LABEL[book.kind] ?? book.kind}]
                {story.finished && ' [완성]'}
            </h1>

            {/* 보상 진행 (받기는 보상 화면이 생기면).
                 '3문장 이상 쓴 장: N개' 는 받은 보상 수가 아니라 보상에 세는 장의 수다. 선물 구간(3 · 6 · 10개)과 다음 선물까지 남은 장 수를 함께 보여 준다 */}
            <div className="reward-progress" id="reward-progress">
                <p className="reward-count">{minSentences}문장 이상 쓴 장: {story.qualified}개</p>
                <ul className="reward-steps">
                    {steps.map((m) => (
                        <li key={m} className={story.rewards_reached.includes(m) ? 'reached' : ''}>
                            🎁 {m}개{story.rewards_reached.includes(m) ? ' ✓' : ''}
                        </li>
                    ))}
                </ul>
                <p className="reward-next">
                    {nextGift ? `다음 선물까지 ${nextGift - story.qualified}장 남았어요` : '선물을 모두 모았어요'}
                </p>
            </div>

            {chapters.length === 0 ? (
                <>
                    <p className="empty">아직 쓴 이야기가 없어요.</p>
                    <p className="start">
                        <button type="button" onClick={() => onWrite(null)}>이야기 쓰기</button>
                    </p>
                </>
            ) : (
                <>
                    {!story.finished && (
                        <p className="start">
                            <button type="button" id="new-chapter" disabled={!story.can_new_chapter} onClick={() => onWrite(NEW_CHAPTER)}>
                                새 장 쓰기
                            </button>{' '}
                            <button type="button" id="continue" onClick={continueStory}>이어서 쓰기 ({lastShown}장)</button>{' '}
                            {story.can_finish && <button type="button" id="finish-story" onClick={() => setAsk('finish')}>이야기 끝내기</button>}
                            {!story.can_new_chapter && story.written_chapters >= story.max_chapters && <span className="hint"> 이야기는 {story.max_chapters}장까지 쓸 수 있어요.</span>}
                        </p>
                    )}

                    {ask === 'resume' && (
                        <div className="confirm" id="resume-ask" role="alertdialog" aria-label="이어 쓰기">
                            <p className="ask">{lastShown}장에 이어서 쓸까요, {lastShown + 1}장을 새로 쓸까요?</p>
                            <button type="button" id="resume-same" onClick={() => onWrite(chapterTarget(lastNo))}>{lastShown}장 이어 쓰기</button>{' '}
                            <button type="button" id="resume-new" onClick={() => onWrite(NEW_CHAPTER)}>{lastShown + 1}장 쓰기</button>{' '}
                            <button type="button" onClick={() => setAsk(null)}>취소</button>
                        </div>
                    )}
                    {ask === 'finish' && (
                        <div className="confirm" id="finish-ask" role="alertdialog" aria-label="이야기 끝내기">
                            <p className="ask">이야기를 끝낼까요? 끝내면 새 장은 더 쓸 수 없고, 고쳐 쓰기만 할 수 있어요.</p>
                            {error && <p role="alert">{error}</p>}
                            <button type="button" id="finish-yes" disabled={sending} onClick={finish}>{sending ? '끝내는 중...' : '이야기 끝내기'}</button>{' '}
                            <button type="button" disabled={sending} onClick={() => { setAsk(null); setError('') }}>취소</button>
                        </div>
                    )}

                    <p>읽고 싶은 장을 눌러 주세요.</p>
                    <ul className="rows chapters">
                        {chapters.map((c) => (
                            <li key={c.id}>
                                <button type="button" onClick={() => onOpenEntry(c.id)}>
                                    <span className="chapter-no">{c.display_no}장</span>{' '}
                                    <span className="preview">{c.first || '(쓰던 문장만 있어요)'}</span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    )
}

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
            <input type="date" aria-label="날짜 선택" value={value} max={todayKST()} onChange={(e) => setValue(e.target.value)} />{' '}
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

    // 동화: 장 목록
    if (!isDiary) {
        return <StoryChapters data={data} back={back} onOpenEntry={onOpenEntry} onWrite={onWrite}
                              onAuthError={onAuthError} reload={retry} />
    }

    const today = todayKST()
    const writing = data.writing // 쓰는 중인 글 (없으면 null)
    const writingDate = writing && writing.date ? String(writing.date).slice(0, 10) : null

    return (
        <div>
            {back}
            <h1>
                {COVER[book.cover] || '📖'} {book.title}에게 들려준 이야기 [{KIND_LABEL[book.kind] ?? book.kind}]
            </h1>
            {data.total > 0 && <p>읽고 싶은 날짜를 눌러 주세요.</p>}

            <p className="start">
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
            </p>

            <DateFinder bookId={bookId} onOpenEntry={onOpenEntry} onWrite={onWrite} onAuthError={onAuthError} />

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
                   unit="일" onGo={onPageChange} />
        </div>
    )
}
