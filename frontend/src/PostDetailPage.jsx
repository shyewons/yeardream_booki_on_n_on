// 작성한 글 조회 화면 (요구사항정의서 차트 - 화면ID 시트 - 11번 화면)
// GET /api/entries/{글} → 문장과 고친 곳. 이전/다음 이야기, 고쳐쓰기(쓰는 중이면 이어서 쓰기).
//
// 문장이 많으면 SENTENCES_PER_PAGE 개씩 쪽을 나눠 보여 준다 (서버에서는 한 번에 받고 화면에서만 나눈다).
// 동화는 책 하나에 이야기 한 편이라 글 목록이 없다 → '목록으로' · '이전/다음 이야기' 버튼을 내지 않는다.
// saved 가 참이면 방금 '이야기 저장하기'를 누르고 온 것이라 '저장했어요' 안내를 보여 준다 (10번 화면).
//
// 화면을 바꾸는 일은 App.jsx 가 한다. 이 화면은 아래 함수(props)를 부르기만 한다.
//   onOpenEntry(글 번호)   이전/다음 이야기로
//   onWrite(날짜 또는 null)   글쓰기 화면으로 (고쳐쓰기 · 이어서 쓰기)
//   onBack()   글 목록으로        onHome()   목장으로
//   onAuthError()   토큰이 틀림 → 별명 화면으로

import { useState } from 'react'
import { evidenceText, fmtDate, fmtTime } from './format.js'
import { useLoad } from './useLoad.js'
import LoadError from './LoadError.jsx'
import Pager from './Pager.jsx'

const SENTENCES_PER_PAGE = 10 // 한 쪽에 보여 줄 문장 수 (바꾸려면 이 숫자만 고친다)

export default function PostDetailPage({ entryId, saved = false, onOpenEntry, onWrite, onBack, onHome, onAuthError }) {
    const { data, error, retry } = useLoad(`/api/entries/${entryId}`, onAuthError)

    // 지금 보고 있는 쪽. 어느 글의 쪽인지 함께 기억해서, 다른 글로 넘어가면 1쪽부터 다시 본다
    const [view, setView] = useState({ entryId, page: 1 })

    const isFairy = !!data && data.book.kind === 'fairy'
    const head = (
        <p>
            {/* 글을 불러오기 전에는 일기인지 동화인지 모르므로 '목장으로'만 보여 준다 */}
            {data && !isFairy && <><button type="button" onClick={onBack}>← 목록으로</button>{' '}</>}
            <button type="button" onClick={onHome}>{data && !isFairy ? '목장으로' : '← 목장으로'}</button>
        </p>
    )
    if (error) return <div>{head}<LoadError error={error} what="글" onRetry={retry} onHome={onHome} /></div>
    if (!data) return <div>{head}<p>불러오는 중...</p></div>

    const { entry, sentences, nav } = data
    // 처음 쓴 시각 = 글이 처음 만들어진 때, 마지막 수정 = 문장을 고친 때와 '이야기 저장하기'를 누른 때 중 나중 것
    const last = [fmtTime(entry.edited_at), fmtTime(entry.saved_at)].sort().pop()
    const when = [entry.created_at && `처음 쓴 시각 ${fmtTime(entry.created_at)}`, last && `마지막 수정 ${last}`]
        .filter(Boolean)
        .join(' · ')
    const writeDate = entry.date ? String(entry.date).slice(0, 10) : null
    // 이전 이야기 = 더 오래된 글, 다음 이야기 = 더 새 글 (없으면 누를 수 없다)
    // 문장을 쪽으로 나눈다 (마지막 쪽을 넘는 번호가 남아 있으면 마지막 쪽으로 맞춘다)
    const totalPages = Math.ceil(sentences.length / SENTENCES_PER_PAGE)
    const sentPage = Math.min(view.entryId === entryId ? view.page : 1, Math.max(1, totalPages))
    const first = (sentPage - 1) * SENTENCES_PER_PAGE
    const shown = sentences.slice(first, first + SENTENCES_PER_PAGE)

    const near = (text, to) => (
        <button type="button" disabled={!to} onClick={() => onOpenEntry(to)}>{text}</button>
    )

    return (
        <div>
            {head}
            {saved && <p className="saved" role="status">✔ 이야기를 저장했어요!</p>}
            <h1>{fmtDate(entry.date)} [{entry.status === 'done' ? '완성' : '쓰는 중'}]</h1>
            <p className="sub">{data.book.title}{when ? ` · ${when}` : ''}</p>
            {entry.draft_text && <p>쓰다가 멈춘 문장: {entry.draft_text}</p>}

            {sentences.length ? (
                <ol className="sents" start={first + 1}>
                    {shown.map((s) => (
                        <li key={s.id}>
                            <p className="text">
                                {s.revised}
                                {s.has_correction && ' [고쳤어요]'}
                                {s.attempt_count > 1 && ` [${s.attempt_count}번 만에 통과]`}
                            </p>
                            {s.has_correction && s.original !== s.revised && <p>처음에 쓴 문장: {s.original}</p>}
                            {s.expression_choice && s.expression_choice.picked && <p>내가 고른 표현이에요.</p>}
                            {s.corrections.length > 0 && (
                                <details className="fix">
                                    <summary>고친 곳 {s.corrections.length}군데</summary>
                                    {s.corrections.map((c) => (
                                        <div key={c.index}>
                                            <p>{c.before} → {c.after}</p>
                                            {c.explanation && <p>{c.explanation}</p>}
                                            {evidenceText(c) && <p>{evidenceText(c)}</p>}
                                        </div>
                                    ))}
                                </details>
                            )}
                        </li>
                    ))}
                </ol>
            ) : (
                <p className="empty">아직 쓴 문장이 없어요.</p>
            )}

            {totalPages > 1 && (
                <Pager page={sentPage} totalPages={totalPages} total={sentences.length} unit="문장"
                       onGo={(p) => setView({ entryId, page: p })} />
            )}

            <p className="near">
                {!isFairy && <>{near('이전 이야기', nav && nav.prev)}{' '}</>}
                <button type="button" onClick={() => onWrite(writeDate)}>
                    {entry.status === 'done' ? '고쳐쓰기' : '이어서 쓰기'}
                </button>
                {!isFairy && <>{' '}{near('다음 이야기', nav && nav.next)}</>}
            </p>
        </div>
    )
}
