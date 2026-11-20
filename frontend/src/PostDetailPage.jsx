// 작성한 글 조회 화면 (요구사항정의서 차트 - 화면ID 시트 - 11번 화면)
// GET /api/entries/{글} → 문장과 고친 곳. 이전/다음 이야기, 고쳐쓰기(쓰는 중이면 이어서 쓰기).
//
// 일기: 문장이 많으면 책 안에서 스크롤해서 본다 (예전에는 SENTENCES_PER_PAGE 개씩 쪽을 나눴는데, 글쓰기 화면의 '내가 쓴 글'과 같게 바꿨다).
// 동화: 한 장 = 한 쪽. 장 첫머리에 앞 장의 마지막 문장(prev_tail)을 살짝 보여 주고, '이전 장 · 다음 장'으로 넘긴다.
//       끝낸 이야기는 '고쳐쓰기', 아니면 '이어서 쓰기'로 그 장을 연다.
// saved 가 참이면 방금 '이야기 저장하기'를 누르고 온 것이라 '저장했어요' 안내를 보여 준다 (10번 화면).
//
// 모양(2026-11-20 임시 디자인, 낙준): 디자인 시안 11번이 아직 없어서, 글쓰기 화면(DiaryWriteView)에서 '← 내가 쓴 글 보기'를 눌렀을 때의
//   책 왼쪽 쪽(diary-write--history) 모양을 그대로 가져다 썼다. 이 화면만의 모양은 PostDetailPage.css (.post-detail__…) 에 모아 두었다.
//   시안 11번이 나오면 그 기준으로 다시 맞춰 주세요.
//   id · class 중 .saved · #prev-tail · .sents · .near · #post-detail-title 은 시험과 다른 코드가 찾으므로 남겨 주세요.
//   문장은 글만 보여 준다 (고친 곳 · 고른 표현 표시 없음. 고친 말 형광펜이 필요하면 DiaryWriteView 의 CorrectedText 와 같은 방식으로 다시 넣는다)
//
// 화면을 바꾸는 일은 App.jsx 가 한다. 이 화면은 아래 함수(props)를 부르기만 한다.
//   onOpenEntry(글 번호)   이전/다음 이야기로
//   onWrite(날짜 · 장, 쓴 문장 있음)   글쓰기 화면으로 (고쳐쓰기 · 이어서 쓰기. 동화는 chapterTarget(장 번호)).
//     쓴 문장이 있으면 글쓰기 화면이 불러오는 동안에도 펼친 책으로 그린다 (다 불러온 뒤 한 쪽 → 펼친 책으로 바뀌며 넘어가지 않게)
//   onBack(쪽)   글 목록으로 (동화는 이 장이 있는 장 목록 쪽, 일기는 null = 보던 쪽)        onHome()   목장으로
//   onAuthError()   토큰이 틀림 → 별명 화면으로

import { KIND_LABEL, chapterTarget, fmtDate, fmtTime } from './format.js'
import { useLoad } from './useLoad.js'
import spread from './assets/backgrounds/diary-writing-spread.png'
import fairySpread from './assets/backgrounds/fairy-writing-spread.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import './DiaryWriteView.css'
import './PostDetailPage.css'

// 글쓰기 화면과 같은 책 (왼쪽 쪽을 펼친 모양). 위: 목록으로 · 목장으로, 책 왼쪽 쪽: 머리(종류 · 날짜/장 · 완성) + 내용 + 아래 버튼
function DetailBook({ kind, label, status, onList, onHome, children, actions }) {
    const fairy = kind === 'fairy'
    return <main className={`diary-write diary-write--spread diary-write--history${fairy ? ' diary-write--fairy' : ''} post-detail`} aria-labelledby="post-detail-title">
        <div className="diary-write__topbar post-detail__topbar">
            {onList && <button className="ui-button ui-button--secondary ui-button--small" type="button" onClick={onList}>← 목록으로</button>}
            <button className="ui-button ui-button--secondary ui-button--small post-detail__farm" type="button" onClick={onHome}>목장으로</button>
        </div>
        <div className="diary-write__viewport">
            <div className="diary-write__book">
                <img className="diary-write__paper" src={fairy ? fairySpread : spread} alt="" />
                <section className="diary-write__page diary-write__page--left">
                    <div className="diary-write__page-header">
                        <p className="diary-write__category">{kind ? (KIND_LABEL[kind] ?? kind) : '글'}</p>
                        <h1 className="post-detail__title" id="post-detail-title">
                            {label || '글 보기'}
                            {status && <span className={`post-detail__status${status === '완성' ? ' is-done' : ''}`}>{status}</span>}
                        </h1>
                    </div>
                    {children}
                    {actions}
                </section>
                <section className="diary-write__page diary-write__page--right" inert aria-hidden="true" />
            </div>
        </div>
        {kind && <div className="diary-write__mascot" aria-hidden="true"><img src={fairy ? alpaca : sheep} alt="" /></div>}
    </main>
}

export default function PostDetailPage({ entryId, saved = false, onOpenEntry, onWrite, onBack, onHome, onAuthError }) {
    const { data, error, retry } = useLoad(`/api/entries/${entryId}`, onAuthError)

    const isFairy = !!data && data.book.kind === 'fairy'
    // 동화는 이 장이 있는 장 목록 쪽으로 돌아간다 (한 쪽 장 수는 서버 rules.story_chapters_per_page)
    function backToList() {
        if (!isFairy) return onBack(null)
        const per = data.rules ? data.rules.story_chapters_per_page : 10
        onBack(Math.ceil((data.entry.display_no || data.entry.chapter_no || 1) / per))
    }

    // 불러오기 전 · 실패: 같은 책 안에서 안내 (글을 불러오기 전에는 '목장으로'만 보여 준다)
    if (error || !data) return <DetailBook onHome={onHome}>
        <div className="diary-write__load-state post-detail__state">
            {error ? <div className="ui-notice ui-notice--error" role="alert">
                <p>{error.status === 404 ? '글을 찾을 수 없어요.' : `글을 불러오지 못했어요. ${error.message || ''}`}</p>
                <button className="ui-button ui-button--primary" type="button" onClick={retry}>다시 불러오기</button>
            </div> : <p className="ui-description ui-muted" role="status">글을 불러오고 있어요</p>}
        </div>
    </DetailBook>

    const { entry, sentences, nav } = data
    // 처음 쓴 시각 = 글이 처음 만들어진 때, 마지막 수정 = 문장을 고친 때와 '이야기 저장하기'를 누른 때 중 나중 것
    const last = [fmtTime(entry.edited_at), fmtTime(entry.saved_at)].sort().pop()
    const when = [entry.created_at && `처음 쓴 시각 ${fmtTime(entry.created_at)}`, last && `마지막 수정 ${last}`]
        .filter(Boolean)
        .join(' · ')
    const writeDate = isFairy ? chapterTarget(entry.chapter_no || 1) : entry.date ? String(entry.date).slice(0, 10) : null
    const done = isFairy ? !!(data.story && data.story.finished) : entry.status === 'done'
    // 제목: 일기는 날짜, 동화는 날짜가 없으니 책 이름 『○○』 과 장 번호 (책 이름이 주제 이름 · 문장일 수 있어 '에게 들려준 이야기'는 쓰지 않는다)
    const label = isFairy ? `『${data.book.title}』 ${entry.display_no || entry.chapter_no || 1}장` : fmtDate(entry.date)

    // 이전 이야기 = 더 오래된 글, 다음 이야기 = 더 새 글 (없으면 누를 수 없다)
    const near = (text, to) => (
        <button className="ui-button ui-button--secondary" type="button" disabled={!to} onClick={() => onOpenEntry(to)}>{text}</button>
    )
    const actions = <div className="ui-actions near post-detail__near">
        {near(isFairy ? '← 이전 장' : '← 이전 이야기', nav && nav.prev)}
        <button className="ui-button ui-button--primary" type="button" onClick={() => onWrite(writeDate, sentences.length > 0)}>
            {done ? '고쳐쓰기' : '이어서 쓰기'}
        </button>
        {near(isFairy ? '다음 장 →' : '다음 이야기 →', nav && nav.next)}
    </div>

    return <DetailBook kind={data.book.kind} label={label} status={done ? '완성' : '쓰는 중'} onList={backToList} onHome={onHome} actions={actions}>
        <div className="diary-write__page-navigation diary-write__page-navigation--left post-detail__head">
            <h2 className="diary-write__history-title">내가 쓴 글</h2>
            <p className="ui-description ui-muted sub">{[isFairy ? '동화' : data.book.title, when].filter(Boolean).join(' · ')}</p>
        </div>
        {saved && <p className="saved ui-notice post-detail__notice" role="status">✔ 이야기를 저장했어요!</p>}
        {entry.draft_text && <p className="ui-description post-detail__draft">쓰다가 멈춘 문장: {entry.draft_text}</p>}
        {isFairy && data.prev_tail && data.prev_tail.sentences.length > 0 && (
            <p className="prev-tail ui-description post-detail__prev" id="prev-tail">지난 {data.prev_tail.display_no || data.prev_tail.chapter_no}장에서: {data.prev_tail.sentences.join(' ')}</p>
        )}

        <div className="diary-write__history-scroll post-detail__scroll">
            {sentences.length ? (
                <ul className="sents" aria-label="쓴 문장">
                    {sentences.map((s) => (
                        // 글 보기는 이야기를 읽는 화면이라 문장만 보여 준다 (2026-11-20).
                        // 고친 곳 · 처음 쓴 문장 · 고른 표현 표시는 빼 두었다 (교정 기록은 대시보드 · 글쓰기 화면에서 본다). 다시 넣으려면 s.corrections · s.original · s.expression_choice 를 쓴다
                        <li key={s.id} className="card">
                            <p className="text">{s.revised || s.original}</p>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="ui-body empty post-detail__empty">아직 쓴 문장이 없어요.</p>
            )}
        </div>
    </DetailBook>
}
