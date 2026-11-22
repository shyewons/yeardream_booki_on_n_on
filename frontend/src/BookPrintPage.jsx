// 책 출력 화면 (책 보기 + PDF 저장). 글 목록 오른쪽 위 '책 출력하기'로 들어온다 (2026-11-20 낙준, 임시 디자인)
// GET /api/books/{책}/print → 책 한 권의 보이는 글과 문장 (동화는 1장부터, 일기는 오래된 날부터)
//
// 쪽 나누기: 쪽 상자(PAGE_W × PAGE_H, 고정 크기)에 문장을 하나씩 넣어 보고, 넘치면 그 문장부터 다음 쪽으로 보낸다.
//   - 실제로 그려 보고 높이를 재므로 문장 길이가 제각각이어도 쪽마다 고르게 찬다. 문장 하나가 두 쪽에 걸쳐 잘리지 않는다
//   - 장(동화) · 날짜(일기)가 바뀌면 다음 펼친 면(왼쪽 쪽)부터 시작한다. 장 이름(3장 · 날짜)은 그 장의 첫 쪽에만 쓰고, 이어지는 쪽은 제목 없이 글만 (그만큼 글이 더 들어간다)
//   - 쪽 상자 크기가 화면 크기와 상관없이 고정이라, 어느 기기에서 열어도 같은 쪽으로 나뉜다
// 화면: 쪽을 두 개씩 펼친 책 위에 놓고, 책의 오른쪽 · 왼쪽 끝(또는 ◀ ▶ · 키보드 ← →)으로 넘긴다
// PDF: 'PDF로 저장' → 브라우저 인쇄 창. 같은 쪽들을 A4 가로 한 장에 하나씩, 통째로 키워서 놓는다 (줄바꿈이 화면과 같다)
//
// 화면을 바꾸는 일은 App.jsx 가 한다. onBack() 글 목록으로, onAuthError() 토큰이 틀림

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { KIND_LABEL, fmtDate } from './format.js'
import { useLoad } from './useLoad.js'
import spread from './assets/backgrounds/diary-writing-spread.png'
import fairySpread from './assets/backgrounds/fairy-writing-spread.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import './BookPrintPage.css'

// 쪽 상자 크기 (px). 바꾸면 BookPrintPage.css 의 --page-w · --page-h 도 같이 바꾼다
export const PAGE_W = 400
export const PAGE_H = 360

// 표지 · 첫머리 쪽을 만들고, 글을 쪽 상자에 채워 쪽 목록을 만든다. measure 는 화면 밖에 그려 둔 빈 쪽 상자
function paginate(data, measure) {
    const fairy = data.book.kind === 'fairy'
    const total = data.parts.reduce((n, p) => n + p.sentences.length, 0)
    const pages = [
        { type: 'cover' },
        { type: 'intro', total },
    ]
    const head = measure.querySelector('.book-print__page-head')
    const body = measure.querySelector('.book-print__page-body')
    const overflows = () => body.scrollHeight > body.clientHeight + 1
    const pageEl = measure.querySelector('.book-print__page')
    // 이어지는 쪽은 제목 칸을 없앤다. 제목이 있는 쪽은 글 줄 수가 하나 적다 (--headed, BookPrintPage.css)
    const setHead = (text) => {
        head.textContent = text || ''
        head.style.display = text ? '' : 'none'
        pageEl.classList.toggle('book-print__page--headed', !!text)
    }

    for (const part of data.parts) {
        const label = fairy ? part.label : fmtDate(part.date)
        if (pages.length % 2 === 1) pages.push({ type: 'blank' })        // 새 장 · 새 날짜는 펼친 면의 왼쪽 쪽부터
        let page = { type: 'text', head: label, sentences: [] }
        setHead(page.head)
        body.replaceChildren()
        for (const text of part.sentences) {
            const p = document.createElement('p')
            p.textContent = text
            body.appendChild(p)
            if (overflows() && page.sentences.length) {
                pages.push(page)                                          // 넘치면 그 문장부터 다음 쪽으로
                page = { type: 'text', head: null, sentences: [] }      // 이어지는 쪽: 제목 없이 글만
                setHead(null)
                body.replaceChildren(p)
            }
            page.sentences.push(text)
        }
        pages.push(page)
    }
    if (pages.length % 2 === 1) pages.push({ type: 'blank' })            // 마지막 펼친 면을 채운다
    return pages
}

// 쪽 하나. 번호는 표지(1쪽)부터 센다 (표지 · 빈 쪽에는 번호를 쓰지 않는다)
function Page({ page, no, data }) {
    const fairy = data.book.kind === 'fairy'
    if (page.type === 'cover') return <div className="book-print__page book-print__page--cover">
        <p className="book-print__kind">{KIND_LABEL[data.book.kind] ?? data.book.kind}</p>
        <h2 className="book-print__title">{data.book.title}</h2>
        <img className="book-print__animal" src={fairy ? alpaca : sheep} alt="" />
        <p className="book-print__owner">지은이 {data.owner}</p>
        {data.first_at && <p className="book-print__period">{fmtDate(data.first_at)} ~ {fmtDate(data.last_at)}</p>}
    </div>
    if (page.type === 'intro') return <div className="book-print__page book-print__page--intro">
        {fairy && data.topic ? <>
            <p className="book-print__intro-label">이야기 주제</p>
            <h3 className="book-print__intro-title">{data.topic.title}</h3>
            {data.topic.opening && <p className="book-print__intro-text">{data.topic.opening}</p>}
        </> : <p className="book-print__intro-label">{fairy ? '내가 정한 이야기' : '나의 일기'}</p>}
        <p className="book-print__intro-count">
            {fairy ? `${data.parts.length}개의 장` : `${data.parts.length}일의 일기`} · {page.total}문장
        </p>
        <span className="book-print__page-no">{no}</span>
    </div>
    if (page.type === 'blank') return <div className="book-print__page book-print__page--blank" />
    return <div className={`book-print__page${page.head ? ' book-print__page--headed' : ''}`}>
        {page.head && <h3 className="book-print__page-head">{page.head}</h3>}
        <div className="book-print__page-body">{page.sentences.map((s, i) => <p key={i}>{s}</p>)}</div>
        <span className="book-print__page-no">{no}</span>
    </div>
}

export default function BookPrintPage({ bookId, onBack, onAuthError }) {
    const { data, error, retry } = useLoad(`/api/books/${bookId}/print`, onAuthError)
    const measureRef = useRef(null)
    const [pages, setPages] = useState(null)
    const [at, setAt] = useState(0)                 // 지금 펼친 면 (0 = 1 · 2쪽)
    const fairy = data?.book.kind === 'fairy'

    // 글을 받으면 글꼴이 다 불러와진 뒤에 쪽을 나눈다 (글꼴이 바뀌면 줄 수가 달라지므로)
    useLayoutEffect(() => {
        if (!data || !measureRef.current) return
        let live = true
        const run = () => { if (live) { setPages(paginate(data, measureRef.current)); setAt(0) } }
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(run)
        else run()
        return () => { live = false }
    }, [data])

    const spreads = pages ? pages.length / 2 : 0
    const go = (d) => setAt((a) => Math.min(Math.max(a + d, 0), Math.max(spreads - 1, 0)))
    useEffect(() => {
        const onKey = (e) => {
            if (e.key === 'ArrowRight') go(1)
            else if (e.key === 'ArrowLeft') go(-1)
        }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    })

    const top = <div className="book-print__topbar">
        <button className="ui-button ui-button--secondary ui-button--small" type="button" onClick={onBack}>← 목록으로</button>
        {pages && <button className="ui-button ui-button--primary ui-button--small book-print__save" type="button" onClick={() => window.print()}>PDF로 저장</button>}
    </div>

    if (error || !data) return <main className="book-print" aria-label="책 출력">
        {top}
        <div className="book-print__state">
            {error ? <div className="ui-notice ui-notice--error" role="alert">
                <p>{error.status === 404 ? '책을 찾을 수 없어요.' : `책을 불러오지 못했어요. ${error.message || ''}`}</p>
                <button className="ui-button ui-button--primary" type="button" onClick={retry}>다시 불러오기</button>
            </div> : <p className="ui-description" role="status">책을 펼치고 있어요…</p>}
        </div>
    </main>

    const left = pages ? pages[at * 2] : null
    const right = pages ? pages[at * 2 + 1] : null
    return <main className={`book-print${fairy ? ' book-print--fairy' : ''}`} aria-label="책 출력">
        {top}
        <div className="book-print__book">
            <img className="book-print__paper" src={fairy ? fairySpread : spread} alt="" />
            {pages ? <>
                <div className="book-print__slot book-print__slot--left"><Page page={left} no={at * 2 + 1} data={data} /></div>
                <div className="book-print__slot book-print__slot--right"><Page page={right} no={at * 2 + 2} data={data} /></div>
                {/* 책의 왼쪽 · 오른쪽 끝을 누르면 넘긴다 */}
                <button className="book-print__edge book-print__edge--prev" type="button" aria-label="이전 쪽" disabled={at === 0} onClick={() => go(-1)} />
                <button className="book-print__edge book-print__edge--next" type="button" aria-label="다음 쪽" disabled={at >= spreads - 1} onClick={() => go(1)} />
            </> : <p className="book-print__state" role="status">쪽을 나누고 있어요…</p>}
        </div>
        {pages && <div className="book-print__pager">
            <button className="ui-button ui-button--secondary ui-button--small" type="button" disabled={at === 0} onClick={() => go(-1)} aria-label="이전 쪽">◀</button>
            <span id="book-print-at">{at * 2 + 1}–{at * 2 + 2}쪽 / 전체 {pages.length}쪽</span>
            <button className="ui-button ui-button--secondary ui-button--small" type="button" disabled={at >= spreads - 1} onClick={() => go(1)} aria-label="다음 쪽">▶</button>
        </div>}

        {/* 쪽 나누기용 빈 쪽 상자 (화면 밖) */}
        <div className="book-print__measure" aria-hidden="true" ref={measureRef}>
            <div className="book-print__page"><h3 className="book-print__page-head" /><div className="book-print__page-body" /></div>
        </div>

        {/* 인쇄용: 모든 쪽을 A4 한 장에 하나씩 (화면에서는 숨김) */}
        {pages && <div className="book-print__all" aria-hidden="true">
            {pages.map((p, i) => <div className="book-print__sheet" key={i}><Page page={p} no={i + 1} data={data} /></div>)}
        </div>}
    </main>
}
