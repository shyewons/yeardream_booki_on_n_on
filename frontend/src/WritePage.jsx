// 글쓰기 화면 (요구사항정의서 차트 - 화면ID 시트 - 05~09번 화면)
// 한 문장씩 쓴다: 확인하기 → 유효성 검사 → 교정 → 문장 저장.
//   일기: 다 쓰면 '다 썼어요' → 전체 글 → '이야기 저장하기'.
//   동화: 장(1장 ~ 100장, reward_rules.STORY_MAX_CHAPTERS)마다 쓴다. 문장은 쓰는 대로 저장되고, '이야기 끝내기'로 이야기 전체를 끝낸다 (FinishOffer).
// 동작은 모두 writer.js 에 있고, 이 파일은 그 상태를 그리기만 한다.
//   bookId 책의 글을 열어 문장마다 저장한다 (일기는 date 의 글, 동화는 date 자리의 'ch3' · 'new' 로 장을 고른다).
//
// 화면을 바꾸는 일은 App.jsx 가 한다. 이 화면은 아래 함수(props)를 부르기만 한다.
//   onBack(쪽)   글 목록으로 (동화는 장 목록으로. 쪽 = 지금 장이 있는 장 목록 쪽, 일기는 null = 보던 쪽)
//   note   앞 화면에서 넘겨준 안내 한 줄 (날짜 바꾸기 전에 저장했으면 '○○ 일기를 저장했어요.'). 없으면 null
//   onSaved(글 번호)   '이야기 저장하기' · '이야기 끝내기'가 끝남 → 글 조회 화면으로
//   onDateChange(날짜 · 장, 안내, 쓴 글 보기)   '날짜 바꾸기'로 다른 날짜의 일기를, 동화 '다음 장'으로 다음 장('ch4')을 연다 (안내는 다음 화면의 note)
//     쓴 글 보기: 동화 '이전 장 · 다음 장'을 '내가 쓴 글' 쪽에서 눌렀으면 true → 넘어간 장도 '내가 쓴 글'로 연다 (startHistory 로 돌아온다)
//   onAuthError()   토큰이 틀림 → 별명 화면으로
// 동화는 마지막 장(100장)을 채운 뒤 '← 목록으로'를 누르면, 나가기 전에 화면 안에서 끝낼지 묻는다 (FinishOffer).
// 일기는 하루치(3문장)를 채웠는데 저장하지 않고 '← 목록으로' · '날짜 바꾸기'를 하면 저장할지 묻는다 (SaveOffer). 하루치를 채우면 작은 안내(#day-done)를 띄운다.
// 동화 '← 이전 장' · '다음 장 →': 있는 장으로는 바로, 새 장은 '새로 쓸까요?'를 묻고 연다 (onDateChange 로 'ch4' 를 넘긴다).
//   마지막 장에서 새 장을 쓸 수 없으면(빈 장 · 100장 · 끝낸 이야기) '다음 장'은 눌리지 않는다. 장 번호는 화면 번호(display_no)로 보여 준다.
// 모양(CSS)은 아직 입히지 않았다. className 과 id 는 나중에 디자인을 입힐 때 쓰라고 남겨 둔 것이다.

import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { createWriter } from './writer.js'
import { evidenceText, fmtDate, todayKST } from './format.js'
import DiaryWriteView from './DiaryWriteView.jsx'

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

function SentenceCard({ sentence: s, index, total, state, writer, diary = false, onEdit }) {
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
            {diary && s.original && <div className="diary-write__sentence-head">
                <p className="text">{s.revised || s.original}</p>
                <div className="diary-write__sentence-tools">
                    <button type="button" className="diary-write__icon-button" disabled={busy} aria-label={`${index + 1}번째 문장 다시쓰기`} onClick={() => onEdit(s)}><span className="diary-write__icon diary-write__icon--pencil" /></button>
                    {state.dbMode && !state.finished && <button type="button" className="diary-write__icon-button" disabled={!s.deletable || state.confirmDeleteId !== null} aria-label={`${index + 1}번째 문장 지우기`} onClick={() => writer.askDelete(s.id)}><span className="diary-write__icon diary-write__icon--eraser" /></button>}
                    {state.kind === 'diary' && <>
                        <button type="button" className="diary-write__icon-button" disabled={busy || index === 0} aria-label={`${index + 1}번째 문장 위로 이동`} onClick={() => writer.moveSentence(s.id, -1)}><span className="diary-write__icon diary-write__icon--up" /></button>
                        <button type="button" className="diary-write__icon-button" disabled={busy || index === total - 1} aria-label={`${index + 1}번째 문장 아래로 이동`} onClick={() => writer.moveSentence(s.id, 1)}><span className="diary-write__icon diary-write__icon--down" /></button>
                    </>}
                </div>
            </div>}
            {diary && <details className="diary-write__sentence-info"><summary>문장 정보</summary><div className="diary-write__sentence-meta">
                {pill}
                {state.dbMode && s.original && s.saveState === 'error' && <span>저장 안 됨</span>}
            </div>
                {s.original && s.revised && s.revised !== s.original && <p className="orig">내가 쓴 문장: {s.original}</p>}
                {s.original && !s.work && <FixBlock sentence={s} writer={writer} />}
            </details>}
            {!diary && <div className="top">
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
                {/* 지우기: 저장이 끝난 줄만. 다시쓰기 중인 줄 · 교정 중 · 다른 줄을 지우는 중에는 잠긴다 (writer.js 의 canDelete). 끝낸 동화는 보이지 않는다 */}
                {state.dbMode && s.original && !state.finished && (
                    <button type="button" className="btn-sm del" disabled={!s.deletable || state.confirmDeleteId !== null}
                                    aria-label={`${index + 1}번째 줄 지우기`} onClick={() => writer.askDelete(s.id)}>
                        {state.deletingId === s.id ? '지우는 중…' : '지우기'}
                    </button>
                )}
            </div>}
            {state.confirmDeleteId === s.id && <DeleteConfirm writer={writer} diary={diary} />}
            {!diary && s.original && <p className="text">{s.revised || s.original}</p>}
            {!diary && s.original && s.revised && s.revised !== s.original && <p className="orig">내가 쓴 문장: {s.original}</p>}
            {s.work && <WorkBlock work={s.work} />}
            {!diary && s.original && !s.work && <FixBlock sentence={s} writer={writer} />}
            {s.expression_choice && s.expression_choice.picked && <p className="mode">내가 고른 표현이에요.</p>}
        </li>
    )
}

// 문장 지우기 확인 (브라우저 창 대신 그 줄 안에서 묻는다). 처음 선택은 '취소', Esc 를 눌러도 취소된다.
function DeleteConfirm({ writer, diary = false }) {
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
                <button type="button" className={diary ? 'ui-button ui-button--secondary ui-button--small' : 'btn-sm del yes'} onClick={writer.confirmDelete}>지우기</button>{' '}
                <button type="button" className={diary ? 'ui-button ui-button--secondary ui-button--small' : 'btn-sm'} ref={cancelRef} onClick={writer.cancelDelete}>취소</button>
            </div>
        </div>
    )
}

// 동화: 다음 장을 새로 쓸지 묻기. 처음 선택은 '이 장 계속 쓰기', Esc 를 눌러도 같다.
// short: 이 장이 아직 선물 기준(rules.story_chapter_min_sentences)에 모자라면 { have, need }, 채웠으면 null
function NextChapterAsk({ chapterNo, writer, onGo, short }) {
    const stayRef = useRef(null)
    useEffect(() => {
        if (stayRef.current) stayRef.current.focus()
        const onKey = (e) => { if (e.key === 'Escape') writer.closeNext() }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [writer])
    return (
        <div className="confirm" id="next-ask" role="alertdialog" aria-label="다음 장 쓰기">
            <p className="ask">{chapterNo}장은 여기까지 쓸까요? {chapterNo + 1}장을 새로 써요.</p>
            {short && (
                <p className="note" id="next-gift-note">
                    🎁 {chapterNo}장은 지금 {short.have}문장이에요. {short.need}문장을 채워야 선물에 세어져요. (나중에 돌아와 더 써도 돼요)
                </p>
            )}
            <div className="row">
                <button type="button" className="ui-button ui-button--primary" id="next-yes" onClick={() => { writer.closeNext(); onGo() }}>{chapterNo + 1}장 쓰기</button>{' '}
                <button type="button" className="ui-button ui-button--secondary" id="next-stay" ref={stayRef} onClick={writer.closeNext}>{chapterNo}장 계속 쓰기</button>
            </div>
        </div>
    )
}

// 동화: 이야기 끝내기 묻기 (나갈 때 마지막 장, 또는 '이야기 끝내기' 버튼). 처음 선택은 '계속 쓸래요', Esc 를 눌러도 같다.
function FinishOffer({ ask, writer, onLeave, saving, error }) {
    const stayRef = useRef(null)
    useEffect(() => {
        if (stayRef.current) stayRef.current.focus()
        const onKey = (e) => { if (e.key === 'Escape') writer.closeComplete('esc') }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [writer])
    // 숫자는 장 번호가 아니라 '기준(3문장)을 채운 장'의 개수다 (빈 장 · 1~2문장 장은 세지 않는다)
    const counted = `${ask.min}문장 이상 쓴 장이 ${ask.upto || ask.qualified}개`
    const question = ask.last ? `마지막 장(${ask.max}장)까지 다 썼어요! 이야기를 끝낼까요?`
        : ask.upto ? `${counted}가 됐어요. 여기서 이야기를 끝낼까요, 다음에 이어 쓸까요?`
        : `${counted}예요. 이야기를 끝낼까요?`
    return (
        <div className="confirm" id="complete-offer" role="alertdialog" aria-label="이야기 끝내기">
            <p className="ask">{question}</p>
            <p className="note">끝내면 새 장은 더 쓸 수 없고, 고쳐 쓰기만 할 수 있어요.</p>
            {error && <p role="alert" id="finish-error">{error}</p>}
            <div className="row">
                <button type="button" className="ui-button ui-button--primary" id="complete-yes" disabled={saving} onClick={writer.completeNow}>
                    {saving ? '끝내는 중…' : '이야기 끝내기'}
                </button>{' '}
                {ask.from === 'leave' && (
                    <>
                        <button type="button" className="ui-button ui-button--secondary" id="complete-later" disabled={saving}
                                onClick={() => { writer.closeComplete('later'); onLeave() }}>다음에 이어 쓸래요</button>{' '}
                    </>
                )}
                <button type="button" className="ui-button ui-button--secondary" id="complete-stay" ref={stayRef} disabled={saving}
                        onClick={() => writer.closeComplete('stay')}>계속 쓸래요</button>
            </div>
        </div>
    )
}

// 일기: 하루치를 채웠는데 저장하지 않고 나가려 할 때 묻기. 처음 선택은 '계속 쓸래요', Esc 를 눌러도 같다.
function SaveOffer({ writer, onLeave, saving, error }) {
    const stayRef = useRef(null)
    useEffect(() => {
        if (stayRef.current) stayRef.current.focus()
        const onKey = (e) => { if (e.key === 'Escape') writer.closeSave('esc') }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [writer])
    return (
        <div className="confirm" id="save-offer" role="alertdialog" aria-label="일기 저장하기">
            <p className="ask">일기를 저장할까요?</p>
            <p className="note">저장하면 목록에 '완성'으로 보여요. 저장하지 않아도 쓴 문장은 그대로 남아요.</p>
            {error && <p role="alert" id="save-offer-error">{error}</p>}
            <div className="row">
                <button type="button" className="ui-button ui-button--primary" id="save-yes" disabled={saving} onClick={writer.saveStory}>
                    {saving ? '저장 중…' : '저장하기'}
                </button>{' '}
                <button type="button" className="ui-button ui-button--secondary" id="save-later" disabled={saving}
                        onClick={() => { writer.closeSave('leave'); onLeave() }}>저장하지 않고 나갈래요</button>{' '}
                <button type="button" className="ui-button ui-button--secondary" id="save-stay" ref={stayRef} disabled={saving}
                        onClick={() => writer.closeSave('stay')}>계속 쓸래요</button>
            </div>
        </div>
    )
}

// 동화: 주제 바꾸기 (추천 1개 + 다른 주제 3개 + 더 보기 + 내가 정할래요 + 그대로 둘래요)
// 주제는 새 책 만들기에서 고르고, 여기서는 책의 첫 문장을 쓰기 전에만 바꿀 수 있다 (writer.topicChangeable. 2장부터는 못 바꾼다)
function TopicBox({ box, writer, error }) {
    return (
        <div id="topic-box">
            <p className="ask" id="topic-ask">어떤 이야기를 쓸까요? 「{box.pick}」에 대한 이야기는 어때요?</p>
            <div className="row">
                <button type="button" className="ui-button ui-button--primary ui-button--small" onClick={() => writer.chooseTopic(box.pick)}>좋아요, 이 이야기로!</button>
            </div>
            <p>다른 주제도 있어요.</p>
            <div className="row" id="topic-others">
                {box.others.map((v) => (
                    <button key={v} type="button" className="ui-button ui-button--secondary ui-button--small" onClick={() => writer.chooseTopic(v)}>{v}</button>
                ))}
            </div>
            <div className="row">
                <button type="button" className="ui-button ui-button--secondary ui-button--small" onClick={() => writer.openTopics(true)}>다른 주제 더 보기</button>
                <button type="button" className="ui-button ui-button--secondary ui-button--small" onClick={() => writer.chooseTopic('')}>내가 정할래요</button>
                <button type="button" className="ui-button ui-button--secondary ui-button--small" id="topic-keep" onClick={writer.closeTopics}>그대로 둘래요</button>
            </div>
            {error && <p role="alert" id="topic-error">{error}</p>}
        </div>
    )
}

// 동화: 표현 추천 (바꿔 쓴 문장 + 원래 문장 그대로)
function ExprBox({ expr, writer }) {
    // 찾는 중에도 '내가 쓴 문장'은 다 찾은 뒤와 같은 자리에 먼저 보여 준다 (글이 사라졌다가 다시 나타나지 않게, 2026-11-20). 보기 자리에만 안내를 띄운다
    if (expr.status === 'loading') return (
        <div id="expr-box">
            <div className="fairy-write__expression-original"><h2>내가 쓴 문장</h2><p>{expr.base}</p></div>
            <div className="fairy-write__expression-options">
                <p className="ask" role="status">다른 표현을 찾고 있어요… (처음에는 조금 오래 걸릴 수 있어요)</p>
            </div>
        </div>
    )
    if (expr.status === 'error') {
        return (
            <div id="expr-box">
                <p className="ask">다른 표현을 불러오지 못했어요. 쓴 문장은 그대로 있어요.</p>
                <p className="fairy-write__expression-original">{expr.base}</p>
                <div className="row">
                    <button type="button" className="ui-button ui-button--primary" onClick={writer.retryExpr}>다시 불러오기</button>
                    <button type="button" className="ui-button ui-button--secondary" onClick={writer.skipExpr}>그대로 쓸게요</button>
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
                {point && <small className="point">{point}</small>}
            </label>
        </div>
    )
    return (
        <div id="expr-box">
            <div className="fairy-write__expression-original"><h2>내가 쓴 문장</h2><p>{expr.base}</p></div>
            <div className="fairy-write__expression-options" role="radiogroup" aria-label="다른 표현 고르기" tabIndex={0}>
            {/* 모델이 꺼져 있을 때: 아래 보기는 모델이 만든 게 아니라 임시 예시라고 꼭 알린다 (서버 /suggest 의 notice) */}
            {expr.demo && <p className="demo-note" role="note">{expr.notice || '지금은 표현 추천 모델이 꺼져 있어요. 아래 문장은 임의로 바꿔 본 예시예요.'}</p>}
            <p className="ask">{expr.guide || '지금 문장도 좋아요. 다른 말로 쓸 수도 있어요.'}</p>
            {expr.options.map((o, i) => radio(String(i), o.text, o.point))}
            {radio('keep', '원래 문장 그대로 쓸래요', expr.originalPoint)}
            </div>
            <div className="row">
                <button type="button" className="ui-button ui-button--primary" onClick={writer.confirmExpr}>확인하기</button>
            </div>
        </div>
    )
}

export default function WritePage({ bookId, bookKind, date, note = null, startHistory = false, onBack, onSaved, onDateChange, onAuthError }) {
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
        if (state.focusTick && boxRef.current && !boxRef.current.disabled) boxRef.current.focus({ preventScroll: true })
    }, [state.focusTick, state.busy, state.kind])
    const scrollId = state.scrollTo ? state.scrollTo.id : null
    const scrollTick = state.scrollTo ? state.scrollTo.tick : 0
    useEffect(() => {
        if (!scrollTick) return
        const el = document.getElementById(`s-${scrollId}`)
        if (el && !el.closest('[inert]')) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
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

    // 목록으로: 동화는 지금 장이 있는 쪽을 함께 알려 준다 (장 목록이 그 쪽을 연다). 일기는 보던 쪽 그대로
    function back() {
        const per = state.rules ? state.rules.story_chapters_per_page : 10
        const no = state.displayNo || state.chapterNo
        onBack(state.kind === 'fairy' && no ? Math.ceil(no / per) : null)
    }

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
        : state.kind === 'fairy' ? `『${state.bookTitle}』 ${state.displayNo || state.chapterNo || 1}장 ${state.finished ? '고쳐 쓰기' : '쓰기'}`   // 동화는 날짜 대신 장. 책 이름이 주제 이름 · 문장일 수 있어 『』로 감싼다
        : `${state.bookTitle} · ${fmtDate(entryDate)}`
    useEffect(() => {
        document.title = state.dbMode && state.bookTitle ? `${state.bookTitle} 쓰기` : '글쓰기'
    }, [state.dbMode, state.bookTitle])

    // 일기 날짜가 오늘에서 며칠 지났는지. 보상 기준 일수(rules.diary_late_days)를 넘었을 때만 숫자, 아니면 null
    const lateDays = (() => {
        if (state.kind !== 'diary' || !entryDate || !state.rules) return null
        const days = Math.round((Date.parse(todayKST()) - Date.parse(entryDate)) / 86400000)
        return days > state.rules.diary_late_days ? days : null
    })()

    // 동화: 지금 장이 아직 선물 기준 문장 수에 모자라면 { have, need } ('다음 장' 묻기에 안내)
    const giftNeed = state.rules ? state.rules.story_chapter_min_sentences : 3
    const giftHave = state.sentences.filter((s) => s.original).length
    const giftShort = state.kind === 'fairy' && giftHave < giftNeed ? { have: giftHave, need: giftNeed } : null

    const editing = state.sentences.find((s) => s.id === state.editingId)
    const insertNext = state.insertAt !== null ? state.sentences[state.insertAt] : null
    const written = state.sentences.filter((s) => s.original)
    const placeholder = editing ? '이 줄을 새로 적어보세요'
        : state.insertAt !== null ? '사이에 넣을 문장을 적어보세요'
        : state.kind === 'fairy' ? '상상한 이야기를 한 문장으로 적어보세요' : '오늘 있었던 일을 한 문장으로 적어보세요'

    // 동화 '다음 장': 다음 장이 이미 있으면 바로 넘어가고, 새 장이면 먼저 묻는다
    const nav = writer.chapterNav()
    // 장 이동 버튼은 '내가 쓴 글'(책 왼쪽 쪽)과 '문장 쓰기'(오른쪽 쪽)에 같이 있다. 누른 쪽을 기억해 넘어간 장도 같은 쪽으로 연다
    const fromHistory = (e) => !!e?.currentTarget?.closest('.diary-write__page--left')
    function goNext(e) {
        const next = writer.chapterNav().next
        if (!next) return
        const history = fromHistory(e)
        if (next.isNew) writer.askNext()        // 새 장은 빈 장이라 '내가 쓴 글'이 없다 → 문장 쓰기로 연다
        else leave(() => onDateChange(next.target, null, history))
    }
    function goPrev(e) {
        const prev = writer.chapterNav().prev
        const history = fromHistory(e)
        if (prev) leave(() => onDateChange(prev.target, null, history))
    }

    function changeDate(e) {
        const value = e.target.value
        if (!value || value === entryDate) return
        writer.noteDateChange(entryDate, value)
        // saved: 묻는 창에서 '저장하기'를 눌러 저장하고 가는지 → 다음 화면에 '○○ 일기를 저장했어요'를 띄운다
        const go = (saved) => onDateChange(value, saved === true ? `${fmtDate(entryDate)} 일기를 저장했어요.` : null)
        if (!writer.askSave(go)) leave(go)            // 저장 안 한 하루치 일기면 먼저 묻는다 (저장하면 고른 날짜로 간다)
    }

    // 일기와 동화가 책 레이아웃을 공유하며, 검사·저장·장 이동은 기존 writer를 사용한다.
    const fairy = state.kind === 'fairy' || (!state.entry && bookKind === 'fairy') || /^(ch\d+|new)$/.test(date || '')
    // 글을 불러오기 전에도 새 화면으로 그린다: 일기 책이면(bookKind) 날짜 없이 열어도(새 책 → 바로 쓰기 · 오늘 일기) 예전 화면이 잠깐 비치지 않게
    if (state.entry || fairy || bookKind === 'diary' || /^\d{4}-/.test(date || '')) {
        const storyContext = fairy && <>
            {state.finished && <p id="finished-note" role="status" className="ui-description">끝낸 이야기예요. 다시쓰기로 문장을 고칠 수 있어요.</p>}
            {!state.finished && state.rules && (state.displayNo || state.chapterNo) >= state.rules.story_max_chapters && <p id="last-chapter" role="status" className="ui-description">이번이 마지막 장({state.rules.story_max_chapters}장)이에요.</p>}
            <details className="fairy-write__context" key={written.length ? 'written' : 'empty'} open={!written.length}>
                <summary>이야기 주제{state.prevTail?.sentences?.length ? ' · 앞 장 보기' : ''}</summary>
                <div className="fairy-write__context-scroll">
                    {state.prevTail?.sentences?.length > 0 && <div id="prev-tail"><p>지난 {state.prevTail.display_no || state.prevTail.chapter_no}장에서</p><p>{state.prevTail.sentences.join(' ')}</p></div>}
                    {state.topicBox ? <TopicBox box={state.topicBox} writer={writer} error={state.topicError} /> : <div id="topic-line">
                        <p>{state.topic ? `주제: ${state.topic}` : '주제를 스스로 정했어요'}</p>
                        {state.topicPrompt && <p id="topic-prompt">{state.topicPrompt}</p>}
                        {/* 시작 상황은 이야기의 첫 장에서만 (이어 쓰는 장에서는 앞 장의 끝 문장을 보여 준다) */}
                        {state.topicOpening && (state.displayNo || state.chapterNo) === 1 && <p id="topic-opening">{state.topicOpening}</p>}
                        {writer.topicChangeable() && <button type="button" className="ui-button ui-button--secondary ui-button--small" onClick={() => writer.openTopics(false)}>{state.topic ? '주제 바꾸기' : '주제 추천받기'}</button>}
                    </div>}
                </div>
            </details>
        </>
        const chapterActions = fairy && <div className="ui-actions fairy-write__chapter-actions">
            <button className="ui-button ui-button--secondary ui-button--small" type="button" id="prev-chapter" disabled={state.busy || !nav.prev} onClick={goPrev}>← 이전 장</button>
            <button className="ui-button ui-button--secondary ui-button--small" type="button" id="next-chapter" disabled={state.busy || !nav.next} onClick={goNext}>다음 장 →</button>
            {writer.canFinish() && <button className="ui-button ui-button--primary ui-button--small" type="button" id="finish-story" disabled={state.busy} onClick={writer.openFinish}>이야기 끝내기</button>}
        </div>
        // 일기: 앞 화면에서 저장하고 넘어온 안내 · 하루치(3문장) 안내 · 오래된 날짜 안내 (동화의 storyContext 자리에 같이 넣는다)
        const diaryContext = !fairy && (note || state.dayDoneAt || lateDays !== null) && <div className="diary-write__notes">
            {note && <p id="saved-note" className="ui-description" role="status">✔ {note}</p>}
            {state.dbMode && state.dayDoneAt && <p id="day-done" className="ui-description" role="status">
                ✓ 이 날 일기는 하루치({state.rules ? state.rules.diary_day_sentences : 3}문장)를 채웠어요. 문장을 고치거나 지워도 그대로 인정돼요.
            </p>}
            {state.dbMode && !state.dayDoneAt && lateDays !== null && <p id="late-note" className="ui-description" role="status">
                {lateDays}일 전 일기라 보상 기록에는 들어가지 않아요. 일기는 그대로 쓰고 저장할 수 있어요.
            </p>}
        </div>
        // 화면 가운데 묻는 창: 동화는 다음 장 · 끝내기, 일기는 저장할까요 ('저장하지 않고 나갈래요'는 브라우저 확인창 없이 쓰던 글자를 임시저장하고 나간다)
        const storyDialog = state.nextAsk ? <NextChapterAsk chapterNo={state.displayNo || state.chapterNo} writer={writer} short={giftShort} onGo={() => { const next = writer.chapterNav().next; if (next) leave(() => onDateChange(next.target)) }} />
            : state.finishAsk ? <FinishOffer ask={state.finishAsk} writer={writer} onLeave={() => leave(back)} saving={state.finishSaving} error={state.finishError} />
            : state.saveAsk ? <SaveOffer writer={writer} onLeave={() => { writer.flushDraft(); (writer.pendingNext() || back)() }} saving={state.storySaving} error={state.storyError} />
            : null
        return <DiaryWriteView
            state={state} writer={writer} boxRef={boxRef} onChangeDate={changeDate}
            // 목록으로: 동화는 끝낼지(마지막 장), 일기는 저장할지(하루치 채우고 저장 전) 먼저 묻는다. 동화는 지금 장이 있는 쪽으로 돌아간다 (back)
            onBack={() => { if (fairy ? !writer.askComplete() : !writer.askSave()) leave(back) }} maxChars={MAX_CHARS}
            renderWork={(work) => <WorkBlock work={work} />}
            SentenceComponent={SentenceCard}
            fairy={fairy} storyContext={fairy ? storyContext : diaryContext} chapterActions={chapterActions} storyDialog={storyDialog}
            startHistory={startHistory}
            expression={fairy && state.expr ? <ExprBox expr={state.expr} writer={writer} /> : null}
        />
    }

    return (
        <div className="write-page">
            <header>
                <button type="button" className="to-list btn-sm" id="to-list" onClick={() => { if (!writer.askComplete() && !writer.askSave()) leave(back) }}>
                    ← 목록으로
                </button>
                <h1 id="title">{title}</h1>
                {state.entry && <span className="pill" id="kind-pill">{state.kind === 'fairy' ? '동화' : '일기'}</span>}{' · '}
                {state.entry && (
                    <span className={(state.kind === 'fairy' ? state.finished : state.entry.status === 'done') ? 'pill ok' : 'pill warn'} id="entry-pill">
                        {(state.kind === 'fairy' ? state.finished : state.entry.status === 'done') ? '완성' : '쓰는 중'}
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

            {state.nextAsk && (
                <NextChapterAsk chapterNo={state.displayNo || state.chapterNo} writer={writer} short={giftShort}
                                onGo={() => { const next = writer.chapterNav().next; if (next) leave(() => onDateChange(next.target)) }} />
            )}

            {state.finishAsk && (
                <FinishOffer ask={state.finishAsk} writer={writer} onLeave={() => leave(back)}
                             saving={state.finishSaving} error={state.finishError} />
            )}

            {/* 앞 화면에서 저장하고 넘어왔다는 안내 (예: 날짜 바꾸기 전에 '저장하기') */}
            {note && <p id="saved-note" className="saved" role="status">✔ {note}</p>}

            {/* '저장하지 않고 나갈래요'는 이미 한 번 물은 것이라 브라우저 확인창은 띄우지 않는다. 쓰던 글자는 나가기 전에 임시저장한다 */}
            {state.saveAsk && (
                <SaveOffer writer={writer} onLeave={() => { writer.flushDraft(); (writer.pendingNext() || back)() }} saving={state.storySaving} error={state.storyError} />
            )}

            {/* 일기: 하루치(3문장)를 채웠다는 작은 안내 (보상 기준. 저장 버튼을 누르지 않아도 이미 채운 것이다) */}
            {state.kind === 'diary' && state.dbMode && state.dayDoneAt && (
                <p id="day-done" className="note" role="status">
                    ✓ 이 날 일기는 하루치({state.rules ? state.rules.diary_day_sentences : 3}문장)를 채웠어요. 문장을 고치거나 지워도 그대로 인정돼요.
                </p>
            )}

            {/* 일기: 오래된 날짜 안내. 날짜 + rules.diary_late_days(3일)가 지난 일기는 써도 하루치(보상 기록)에 들어가지 않는다 */}
            {state.kind === 'diary' && state.dbMode && !state.dayDoneAt && lateDays !== null && (
                <p id="late-note" className="note" role="status">
                    {lateDays}일 전 일기라 보상 기록에는 들어가지 않아요. 일기는 그대로 쓰고 저장할 수 있어요.
                </p>
            )}

            {/* 동화: 마지막 장 안내 · 끝낸 이야기 안내 */}
            {state.kind === 'fairy' && state.entry && !state.finished && state.rules && (state.displayNo || state.chapterNo) >= state.rules.story_max_chapters && (
                <p id="last-chapter" role="status">이번이 마지막 장({state.rules.story_max_chapters}장)이에요.</p>
            )}
            {state.kind === 'fairy' && state.finished && (
                <p id="finished-note" role="status">끝낸 이야기예요. 다시쓰기로 문장을 고칠 수 있어요.</p>
            )}

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
                    {/* 동화: 앞 장의 마지막 문장 (이어지는 느낌용) */}
                    {state.kind === 'fairy' && state.prevTail && state.prevTail.sentences.length > 0 && (
                        <div id="prev-tail" className="prev-tail">
                            <p className="label">지난 {state.prevTail.display_no || state.prevTail.chapter_no}장에서</p>
                            <p className="text">{state.prevTail.sentences.join(' ')}</p>
                        </div>
                    )}
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
                        {state.topicBox && <TopicBox box={state.topicBox} writer={writer} error={state.topicError} />}
                        {state.kind === 'fairy' && state.entry && !state.topicBox && (
                            <p id="topic-line">
                                <span>{state.topic ? `주제: ${state.topic}` : '주제를 스스로 정했어요'}</span>
                                {state.topicPrompt && <><br /><span id="topic-prompt">{state.topicPrompt}</span></>}
                                {/* 시작 상황은 이야기의 첫 장에서만 (이어 쓰는 장에서는 앞 장의 끝 문장을 보여 준다) */}
                                {state.topicOpening && (state.displayNo || state.chapterNo) === 1 && (
                                    <><br /><span id="topic-opening">{state.topicOpening}</span></>
                                )}
                                {writer.topicChangeable() && (
                                    <>
                                        {' '}
                                        <button type="button" className="btn-sm" onClick={() => writer.openTopics(false)}>
                                            {state.topic ? '주제 바꾸기' : '주제 추천받기'}
                                        </button>
                                    </>
                                )}
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

                        {/* 끝낸 동화는 다시쓰기를 누른 동안에만 입력칸을 보여 준다 */}
                        {(!state.finished || editing) && <div className="row">
                            <input id="box" ref={boxRef} type="text" maxLength={MAX_CHARS} autoComplete="off" placeholder={placeholder}
                                          value={state.box} disabled={state.busy || state.loading || !!state.loadError}
                                          onChange={(e) => writer.setBox(e.target.value)}
                                          onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) writer.submit() }} />
                            <button type="button" id="go" disabled={state.busy || state.loading || !!state.loadError} onClick={writer.submit}>확인하기</button>
                        </div>}

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
                            {state.kind === 'fairy' ? (
                                <>
                                    {state.entry && (
                                        <>
                                            <button type="button" id="prev-chapter" disabled={state.busy || !nav.prev} onClick={goPrev}>← 이전 장</button>{' '}
                                            <button type="button" id="next-chapter" disabled={state.busy || !nav.next} onClick={goNext}>다음 장 →</button>{' '}
                                        </>
                                    )}
                                    {writer.canFinish() && (
                                        <button type="button" id="finish-story" disabled={state.busy} onClick={writer.openFinish}>이야기 끝내기</button>
                                    )}
                                </>
                            ) : (
                                <button type="button" id="finish" disabled={state.busy || written.length === 0} onClick={writer.finish}>다 썼어요</button>
                            )}
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
