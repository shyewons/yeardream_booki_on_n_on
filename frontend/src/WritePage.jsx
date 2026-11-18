// 글쓰기 화면 (요구사항정의서 차트 - 화면ID 시트 - 05~09번 화면)
// 한 문장씩 쓴다: 확인하기 → 유효성 검사 → 교정 → 문장 저장.  다 쓰면 '다 썼어요' → 전체 글 → '이야기 저장하기'.
// 동작은 모두 writer.js 에 있고, 이 파일은 그 상태를 그리기만 한다.
//   bookId 책의 글을 열어 문장마다 저장한다 (일기는 date 의 글, 동화는 date 없이 책 하나에 이야기 한 편).
//
// 화면을 바꾸는 일은 App.jsx 가 한다. 이 화면은 아래 함수(props)를 부르기만 한다.
//   onBack()   글 목록으로 (동화는 이야기 보기로)
//   onSaved(글 번호)   '이야기 저장하기'가 끝남 → 글 조회 화면으로
//   onDateChange(날짜)   '날짜 바꾸기'로 다른 날짜의 일기를 연다
//   onAuthError()   토큰이 틀림 → 별명 화면으로
// 모양(CSS)은 아직 입히지 않았다. className 과 id 는 나중에 디자인을 입힐 때 쓰라고 남겨 둔 것이다.

import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { createWriter } from './writer.js'
import { evidenceText, fmtDate, todayKST } from './format.js'

const MAX_CHARS = 100 // backend/diary_pipeline/input_validation.py 의 MAX_CHARS 와 같은 값

// 모델을 처음 불러올 때 '○초째'를 1초마다 다시 그린다
function Elapsed({ since }) {
    const [now, setNow] = useState(since)
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 1000)
        return () => clearInterval(timer)
    }, [])
    return <> · {Math.max(0, Math.floor((now - since) / 1000))}초째</>
}

// 교정이 진행되는 동안 나오는 대로 보여 줄 내용
function WorkBlock({ work }) {
    return (
        <div className="pending">
            <div>새 문장: {work.original}</div>
            {work.status === 'error' ? (
                <div className="errmsg">{work.error}</div>
            ) : (
                <>
                    {work.progress && (
                        <div className="prog">
                            {work.progress}
                            {work.loadingSince ? <Elapsed since={work.loadingSince} /> : null}
                        </div>
                    )}
                    {work.revised && <div>고친 문장: {work.revised}</div>}
                    {(work.diff || []).map((d, i) => {
                        const exp = (work.exps || [])[i]
                        if (exp === undefined || exp === null) return null
                        return (
                            <div key={i} className="fix">
                                <div className="item">
                                    <p className="what">{i + 1}. ‘{d.before}’ → ‘{d.after}’</p>
                                    <p className="exp">{exp}</p>
                                </div>
                            </div>
                        )
                    })}
                    {work.compliment && <div>{work.compliment}</div>}
                </>
            )}
        </div>
    )
}

function FixBlock({ sentence, writer }) {
    const items = sentence.corrections || []
    if (!items.length) return sentence.compliment ? <p className="mode">{sentence.compliment}</p> : null
    return (
        <details className="fix" open={sentence.openFix === true} onToggle={(e) => writer.toggleFix(sentence.id, e.currentTarget.open)}>
            <summary>고친 곳 {items.length}개 보기</summary>
            {items.map((c, i) => (
                <div key={i} className="item">
                    <p className="what">{i + 1}. ‘{c.before}’ → ‘{c.after}’</p>
                    <p className="exp">{c.explanation || ''}</p>
                    {evidenceText(c) && <p className="ev">{evidenceText(c)}</p>}
                </div>
            ))}
        </details>
    )
}

function SentenceCard({ sentence: s, index, total, state, writer }) {
    const working = !!s.work && s.work.status !== 'error'
    const failed = !!s.work && s.work.status === 'error'
    const pill =
        !s.original && !failed ? <span className="pill">교정 중</span>
        : working ? <span className="pill">다시 교정 중</span>
        : failed ? <span className="pill err">오류</span>
        : <span className="pill ok">{s.was_corrected ? '고침' : '완료'}</span>
    const { busy } = state
    return (
        <li className={s.id === state.editingId ? 'card editing' : 'card'} id={`s-${s.id}`}>
            <div className="top">
                <span className="no">{index + 1}.</span>{' '}
                {pill}
                {state.dbMode && s.original && s.saveState === 'error' && <span className="pill err">저장 안 됨</span>}
                <span className="spacer" />
                {/* 일기만: 순서 바꾸기(위로/아래로)와 이 줄 앞에 끼워 넣기 */}
                {s.original && state.kind === 'diary' && (
                    <>
                        <button type="button" className="btn-sm" title="위로 옮기기" aria-label={`${index + 1}번째 줄 위로 옮기기`}
                                        disabled={busy || index === 0} onClick={() => writer.moveSentence(s.id, -1)}>↑</button>
                        <button type="button" className="btn-sm" title="아래로 옮기기" aria-label={`${index + 1}번째 줄 아래로 옮기기`}
                                        disabled={busy || index === total - 1} onClick={() => writer.moveSentence(s.id, 1)}>↓</button>
                        <button type="button" className="btn-sm" title="이 줄 앞에 새 문장 넣기" disabled={busy}
                                        onClick={() => writer.startInsert(s.id)}>위에 넣기</button>
                    </>
                )}
                {s.original && (
                    <button type="button" className="btn-sm" disabled={busy} title={busy ? '교정이 끝난 뒤에 고칠 수 있어요' : ''}
                                    onClick={() => writer.startEdit(s.id)}>다시쓰기</button>
                )}
                {/* 지우기: 저장이 끝난 줄만. 다시쓰기 중인 줄 · 교정 중 · 다른 줄을 지우는 중에는 잠긴다 (writer.js 의 canDelete) */}
                {state.dbMode && s.original && (
                    <button type="button" className="btn-sm del" disabled={!s.deletable || state.confirmDeleteId !== null}
                                    aria-label={`${index + 1}번째 줄 지우기`} onClick={() => writer.askDelete(s.id)}>
                        {state.deletingId === s.id ? '지우는 중…' : '지우기'}
                    </button>
                )}
            </div>
            {state.confirmDeleteId === s.id && <DeleteConfirm writer={writer} />}
            {s.original && <p className="text">{s.revised || s.original}</p>}
            {s.original && s.revised && s.revised !== s.original && <p className="orig">내가 쓴 문장: {s.original}</p>}
            {s.work && <WorkBlock work={s.work} />}
            {s.original && !s.work && <FixBlock sentence={s} writer={writer} />}
            {s.expression_choice && s.expression_choice.picked && <p className="mode">내가 고른 표현이에요.</p>}
        </li>
    )
}

// 문장 지우기 확인 (브라우저 창 대신 그 줄 안에서 묻는다). 처음 선택은 '취소', Esc 를 눌러도 취소된다.
function DeleteConfirm({ writer }) {
    const cancelRef = useRef(null)
    useEffect(() => {
        if (cancelRef.current) cancelRef.current.focus()
        const onKey = (e) => { if (e.key === 'Escape') writer.cancelDelete() }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [writer])
    return (
        <div className="confirm" role="alertdialog" aria-label="문장 지우기 확인">
            <p className="ask">이 문장을 지울까요?</p>
            <div className="row">
                <button type="button" className="btn-sm del yes" onClick={writer.confirmDelete}>지우기</button>{' '}
                <button type="button" className="btn-sm" ref={cancelRef} onClick={writer.cancelDelete}>취소</button>
            </div>
        </div>
    )
}

// 동화: 주제 추천 (추천 1개 + 다른 주제 3개 + 더 보기 + 내가 정할게요)
function TopicBox({ box, writer }) {
    return (
        <div id="topic-box">
            <p className="ask" id="topic-ask">어떤 이야기를 쓸까요? 「{box.pick}」에 대한 이야기는 어때요?</p>
            <div className="row">
                <button type="button" className="chip yes" onClick={() => writer.chooseTopic(box.pick)}>좋아요, 이 이야기로!</button>
            </div>
            <p>다른 주제도 있어요.</p>
            <div className="row" id="topic-others">
                {box.others.map((v) => (
                    <button key={v} type="button" className="chip" onClick={() => writer.chooseTopic(v)}>{v}</button>
                ))}
            </div>
            <div className="row">
                <button type="button" className="btn-sm" onClick={() => writer.openTopics(true)}>다른 주제 더 보기</button>
                <button type="button" className="btn-sm" onClick={() => writer.chooseTopic('')}>내가 정할게요</button>
            </div>
        </div>
    )
}

// 동화: 표현 추천 (바꿔 쓴 문장 + 원래 문장 그대로)
function ExprBox({ expr, writer }) {
    if (expr.status === 'loading') return <div id="expr-box"><p>다른 표현을 찾고 있어요… (처음에는 조금 오래 걸릴 수 있어요)</p></div>
    if (expr.status === 'error') {
        return (
            <div id="expr-box">
                <p className="ask">다른 표현을 불러오지 못했어요. 쓴 문장은 그대로 있어요.</p>
                <div className="row">
                    <button type="button" className="btn-sm" onClick={writer.retryExpr}>다시 불러오기</button>
                    <button type="button" className="btn-sm" onClick={writer.skipExpr}>그대로 쓸게요</button>
                </div>
            </div>
        )
    }
    // 보기 하나: 한 줄에 하나씩(div). 문장 아래 줄에 한 줄 설명(point, 무엇이 좋아졌는지)
    // (스타일 없이도 보기끼리 · 문장과 설명이 줄이 나뉘어 보이게 한다. 디자인을 입힐 때 .opt / .text / .point 를 쓰면 된다)
    const radio = (value, text, point) => (
        <div className="opt" key={value}>
            <label>
                <input type="radio" name="expr" value={value} checked={expr.value === value} onChange={() => writer.pickExpr(value)} />
                <span className="text">{text}</span>
                {point && <><br /><small className="point">{point}</small></>}
            </label>
        </div>
    )
    return (
        <div id="expr-box">
            {/* 모델이 꺼져 있을 때: 아래 보기는 모델이 만든 게 아니라 임시 예시라고 꼭 알린다 (서버 /suggest 의 notice) */}
            {expr.demo && <p className="demo-note" role="note">{expr.notice || '지금은 표현 추천 모델이 꺼져 있어요. 아래 문장은 임의로 바꿔 본 예시예요.'}</p>}
            <p className="ask">{expr.guide || '지금 문장도 좋아요. 다른 말로 쓸 수도 있어요.'}</p>
            <p>내가 쓴 문장: {expr.base}</p>
            {expr.options.map((o, i) => radio(String(i), o.text, o.point))}
            {radio('keep', '원래 문장 그대로 쓸래요', expr.originalPoint)}
            <div className="row">
                <button type="button" className="yes" onClick={writer.confirmExpr}>확인하기</button>
            </div>
        </div>
    )
}

export default function WritePage({ bookId, date, onBack, onSaved, onDateChange, onAuthError }) {
    // 이 화면의 두뇌는 한 번만 만든다. (책이나 날짜가 바뀌면 App.jsx 가 key 를 바꿔 화면을 새로 만든다)
    const [writer] = useState(() =>
        createWriter({ book: bookId, date, practice: false, onSaved, onAuthError }),
    )
    const state = useSyncExternalStore(writer.subscribe, writer.getSnapshot)
    const boxRef = useRef(null)

    useEffect(() => {
        // 한 박자 늦게 시작한다: 개발 모드(StrictMode)는 화면을 만들었다 지우고 다시 만들기 때문에,
        // 바로 시작하면 '글 열기' 요청이 동시에 두 번 나간다. 지워지는 쪽은 여기서 취소된다.
        const timer = setTimeout(() => writer.boot(), 0)
        return () => {
            clearTimeout(timer)
            writer.dispose()
        }
    }, [writer])

    // 커서 두기 · 줄이 보이게 스크롤
    useEffect(() => {
        if (state.focusTick && boxRef.current && !boxRef.current.disabled) boxRef.current.focus()
    }, [state.focusTick, state.busy])
    const scrollId = state.scrollTo ? state.scrollTo.id : null
    const scrollTick = state.scrollTo ? state.scrollTo.tick : 0
    useEffect(() => {
        if (!scrollTick) return
        const el = document.getElementById(`s-${scrollId}`)
        if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }, [scrollId, scrollTick])

    // 화면이 가려질 때(다른 앱으로 넘어감 · 화면 꺼짐 · 탭 닫힘): 쓰던 문장을 기다리지 않고 바로 임시저장한다.
    // 태블릿에서는 아래 '나가기 전 확인'이 뜨지 않는 경우가 많아서 따로 챙긴다.
    useEffect(() => {
        const onHide = () => { if (document.visibilityState === 'hidden') writer.flushDraft() }
        document.addEventListener('visibilitychange', onHide)
        window.addEventListener('pagehide', writer.flushDraft)
        return () => {
            document.removeEventListener('visibilitychange', onHide)
            window.removeEventListener('pagehide', writer.flushDraft)
        }
    }, [writer])

    // 창을 닫거나 새로고침할 때: 쓰던 글자나 저장 안 된 문장이 있으면 브라우저가 한 번 물어본다
    useEffect(() => {
        const onBeforeUnload = (e) => {
            const info = writer.unsavedWork()
            if (!info) return
            writer.noteLeave(info)
            e.preventDefault()
            e.returnValue = ''
        }
        window.addEventListener('beforeunload', onBeforeUnload)
        return () => window.removeEventListener('beforeunload', onBeforeUnload)
    }, [writer])

    // 화면 안의 버튼으로 나갈 때도 같은 것을 물어본다. 나가도 되면 move() 를 부른다
    function leave(move) {
        const info = writer.unsavedWork()
        if (info) {
            writer.noteLeave(info)
            const message = state.dbMode
                ? '확인하기를 누르지 않았거나 아직 저장되지 않은 문장이 있어요. 나가면 사라져요. 나갈까요?'
                : '연습 모드라 쓴 문장은 저장되지 않아요. 나갈까요?'
            if (!window.confirm(message)) return
        }
        move()
    }

    const entryDate = state.entry ? state.entry.date : null
    const title = !state.dbMode ? '일기 쓰기 · 연습 (저장되지 않아요)'
        : !state.entry ? '글쓰기'
        : state.kind === 'fairy' ? `${state.bookTitle}에게 들려주는 이야기`     // 동화는 날짜가 없다
        : `${state.bookTitle} · ${fmtDate(entryDate)}`
    useEffect(() => {
        document.title = state.dbMode && state.bookTitle ? `${state.bookTitle} 쓰기` : '글쓰기'
    }, [state.dbMode, state.bookTitle])

    const editing = state.sentences.find((s) => s.id === state.editingId)
    const insertNext = state.insertAt !== null ? state.sentences[state.insertAt] : null
    const written = state.sentences.filter((s) => s.original)
    const placeholder = editing ? '이 줄을 새로 적어보세요'
        : state.insertAt !== null ? '사이에 넣을 문장을 적어보세요'
        : state.kind === 'fairy' ? '상상한 이야기를 한 문장으로 적어보세요' : '오늘 있었던 일을 한 문장으로 적어보세요'

    function changeDate(e) {
        const value = e.target.value
        if (!value || value === entryDate) return
        writer.noteDateChange(entryDate, value)
        leave(() => onDateChange(value))
    }

    return (
        <div className="write-page">
            <header>
                <button type="button" className="to-list btn-sm" id="to-list" onClick={() => leave(onBack)}>
                    {state.kind === 'fairy' ? '← 이야기로' : '← 목록으로'}
                </button>
                <h1 id="title">{title}</h1>
                {state.entry && <span className="pill" id="kind-pill">{state.kind === 'fairy' ? '동화' : '일기'}</span>}{' · '}
                {state.entry && (
                    <span className={state.entry.status === 'done' ? 'pill ok' : 'pill warn'} id="entry-pill">
                        {state.entry.status === 'done' ? '완성' : '쓰는 중'}
                    </span>
                )}
                {' '}
                {state.entry && state.kind === 'diary' && (
                    <label className="day-pick" id="day-wrap">
                        날짜 바꾸기{' '}
                        {/* 고른 날짜의 일기로 옮겨 간다 (하루 = 글 하나, 앞으로 올 날짜는 못 고른다) */}
                        <input type="date" id="day-pick" value={entryDate || ''} max={todayKST()} onChange={changeDate} />
                    </label>
                )}
            </header>

            {state.loadError ? (
                <p id="savebar" className="err" role="status">
                    <span>글을 불러오지 못했어요. {state.loadError}</span>
                    <button type="button" className="btn-sm" onClick={writer.boot}>다시 시도</button>
                </p>
            ) : (
                state.save.text && (
                    <p id="savebar" className={state.save.kind} role="status">
                        <span>{state.save.text}</span>
                        {state.save.retry && <button type="button" className="btn-sm" onClick={writer.retrySaves}>다시 저장하기</button>}
                    </p>
                )
            )}

            {/* 쓰던 문장(확인하기 전) 임시저장 표시. 입력칸에 글자가 있을 때만 보인다 */}
            {state.draft && state.box.trim() && (
                <p id="draft-state" className={state.draft.status === 'error' ? 'err' : ''} role="status">
                    {state.draft.status === 'error'
                        ? '쓰던 문장을 저장하지 못했어요. 잠시 뒤에 다시 저장해요.'
                        : `쓰던 문장도 임시저장했어요${state.draft.at ? ` · ${state.draft.at}` : ''}`}
                </p>
            )}

            {/* 문장을 지운 뒤 잠깐 보이는 되돌리기 (writer.js 의 UNDO_SECONDS) */}
            {state.undo && (
                <p id="undo-bar" className={state.undo.error ? 'err' : ''} role="status">
                    <span>
                        {state.undo.error ? '되살리지 못했어요. ' : `${state.undo.seq}번째 문장을 지웠어요. `}
                    </span>
                    <button type="button" className="btn-sm" disabled={state.undo.busy || state.busy} onClick={writer.undoDelete}>
                        {state.undo.busy ? '되살리는 중…' : state.undo.error ? '다시 시도' : '되돌리기'}
                    </button>
                </p>
            )}

            {state.view === 'write' ? (
                <div id="write">
                    <ul id="list" aria-label="지금까지 쓴 문장">
                        {state.loading ? (
                            <li className="empty">불러오는 중…</li>
                        ) : state.loadError ? (
                            <li className="empty">불러오지 못했어요.</li>
                        ) : state.sentences.length === 0 ? (
                            <li className="empty">아직 쓴 문장이 없어요. 아래에 첫 문장을 적어보세요.</li>
                        ) : (
                            state.sentences.map((s, i) => (
                                <SentenceCard key={s.id} sentence={s} index={i} total={state.sentences.length} state={state} writer={writer} />
                            ))
                        )}
                    </ul>

                    <section id="composer" aria-label="문장 입력">
                        {state.topicBox && <TopicBox box={state.topicBox} writer={writer} />}
                        {state.kind === 'fairy' && state.entry && !state.topicBox && (
                            <p id="topic-line">
                                <span>{state.topic ? `주제: ${state.topic}` : '주제를 스스로 정했어요'}</span>
                                <button type="button" className="btn-sm" onClick={() => writer.openTopics(false)}>
                                    {state.topic ? '주제 바꾸기' : '주제 추천받기'}
                                </button>
                            </p>
                        )}
                        {state.expr && <ExprBox expr={state.expr} writer={writer} />}
                        {!state.topicBox && !state.expr && <p id="question">{state.question}</p>}

                        {(editing || state.insertAt !== null) && (
                            <div id="mode-bar">
                                <span id="mode-title">
                                    {editing ? `${state.sentences.indexOf(editing) + 1}번째 줄 다시 쓰기 ·` : `${state.insertAt + 1}번째 자리에 문장 넣기 ·`}
                                </span>
                                <span className="ref" id="mode-ref">
                                    {editing ? `기존: ${editing.revised || editing.original}`
                                        : insertNext ? `‘${insertNext.revised || insertNext.original}’ 앞에 들어가요` : ''}
                                </span>
                                <button type="button" className="btn-sm" id="cancel-edit" disabled={state.busy} onClick={writer.cancelEdit}>취소</button>
                            </div>
                        )}

                        <div className="row">
                            <input id="box" ref={boxRef} type="text" maxLength={MAX_CHARS} autoComplete="off" placeholder={placeholder}
                                          value={state.box} disabled={state.busy || state.loading || !!state.loadError}
                                          onChange={(e) => writer.setBox(e.target.value)}
                                          onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) writer.submit() }} />
                            <button type="button" id="go" disabled={state.busy || state.loading || !!state.loadError} onClick={writer.submit}>확인하기</button>
                        </div>

                        {state.notice && <p id="msg">{state.notice}</p>}
                        {state.shown && <p id="shown">{state.shown}</p>}
                        <div id="choices">
                            {state.choices && state.choices.items.map((item, i) => (
                                <div key={i}>
                                    &apos;{item.text}&apos; →{' '}
                                    {item.labels.map((label, n) => (
                                        <button key={n} type="button" disabled={state.busy} onClick={() => writer.choose(i, n)}>{label}</button>
                                    ))}
                                </div>
                            ))}
                        </div>

                        {state.dbMode && <p className="note" id="unsaved-note">쓰던 문장은 잠시 멈추면 임시저장돼요. 다시 들어오면 이어서 쓸 수 있어요.</p>}
                        <div className="actions">
                            <button type="button" id="finish" disabled={state.busy || written.length === 0} onClick={writer.finish}>다 썼어요</button>
                            <span className="hint" id="hint">{state.busy ? '검사·교정 중에는 다른 줄을 고칠 수 없어요' : ''}</span>
                        </div>
                    </section>
                </div>
            ) : (
                <section id="all">
                    <h2>전체 글</h2>
                    <p id="all-text">{written.map((s) => s.revised || s.original).join(' ')}</p>
                    {state.storyError && <p id="save-err">{state.storyError}</p>}
                    <div className="actions">
                        <button type="button" id="back" onClick={writer.backToWrite}>이어서 쓰기</button>
                        {state.dbMode ? (
                            <button type="button" id="save-story" className="primary" disabled={state.storySaving} onClick={writer.saveStory}>
                                {state.storySaving ? '저장 중…' : state.storyError ? '다시 저장하기' : '이야기 저장하기'}
                            </button>
                        ) : (
                            <button type="button" id="restart" onClick={writer.restart}>처음부터 다시 쓰기</button>
                        )}
                    </div>
                </section>
            )}
        </div>
    )
}
