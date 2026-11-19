// 04 글 목록. 날짜·장·완료 조건과 API는 기존 동작을 유지한다.
import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { KIND_LABEL, NEW_CHAPTER, chapterTarget, fmtDate, todayKST } from './format.js'
import { useLoad } from './useLoad.js'
import diaryBook from './assets/backgrounds/diary-list-book.png'
import fairyBook from './assets/backgrounds/fairy-list-book.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import gift from './assets/icons/reward-gift.png'
import './PostListPage.css'

function Arrow({ reverse = false, double = false }) {
    return <span className={`post-list__arrows${reverse ? ' post-list__arrows--reverse' : ''}`} aria-hidden="true">
        <span className="post-list__arrow" />{double && <span className="post-list__arrow" />}
    </span>
}

function ListPager({ page, totalPages, total, unit, onGo }) {
    if (!totalPages) return null
    const first = Math.floor((page - 1) / 5) * 5 + 1
    const numbers = Array.from({ length: Math.min(5, totalPages - first + 1) }, (_, i) => first + i)
    return <div className="post-list__pagination">
        {totalPages > 1 && <nav aria-label="글 목록 페이지" className="post-list__pager">
            <button className="ui-button ui-button--secondary" type="button" aria-label="첫 페이지" disabled={page <= 1} onClick={() => onGo(1)}><Arrow reverse double /></button>
            <button className="ui-button ui-button--secondary" type="button" aria-label="이전 페이지" disabled={page <= 1} onClick={() => onGo(page - 1)}><Arrow reverse /></button>
            {numbers.map((number) => <button className={`ui-button ui-button--${number === page ? 'primary' : 'secondary'}`} type="button" key={number} aria-label={`${number}페이지`} aria-current={number === page ? 'page' : undefined} onClick={() => onGo(number)}>{number}</button>)}
            <button className="ui-button ui-button--secondary" type="button" aria-label="다음 페이지" disabled={page >= totalPages} onClick={() => onGo(page + 1)}><Arrow /></button>
            <button className="ui-button ui-button--secondary" type="button" aria-label="마지막 페이지" disabled={page >= totalPages} onClick={() => onGo(totalPages)}><Arrow double /></button>
        </nav>}
        <p className="post-list__count ui-muted">{page} / {totalPages}쪽 · 전체 {total}{unit}</p>
    </div>
}

function BookLayout({ book, onHome, finished, children, footer }) {
    const fairy = book?.kind === 'fairy'
    return <main className={`post-list post-list--${fairy ? 'fairy' : 'diary'}`} aria-labelledby="post-list-title">
        <header className="post-list__header">
            <button className="ui-button ui-button--secondary ui-button--small post-list__home" type="button" onClick={onHome}><Arrow reverse />목장으로</button>
            <div className="post-list__heading">
                {book && <p className="post-list__category">{KIND_LABEL[book.kind] ?? book.kind}</p>}
                <h1 className="ui-title" id="post-list-title">{book?.title || '글 목록'}</h1>
                {finished && <span className="post-list__finished">완성한 이야기</span>}
            </div>
        </header>
        <section className="post-list__book" aria-label="책 안의 글 목록">
            <img className="post-list__book-background" src={fairy ? fairyBook : diaryBook} alt="" />
            <div className="post-list__book-content">{children}</div>
        </section>
        <div className="post-list__footer">{footer}</div>
        {book && <div className="post-list__portrait-anchor" aria-hidden="true">
            <div className="post-list__portrait"><img src={fairy ? alpaca : sheep} alt="" /></div>
        </div>}
    </main>
}

function EntryRows({ items, fairy = false, onOpenEntry }) {
    return <ul className="post-list__rows">
        {items.map((entry) => <li key={entry.id}>
            <button className="post-list__entry" type="button" onClick={() => onOpenEntry(entry.id)}>
                {fairy ? <span className="post-list__chapter">
                    <span>{entry.display_no}장</span>
                    <span className="post-list__preview" title={entry.first || '(쓰던 문장만 있어요)'}>{entry.first || '(쓰던 문장만 있어요)'}</span>
                </span> : <span className="post-list__entry-text">
                    <span className="post-list__date">{fmtDate(entry.date)}</span>
                    <span className="post-list__entry-meta">{entry.status === 'done' ? '완성' : '쓰는 중'} · 문장 {entry.sentence_count}개</span>
                </span>}
                <Arrow />
            </button>
        </li>)}
    </ul>
}

function Confirmation({ label, onCancel, busy, children }) {
    const dialog = useRef(null)
    useEffect(() => {
        const element = dialog.current
        element.showModal()
        return () => element.close()
    }, [])
    return <dialog className="post-list__dialog" ref={dialog} aria-label={label} onCancel={(event) => {
        event.preventDefault()
        if (!busy) onCancel()
    }}>{children}</dialog>
}

function StoryChapters({ data, onHome, onOpenEntry, onWrite, onAuthError, reload, onPageChange }) {
    const { book, story } = data
    const chapters = data.items
    const [ask, setAsk] = useState(null)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState('')
    const last = story.chapters.length ? story.chapters[story.chapters.length - 1] : null
    const steps = data.rules ? data.rules.story_reward_chapters : [3, 6, 10]
    const minSentences = data.rules ? data.rules.story_chapter_min_sentences : 3
    const maxReward = Math.max(1, ...steps)
    const nextGift = steps.find((m) => m > story.qualified) || null
    const lastNo = story.last_chapter
    const lastShown = story.last_display
    const lastDay = last && last.last_written ? String(last.last_written).slice(0, 10) : null
    const askResume = !!last && last.qualified && !!lastDay && lastDay < todayKST() && story.written_chapters < story.max_chapters
    function continueStory() {
        if (askResume) setAsk('resume')
        else onWrite(lastNo ? chapterTarget(lastNo) : null)
    }
    async function finish() {
        if (sending) return
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
    return <BookLayout book={book} onHome={onHome} finished={story.finished} footer={
        <>
            <ListPager page={data.page} totalPages={data.total_pages} total={data.total} unit="장" onGo={onPageChange} />
            {!story.finished && chapters.length > 0 && <div className="post-list__extras">
                {story.can_finish && <button className="ui-button ui-button--secondary" type="button" id="finish-story" onClick={() => setAsk('finish')}>이야기 끝내기</button>}
                {!story.can_new_chapter && story.written_chapters >= story.max_chapters && <p className="ui-description">이야기는 {story.max_chapters}장까지 쓸 수 있어요.</p>}
            </div>}
        </>
    }>
        <div className="post-list__toolbar">
            <div className="post-list__rewards" id="reward-progress">
                <span className="ui-description">이 책의 보상</span>
                <div className="post-list__reward-track" role="img" aria-label={`${minSentences}문장 이상 쓴 장 ${story.qualified}개. ${nextGift ? `다음 선물까지 ${nextGift - story.qualified}장` : '선물을 모두 모았어요'}`}>
                    <span className="post-list__reward-fill" style={{ width: `${Math.min(100, story.qualified / maxReward * 100)}%` }} />
                    {steps.map((step) => <span className={`post-list__reward-stop${story.rewards_reached.includes(step) ? ' is-reached' : ''}`} key={step} style={{ left: `${step / maxReward * 100}%` }}>
                        <img src={gift} alt="" /><span>{step}</span>
                    </span>)}
                </div>
            </div>
            {!story.finished && <div className="post-list__write-actions">
                <button className="ui-button ui-button--primary" type="button" id="new-chapter" disabled={chapters.length > 0 && !story.can_new_chapter} onClick={() => onWrite(chapters.length ? NEW_CHAPTER : null)}>새 장 쓰기</button>
                {chapters.length > 0 && <button className="ui-button ui-button--secondary" type="button" id="continue" onClick={continueStory} aria-label={`이어서 쓰기 (${lastShown}장)`}>이어서 쓰기</button>}
            </div>}
        </div>
        {chapters.length ? <EntryRows items={chapters} fairy onOpenEntry={onOpenEntry} /> : <div className="post-list__empty"><p className="ui-body">아직 쓴 이야기가 없어요.</p><p className="ui-description ui-muted">새 장 쓰기를 눌러 이야기를 시작해요.</p></div>}
        {ask === 'resume' && <Confirmation label="이어 쓰기" onCancel={() => setAsk(null)}>
            <p className="ui-body">{lastShown}장에 이어서 쓸까요, {lastShown + 1}장을 새로 쓸까요?</p>
            <div className="ui-actions">
                <button className="ui-button ui-button--primary" type="button" id="resume-same" onClick={() => onWrite(chapterTarget(lastNo))}>{lastShown}장 이어 쓰기</button>
                <button className="ui-button ui-button--secondary" type="button" id="resume-new" onClick={() => onWrite(NEW_CHAPTER)}>{lastShown + 1}장 쓰기</button>
                <button className="ui-button ui-button--secondary" type="button" onClick={() => setAsk(null)}>취소</button>
            </div>
        </Confirmation>}
        {ask === 'finish' && <Confirmation label="이야기 끝내기" busy={sending} onCancel={() => { setAsk(null); setError('') }}>
            <p className="ui-body">이야기를 끝낼까요? 끝내면 새 장은 더 쓸 수 없고, 고쳐 쓰기만 할 수 있어요.</p>
            {error && <p className="ui-notice ui-notice--error" role="alert">{error}</p>}
            <div className="ui-actions">
                <button className="ui-button ui-button--primary" type="button" id="finish-yes" disabled={sending} aria-busy={sending} onClick={finish}>{sending ? '끝내는 중...' : '이야기 끝내기'}</button>
                <button className="ui-button ui-button--secondary" type="button" disabled={sending} onClick={() => { setAsk(null); setError('') }}>취소</button>
            </div>
        </Confirmation>}
    </BookLayout>
}

function DateFinder({ bookId, onOpenEntry, onWrite, onAuthError }) {
    const [value, setValue] = useState('')
    const [hint, setHint] = useState(null)
    async function find(event) {
        event.preventDefault()
        if (!value) {
            setHint({ text: '날짜를 골라 주세요.' })
            return
        }
        setHint(null)
        try {
            const data = await api(`/api/books/${bookId}/diary/${value}`)
            onOpenEntry(data.entry.id)
        } catch (err) {
            if (err.status === 401) onAuthError()
            else if (err.status === 404) setHint({ text: '그 날짜에는 일기가 없어요.', writeDate: value <= todayKST() ? value : null })
            else setHint({ text: err.message })
        }
    }
    return <form className="post-list__finder" onSubmit={find}>
        <div className="ui-actions">
            <input className="ui-input" type="date" aria-label="날짜 선택" value={value} max={todayKST()} onChange={(event) => setValue(event.target.value)} />
            <button className="ui-button ui-button--secondary ui-button--small" type="submit">날짜로 찾기</button>
        </div>
        {hint && <div className="post-list__finder-hint ui-description" role="status">
            <span>{hint.text}</span>
            {hint.writeDate && <button className="ui-button ui-button--secondary ui-button--small" type="button" onClick={() => onWrite(hint.writeDate)}>이 날짜로 쓰기</button>}
        </div>}
    </form>
}

export default function PostListPage({ bookId, bookInfo, page, onPageChange, onOpenEntry, onWrite, onHome, onAuthError }) {
    const { data, error, retry } = useLoad(`/api/books/${bookId}/entries?page=${page}`, onAuthError)
    const lastPage = data ? data.total_pages : 0
    useEffect(() => {
        if (lastPage && page > lastPage) onPageChange(lastPage)
    }, [page, lastPage, onPageChange])
    const book = data?.book || (bookInfo?.id === bookId ? bookInfo : null)
    if (error || !data) return <BookLayout book={book} onHome={onHome}>
        <div className="post-list__state">
            {error ? <div className="ui-notice ui-notice--error post-list__error">
                <p className="ui-body" role="alert">{error.status === 404 ? '책을 찾을 수 없어요.' : '글 목록을 불러오지 못했어요.'}</p>
                <button className="ui-button ui-button--primary" type="button" onClick={retry}>다시 불러오기</button>
            </div> : <p className="ui-description ui-muted" role="status">글 목록을 불러오고 있어요</p>}
        </div>
    </BookLayout>
    if (book.kind !== 'diary') return <StoryChapters key={bookId} data={data} onHome={onHome} onOpenEntry={onOpenEntry} onWrite={onWrite} onAuthError={onAuthError} reload={retry} onPageChange={onPageChange} />
    const today = todayKST()
    const writing = data.writing
    const writingDate = writing?.date ? String(writing.date).slice(0, 10) : null
    return <BookLayout book={book} onHome={onHome} footer={
        <>
            <ListPager page={data.page} totalPages={data.total_pages} total={data.total} unit="일" onGo={onPageChange} />
            <DateFinder bookId={bookId} onOpenEntry={onOpenEntry} onWrite={onWrite} onAuthError={onAuthError} />
        </>
    }>
        <div className="post-list__toolbar">
            <p className="ui-description">읽고 싶은 날짜를 눌러 주세요.</p>
            <div className="post-list__write-actions">
                <button className="ui-button ui-button--primary" type="button" onClick={() => onWrite(today)}>{writingDate === today ? '오늘 일기 이어쓰기' : '새 일기 쓰기'}</button>
                {writing && writingDate !== today && <button className="ui-button ui-button--secondary" type="button" onClick={() => onWrite(writingDate)} aria-label={`이어서 쓰기 (${fmtDate(writingDate)})`}>이어서 쓰기</button>}
            </div>
        </div>
        {data.items.length ? <EntryRows items={data.items} onOpenEntry={onOpenEntry} /> : <div className="post-list__empty"><p className="ui-body">아직 들려준 이야기가 없어요.</p><p className="ui-description ui-muted">새 일기 쓰기를 눌러 이야기를 시작해요.</p></div>}
    </BookLayout>
}
