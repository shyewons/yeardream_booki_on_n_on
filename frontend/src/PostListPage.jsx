// 글 리스트 화면 (요구사항정의서 차트 - 화면ID 시트 - 04번 화면)
// GET /api/books/{책}/entries?page=N → 한 쪽 10개 (일기: 최신 날짜부터).
// 일기: 오늘 일기 버튼(없으면 '새 일기 쓰기', 쓰는 중이면 '오늘 일기 이어서 쓰기', 저장했으면 '오늘 일기 고쳐 쓰기')
//       + 다른 날짜에 쓰던 일기가 있으면 '이어서 쓰기', 날짜로 찾기.
// 동화: 책 하나 = 이야기 하나, 이야기는 장(1장 ~ 100장)으로 나뉜다 (디자인 04C). 장 목록(장 번호 + 첫 문장)을 1장부터 한 쪽 10장씩 보여 준다.
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

// (디자인) 04 글 목록. 날짜·장·완료 조건과 API는 기존 동작을 유지한다.
import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { KIND_LABEL, NEW_CHAPTER, chapterTarget, fmtDate, todayKST } from './format.js'
import { useLoad } from './useLoad.js'
import WardrobeThumbnail from './WardrobeThumbnail.jsx'
import diaryBook from './assets/backgrounds/diary-list-book.png'
import fairyBook from './assets/backgrounds/fairy-list-book.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import giftIcon from './assets/icons/reward-gift.png'
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

// onPrint: 오른쪽 위 '책 출력하기' (책 출력 화면으로). 글을 불러오기 전 · 실패 화면에는 없다
function BookLayout({ book, onHome, onPrint, finished, children, footer }) {
    const fairy = book?.kind === 'fairy'
    return <main className={`post-list post-list--${fairy ? 'fairy' : 'diary'}`} aria-labelledby="post-list-title">
        <header className="post-list__header">
            <button className="ui-button ui-button--secondary ui-button--small post-list__home" type="button" onClick={onHome}><Arrow reverse />목장으로</button>
            {onPrint && <button className="ui-button ui-button--primary ui-button--small post-list__print" type="button" id="book-print" onClick={onPrint}>책 출력하기</button>}
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
                    {/* 선물에 세는 장(기준 문장 수 이상)은 ✓, 아니면 지금 문장 수 (디자인 때 모양만 바꾸거나 뺄 수 있게 따로 둔다) */}
                    <span className={entry.qualified ? 'chapter-mark ok' : 'chapter-mark'}>{entry.qualified ? '✓' : `(${entry.sentence_count}문장)`}</span>
                    <span className="post-list__preview" title={entry.first || '(쓰던 문장만 있어요)'}>{entry.first || '(쓰던 문장만 있어요)'}</span>
                </span> : <span className="post-list__entry-text">
                    <span className="post-list__date">{fmtDate(entry.date)}</span>
                    <span className="post-list__entry-meta">{entry.status !== 'done' && '쓰는 중 · '}{entry.sentence_count}문장</span>
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

function StoryChapters({ data, onHome, onOpenEntry, onWrite, onPrint, onAuthError, reload, onPageChange }) {
    const { book, story } = data
    const chapters = data.items
    const [ask, setAsk] = useState(null)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState('')
    // 동화 선물 (FR-040 · FR-045): GET /api/rewards/fairy/{책} → 구간마다 locked / claimable / claimed 와 옷.
    // 받을 수 있는 구간의 선물 상자를 누르면 묻고(gift-ask) 받는다 (POST …/claim). 받은 뒤에는 응답의 fairy_reward 로 바로 바꾼다
    const rewardLoad = useLoad(`/api/rewards/fairy/${book.id}`, onAuthError)
    const [rewardFresh, setRewardFresh] = useState(null)
    const reward = rewardFresh || rewardLoad.data                     // 불러오지 못하면 null (상자는 진행 표시만 한다)
    const [gift, setGift] = useState(null)                           // 묻는 중인 구간 {order, chapters, clothes} · 받은 뒤 {got}
    const [gifting, setGifting] = useState(false)
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
    const stageOf = (step) => reward && reward.stages.find((x) => x.chapters === step)
    async function claimGift() {
        if (gifting || !gift || !gift.order) return
        setGifting(true)
        setError('')
        try {
            const r = await api(`/api/rewards/fairy/${book.id}/claim`, { method: 'POST', body: { order: gift.order } })
            setRewardFresh(r.fairy_reward)
            setGift({ got: r.clothes })
        } catch (err) {
            if (err.status === 401) {
                onAuthError()
                return
            }
            setError(err.message)
            if (err.status === 409) rewardLoad.retry()               // 이미 받았으면 상태를 다시 읽는다
        }
        setGifting(false)
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
    return <BookLayout book={book} onHome={onHome} onPrint={story.chapters.some((c) => c.sentence_count > 0) ? onPrint : null} finished={story.finished} footer={
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
                <div className="post-list__reward-track" role="group" aria-label={`${minSentences}문장 이상 쓴 장 ${story.qualified}개. ${nextGift ? `다음 선물까지 ${nextGift - story.qualified}장` : '선물을 모두 모았어요'}`}>
                    <span className="post-list__reward-fill" style={{ width: `${Math.min(100, story.qualified / maxReward * 100)}%` }} />
                    {steps.map((step, i) => {
                        // 상자 상태: 받을 수 있음(누르면 받기) · 받음(✓) · 아직(회색). 그 주제에 준비된 옷이 없으면 누를 수 없다
                        const stage = stageOf(step)
                        const claimable = !!stage && stage.status === 'claimable' && !!stage.clothes
                        const claimed = !!stage && stage.status === 'claimed'
                        const cls = `post-list__reward-stop${story.rewards_reached.includes(step) ? ' is-reached' : ''}${claimable ? ' is-claimable' : ''}${claimed ? ' is-claimed' : ''}`
                        // 받을 수 있는 상자 중 첫 상자 위에만 말풍선 '눌러서 받아요!' (칸을 밀지 않게 상자 위에 띄운다)
                        const firstClaimable = claimable && !steps.slice(0, i).some((x) => { const t = stageOf(x); return t && t.status === 'claimable' && t.clothes })
                        const inner = <>
                            {firstClaimable && <span className="post-list__gift-pop" id="gift-hint" aria-hidden="true">🎁 눌러서 받아요!</span>}
                            {/* 받은 상자: 상자 그림 귀퉁이에 작은 ✓ (숫자 칸을 넓히지 않아 숫자가 밀리지 않는다) */}
                            <span className="post-list__gift-box"><img src={giftIcon} alt="" />{claimed && <span className="post-list__gift-check" aria-label="받음">✓</span>}</span><span>{step}</span>
                        </>
                        return claimable
                            ? <button type="button" className={cls} key={step} style={{ left: `${step / maxReward * 100}%` }} id={`gift-${step}`}
                                      aria-label={`${step}장 선물 받기`} onClick={() => { setError(''); setGift(stage) }}>{inner}</button>
                            : <span className={cls} key={step} style={{ left: `${step / maxReward * 100}%` }}
                                    title={claimed ? `${stage.clothes ? stage.clothes.name : '선물'}을(를) 받았어요` : `${minSentences}문장 이상 쓴 장이 ${step}개가 되면 받아요`}>{inner}</span>
                    })}
                </div>
            </div>
            {!story.finished && <div className="post-list__write-actions">
                <button className="ui-button ui-button--primary" type="button" id="new-chapter" disabled={chapters.length > 0 && !story.can_new_chapter} onClick={() => onWrite(chapters.length ? NEW_CHAPTER : null)}>새 장 쓰기</button>
                {chapters.length > 0 && <button className="ui-button ui-button--secondary" type="button" id="continue" onClick={continueStory} aria-label={`이어서 쓰기 (${lastShown}장)`}>이어서 쓰기</button>}
            </div>}
        </div>
        {chapters.length ? <EntryRows items={chapters} fairy onOpenEntry={onOpenEntry} /> : <div className="post-list__empty"><p className="ui-body">아직 쓴 이야기가 없어요.</p><p className="ui-description ui-muted">새 장 쓰기를 눌러 이야기를 시작해요.</p></div>}
        {gift && <Confirmation label="동화 선물" busy={gifting} onCancel={() => { setGift(null); setError('') }}>
            <WardrobeThumbnail item={gift.got || gift.clothes} className="post-list__gift-preview" fallback={<img src={giftIcon} alt="" />} />
            {gift.got ? <>
                <p className="ui-body" id="gift-got">🎉 {gift.got.name}을(를) 받았어요! 옷장에서 입혀 볼 수 있어요.</p>
                <div className="ui-actions"><button className="ui-button ui-button--primary" type="button" onClick={() => setGift(null)}>좋아요</button></div>
            </> : <>
                <p className="ui-body" id="gift-ask">{minSentences}문장 이상 쓴 장이 {gift.chapters}개가 됐어요. 선물 「{gift.clothes.name}」을(를) 받을까요?</p>
                {error && <p className="ui-notice ui-notice--error" role="alert">{error}</p>}
                <div className="ui-actions">
                    <button className="ui-button ui-button--primary" type="button" id="gift-yes" disabled={gifting} aria-busy={gifting} onClick={claimGift}>{gifting ? '받는 중...' : '선물 받기'}</button>
                    <button className="ui-button ui-button--secondary" type="button" disabled={gifting} onClick={() => { setGift(null); setError('') }}>나중에</button>
                </div>
            </>}
        </Confirmation>}
        {ask === 'resume' && <Confirmation label="이어 쓰기" onCancel={() => setAsk(null)}>
            <p className="ui-body">{lastShown}장에 이어서 쓸까요, {lastShown + 1}장을 새로 쓸까요?</p>
            <div className="ui-actions">
                <button className="ui-button ui-button--primary" type="button" id="resume-same" onClick={() => onWrite(chapterTarget(lastNo))}>{lastShown}장 이어 쓰기</button>
                <button className="ui-button ui-button--secondary" type="button" id="resume-new" onClick={() => onWrite(NEW_CHAPTER)}>{lastShown + 1}장 쓰기</button>
                <button className="ui-button ui-button--secondary" type="button" onClick={() => setAsk(null)}>취소</button>
            </div>
        </Confirmation>}
        {ask === 'finish' && <Confirmation label="이야기 끝내기" busy={sending} onCancel={() => { setAsk(null); setError('') }}>
            <p className="ui-body">{minSentences}문장 이상 쓴 장이 {story.qualified}개예요. 이야기를 끝낼까요? 끝내면 새 장은 더 쓸 수 없고, 고쳐 쓰기만 할 수 있어요.</p>
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

export default function PostListPage({ bookId, bookInfo, page, onPageChange, onOpenEntry, onWrite, onPrint, onHome, onAuthError }) {
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
    if (book.kind !== 'diary') return <StoryChapters key={bookId} data={data} onHome={onHome} onOpenEntry={onOpenEntry} onWrite={onWrite} onPrint={onPrint} onAuthError={onAuthError} reload={retry} onPageChange={onPageChange} />
    const today = todayKST()
    const writing = data.writing
    const writingDate = writing?.date ? String(writing.date).slice(0, 10) : null
    // 그날 일기에 쓴 문장이 있는지 (목록에 받아 둔 sentence_count). 있으면 글쓰기 화면을 불러오는 동안에도 펼친 책으로 그린다
    // (한 쪽 그림 → 펼친 책으로 바뀌며 넘어갔다 오지 않게, 2026-11-23). 이 쪽 목록에 없는 날짜면 모름 = false (불러온 뒤 정한다)
    const hasPages = (date) => data.items.some((item) => String(item.date).slice(0, 10) === date && item.sentence_count > 0)
    return <BookLayout book={book} onHome={onHome} onPrint={data.total ? onPrint : null} footer={
        <>
            <ListPager page={data.page} totalPages={data.total_pages} total={data.total} unit="일" onGo={onPageChange} />
            <DateFinder bookId={bookId} onOpenEntry={onOpenEntry} onWrite={onWrite} onAuthError={onAuthError} />
        </>
    }>
        <div className="post-list__toolbar">
            <p className="ui-description">읽고 싶은 날짜를 눌러 주세요.</p>
            <div className="post-list__write-actions">
                {/* 하루에 일기는 하나라서, 오늘 일기가 이미 있으면 그 글을 연다 (서버 list_entries 의 today: 없음 · 쓰는 중 · 저장함) */}
                <button className="ui-button ui-button--primary" type="button" id="today-write" onClick={() => onWrite(today, hasPages(today))}>{!data.today ? '새 일기 쓰기' : data.today.status === 'done' ? '오늘 일기 고쳐 쓰기' : '오늘 일기 이어서 쓰기'}</button>
                {writing && writingDate !== today && <button className="ui-button ui-button--secondary" type="button" onClick={() => onWrite(writingDate, hasPages(writingDate))} aria-label={`이어서 쓰기 (${fmtDate(writingDate)})`}>이어서 쓰기</button>}
            </div>
        </div>
        {data.items.length ? <EntryRows items={data.items} onOpenEntry={onOpenEntry} /> : <div className="post-list__empty"><p className="ui-body">아직 들려준 이야기가 없어요.</p><p className="ui-description ui-muted">새 일기 쓰기를 눌러 이야기를 시작해요.</p></div>}
    </BookLayout>
}
