import { useEffect, useRef, useState } from 'react'
import { evidenceText, fmtDate, todayKST } from './format.js'
import singlePage from './assets/backgrounds/diary-writing-page.png'
import spread from './assets/backgrounds/diary-writing-spread.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import fairySpread from './assets/backgrounds/fairy-writing-spread.png'
import bubble from './assets/icons/cloud-speech-bubble.png'
import './DiaryWriteView.css'

function CorrectedText({ sentence }) {
    const text = sentence.revised || sentence.original
    const ranges = (sentence.corrections || []).flatMap(({ after }) => {
        const start = after ? text.indexOf(after) : -1
        return start < 0 ? [] : [{ start, end: start + after.length }]
    }).sort((a, b) => a.start - b.start)
    const parts = []
    let cursor = 0
    for (const range of ranges) {
        if (range.start < cursor) continue
        parts.push(text.slice(cursor, range.start), <mark key={range.start}>{text.slice(range.start, range.end)}</mark>)
        cursor = range.end
    }
    parts.push(text.slice(cursor))
    return parts
}

function CorrectionPanel({ sentence }) {
    const corrections = sentence.corrections || []
    return <section className="diary-write__result" aria-label="문장 확인 결과">
        <h2>{corrections.length ? '이렇게 써요' : '잘했어요!'}</h2>
        <div className="diary-write__result-scroll" tabIndex={0}>
            <p className="diary-write__corrected"><CorrectedText sentence={sentence} /></p>
            {corrections.map((item, index) => <details key={`${sentence.id}-${index}`} open={index === 0}>
                <summary>{item.before} → {item.after}</summary>
                <div className="diary-write__reason">
                    <p>{item.explanation}</p>
                    {evidenceText(item) && <p className="diary-write__evidence">{evidenceText(item)}</p>}
                </div>
            </details>)}
            {!corrections.length && sentence.compliment && <p>{sentence.compliment}</p>}
        </div>
    </section>
}

// startSpread: 쓴 문장이 있는 일기를 연다고 알고 왔으면 불러오는 동안에도 펼친 책으로 그린다 (다 불러온 뒤 한 쪽 → 펼친 책으로 바뀌며 넘어가지 않게)
// startHistory: 처음부터 '내가 쓴 글' 쪽을 펼쳐 둔다 (동화 장 이동을 '내가 쓴 글'에서 했을 때. 쓴 문장이 없으면 그대로 문장 쓰기)
export default function DiaryWriteView({ state, writer, boxRef, onChangeDate, onBack, maxChars, renderWork, SentenceComponent, fairy = false, storyContext, expression, chapterActions, storyDialog, startHistory = false, startSpread = false }) {
    const [history, setHistory] = useState(startHistory)
    const historyButton = useRef(null)
    const dateInput = useRef(null)
    const written = state.sentences.filter((sentence) => sentence.original)
    const hasPages = written.length > 0
    const reviewing = state.view === 'all'
    const ready = !state.loading && !state.loadError && !!state.entry
    // 불러오는 중에도 '내가 쓴 글'에서 넘어왔으면(history) 왼쪽 쪽을 펼친 채로 불러온다 (오른쪽으로 갔다가 돌아오지 않게). 다 불러왔는데 쓴 글이 없으면 문장 쓰기
    const showingHistory = (hasPages || !ready) && (history || reviewing)
    const editing = state.sentences.find((sentence) => sentence.id === state.editingId)
    const pending = state.sentences.find((sentence) => sentence.work)
    const selected = editing || written.find((sentence) => sentence.id === state.scrollTo?.id) || written.at(-1)
    const locked = state.busy || !ready
    const first = !hasPages && !pending && !state.notice && !state.busy
    const spreadLook = hasPages || (!ready && startSpread)     // 펼친 책 모양 (쓴 문장이 있거나, 있다고 알고 불러오는 중)
    const showResult = !pending && !state.notice && selected && state.insertAt === null
    const inputLabel = editing ? '내 문장 고치기' : state.insertAt !== null ? '사이에 넣을 문장' : '한 문장씩 써요'
    const canInput = !fairy || !state.finished || !!editing

    useEffect(() => {
        if (showingHistory) historyButton.current?.focus({ preventScroll: true })
    }, [showingHistory, hasPages])

    // 키보드가 화면 높이를 줄여도 현재 입력칸과 조작 영역으로 스크롤할 수 있다.
    useEffect(() => {
        const viewport = window.visualViewport
        const revealInput = () => {
            if (document.activeElement === boxRef.current) boxRef.current.scrollIntoView({ block: 'center' })
        }
        viewport?.addEventListener('resize', revealInput)
        return () => viewport?.removeEventListener('resize', revealInput)
    }, [boxRef])

    function returnToInput() {
        setHistory(false)
        if (reviewing) writer.backToWrite()
        requestAnimationFrame(() => boxRef.current?.focus({ preventScroll: true }))
    }
    function edit(sentence) {
        if (state.busy) return
        writer.startEdit(sentence.id)
        writer.setBox(sentence.original || sentence.revised)
        returnToInput()
    }
    function calendar() {
        const input = dateInput.current
        if (!input) return
        input.focus({ preventScroll: true })
        try { input.showPicker?.() } catch { /* 기본 date 입력도 직접 선택할 수 있다. */ }
    }

    const pageHeader = (left = false) => <>
        <div className="diary-write__page-header">
            <h1 className="diary-write__category">{fairy ? '동화' : '일기'}</h1>
            {ready && (fairy ? <p className="diary-write__chapter">{state.displayNo || state.chapterNo || 1}장</p> : left ? <p className="diary-write__date-static">{fmtDate(state.entry.date)}</p> : <div className="diary-write__date">
                <button type="button" onClick={calendar} aria-label={`날짜 바꾸기, ${fmtDate(state.entry.date)}`}>
                    {fmtDate(state.entry.date)}<span className="diary-write__icon diary-write__icon--calendar" aria-hidden="true" />
                </button>
                <input ref={dateInput} id="day-pick" type="date" tabIndex={-1} aria-label="일기 날짜 선택" value={state.entry.date || ''} max={todayKST()} onChange={onChangeDate} />
            </div>)}
        </div>
        {hasPages && <div className={`diary-write__page-navigation${left ? ' diary-write__page-navigation--left' : ''}`}>
            {left && <h2 className="diary-write__history-title">{reviewing ? '전체 글 확인' : '내가 쓴 글'}</h2>}
            <button ref={left ? historyButton : undefined} type="button" className="ui-button ui-button--secondary ui-button--small" onClick={left ? returnToInput : () => setHistory(true)}>
                {left ? (state.expr ? '표현 고르기 →' : editing ? '문장 고치기 →' : '문장 쓰기 →') : '← 내가 쓴 글 보기'}
            </button>
        </div>}
    </>

    // 불러오는 중 · 불러오기 실패: 펼친 쪽(왼쪽 '내가 쓴 글' 또는 오른쪽 문장 쓰기)에 같은 안내를 보여 준다
    const loadState = <div className="diary-write__load-state">
        {state.loadError ? <div className="ui-notice ui-notice--error" role="alert"><p>쓰던 글을 불러오지 못했어요.</p><p>{state.loadError}</p><button type="button" className="ui-button ui-button--primary" onClick={writer.boot}>다시 불러오기</button></div> : <p role="status">쓰던 글을 불러오고 있어요…</p>}
    </div>

    const notices = <div className="diary-write__save-status">
        {state.save.text && <div id="savebar" className={state.save.retry ? 'ui-notice ui-notice--error' : ''} role="status">
            <span>{state.save.text}</span>
            {state.save.retry && <button type="button" className="ui-button ui-button--secondary ui-button--small" onClick={writer.retrySaves}>다시 저장하기</button>}
        </div>}
        {state.draft && state.box.trim() && <p id="draft-state" role="status" className={state.draft.status === 'error' ? 'ui-field-message' : ''}>
            {state.draft.status === 'error' ? '쓰던 문장을 저장하지 못했어요. 잠시 뒤에 다시 저장해요.' : `쓰던 문장도 임시저장했어요${state.draft.at ? ` · ${state.draft.at}` : ''}`}
        </p>}
        {state.undo && <div id="undo-bar" role="status">
            <span>{state.undo.error ? '되살리지 못했어요. ' : `${state.undo.seq}번째 문장을 지웠어요. `}</span>
            <button type="button" className="ui-button ui-button--secondary ui-button--small" disabled={state.undo.busy || state.busy} onClick={writer.undoDelete}>{state.undo.busy ? '되살리는 중…' : state.undo.error ? '다시 시도' : '되돌리기'}</button>
        </div>}
    </div>

    return <main className={`diary-write${spreadLook || fairy ? ' diary-write--spread' : ''}${fairy ? ' diary-write--fairy' : ''}${state.expr ? ' diary-write--expression' : ''}${showingHistory ? ' diary-write--history' : ''}${first ? ' diary-write--first' : ''}`} aria-label={fairy ? '동화 쓰기' : '일기 쓰기'}>
        <div className="diary-write__topbar" inert={!!storyDialog}>
            <button className="ui-button ui-button--secondary ui-button--small" id="to-list" type="button" onClick={onBack}>← 목록으로</button>
        </div>
        {storyDialog && <div className="diary-write__dialog-layer">{storyDialog}</div>}
        <div className="diary-write__viewport" inert={!!storyDialog}>
            <div className="diary-write__book">
                <img className="diary-write__paper" src={fairy ? fairySpread : spreadLook ? spread : singlePage} alt="" />
                {(spreadLook || fairy) && <section className="diary-write__page diary-write__page--left" inert={!showingHistory} aria-hidden={!showingHistory}>
                    {pageHeader(true)}
                    {!ready ? loadState : reviewing ? <>
                        <div className="diary-write__history-scroll" id="all"><p id="all-text">{written.map((sentence) => sentence.revised || sentence.original).join(' ')}</p></div>
                        {state.storyError && <p className="ui-notice ui-notice--error" id="save-err" role="alert">{state.storyError}</p>}
                        <div className="ui-actions diary-write__review-actions">
                            <button type="button" className="ui-button ui-button--secondary" id="back" onClick={returnToInput}>이어서 쓰기</button>
                            <button type="button" className="ui-button ui-button--primary" id="save-story" disabled={state.storySaving} onClick={writer.saveStory}>{state.storySaving ? '저장 중…' : state.storyError ? '다시 저장하기' : '이야기 저장하기'}</button>
                        </div>
                    </> : <div className="diary-write__history-scroll">
                        <ul id="list" aria-label="지금까지 쓴 문장">{state.sentences.map((sentence, index) => <SentenceComponent key={sentence.id} sentence={sentence} index={index} total={state.sentences.length} state={state} writer={writer} diary onEdit={edit} />)}</ul>
                    </div>}
                    {ready && showingHistory && notices}
                    {ready && showingHistory && chapterActions}
                </section>}
                <section className="diary-write__page diary-write__page--right" inert={showingHistory} aria-hidden={showingHistory}>
                    {pageHeader()}
                    {!ready ? loadState : <>
                        {storyContext}
                        {expression || (pending ? <div className="diary-write__result diary-write__working" role="status"><h2>문장을 확인하고 있어요</h2><div className="diary-write__result-scroll">{renderWork(pending.work)}</div></div>
                            : state.busy ? <p className="ui-notice" role="status">문장을 확인하고 있어요…</p>
                            : state.notice || state.choices ? <section className="diary-write__notice ui-notice" aria-label="입력 안내"><p id="msg" role="status">{state.notice}</p>{state.shown && <p id="shown">{state.shown}</p>}
                                {state.choices && <div id="choices">{state.choices.items.map((item, i) => <div key={i}><p>{item.text}</p><div className="ui-actions">{item.labels.map((label, n) => <button type="button" className="ui-button ui-button--secondary ui-button--small" disabled={state.busy} key={n} onClick={() => writer.choose(i, n)}>{label}</button>)}</div></div>)}</div>}
                            </section> : showResult ? <CorrectionPanel key={`${selected.id}-${selected.revised}`} sentence={selected} /> : null)}
                        {canInput && !state.expr && <section className={`diary-write__composer${editing ? ' diary-write__composer--editing' : ''}`} id="composer" aria-label="문장 입력">
                            <div className="diary-write__input-heading">
                                <label htmlFor="box">{inputLabel}</label>
                                {(editing || state.insertAt !== null) && <button type="button" className="ui-button ui-button--secondary ui-button--small" id="cancel-edit" disabled={state.busy} onClick={writer.cancelEdit}>취소</button>}
                            </div>
                            {state.insertAt !== null && <p className="ui-description">{state.insertAt + 1}번째 자리에 문장을 넣어요.</p>}
                            <div className="diary-write__input-line">
                                <input className="ui-input ui-input--line" id="box" ref={boxRef} type="text" maxLength={maxChars} autoComplete="off" placeholder={fairy ? '상상한 이야기를 한 문장으로 써봐요.' : '여기에 오늘 있었던 일을 써봐요.'} value={state.box} disabled={locked} onChange={(event) => writer.setBox(event.target.value)} onFocus={(event) => { if (window.visualViewport?.height < 600) event.currentTarget.scrollIntoView({ block: 'center' }) }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); if (!locked && state.box.trim()) writer.submit() } }} />
                                {!state.box && <span className="diary-write__icon diary-write__icon--pencil diary-write__input-pencil" aria-hidden="true" />}
                            </div>
                        </section>}
                        <div className="ui-actions diary-write__actions">
                            <div className="diary-write__action-status">
                                {!showingHistory && notices}
                                {!state.save.text && <p className="diary-write__autosave-note" id="unsaved-note">쓰던 문장은 잠시 멈추면 임시저장돼요.</p>}
                            </div>
                            {hasPages && !fairy && <button className="ui-button ui-button--secondary" id="finish" type="button" disabled={state.busy} onClick={writer.finish}>다 썼어요</button>}
                            {canInput && !state.expr && <button className="ui-button ui-button--primary" id="go" type="button" disabled={locked || !state.box.trim()} onClick={writer.submit}>{state.busy ? '확인 중…' : '확인하기'}</button>}
                        </div>
                        {!showingHistory && chapterActions}
                        {!fairy && !first && !hasPages && state.question && <p className="diary-write__question" id="question">{state.question}</p>}
                    </>}
                </section>
            </div>
        </div>
        <div className="diary-write__mascot" aria-hidden="true"><img src={fairy ? alpaca : sheep} alt="" /></div>
        {hasPages && !showingHistory && !state.topicBox && state.question && <p className="diary-write__side-question" id="question">{state.expr ? '내 뜻에 맞는 말을 골라요.' : state.question}</p>}
        {first && ready && !showingHistory && <div className="diary-write__bubble"><img src={bubble} alt="" /><p>{fairy ? state.question || '상상한 이야기를 들려줘!' : <>오늘 가장 기억에 남는<br />일을 떠올려 봐~</>}</p></div>}
    </main>
}
