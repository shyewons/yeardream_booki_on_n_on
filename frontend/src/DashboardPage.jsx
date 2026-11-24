// 대시보드 메인 (요구사항정의서 FR-042, 시안 12A · 12D). 아이와 어른이 같은 화면을 본다.
// GET /api/dashboard → 이번 주 일기 작성 요일(FR-024) · 다시 살펴볼 맞춤법(FR-043) · 내가 골라 쓴 표현(FR-044)
//                      · 일기 주간 선물(FR-039, diary_reward) · 내 캐릭터가 입은 옷(character)
// POST /api/rewards/diary/claim → 주간 선물 받기 (자동으로 주지 않고 아이가 눌러서 받는다)
// 대시보드 안의 화면: 최근 고친 문장(FR-021), 캐릭터 옷장(FR-041).
// 대시보드 안의 화면 이동은 이 파일 안에서 한다 (App.jsx 는 대시보드 하나만 연결).

import { useEffect, useState } from 'react'
import { api } from './api.js'
import { resolveWardrobeImage } from './wardrobeImages.js'
import RecentFixesPage from './RecentFixesPage.jsx'
import WardrobePage from './WardrobePage.jsx'
import child from './assets/characters/child-cream-shirt.png'
import gift from './assets/icons/reward-gift.png'
import './DashboardPage.css'

const SLOT_LABEL = { top: '상의', bottom: '하의', hat: '모자', shoes: '신발', gloves: '장갑' }

export default function DashboardPage({ onBack, onAuthError }) {
    const [view, setView] = useState('main') // 'main' 대시보드 메인 / 'fixes' 최근 고친 문장 / 'wardrobe' 옷장
    const [data, setData] = useState(null) // { owner, week, spelling, expressions, diary_reward, character }
    const [error, setError] = useState('')
    const [reloadKey, setReloadKey] = useState(0)
    const [claiming, setClaiming] = useState(false)
    const [failedWeek, setFailedWeek] = useState(null)
    const [claimMsg, setClaimMsg] = useState('') // 선물 받기 결과 (받았어요 / 받지 못했어요)

    useEffect(() => {
        let ignore = false
        api('/api/dashboard')
            .then((res) => {
                if (!ignore) {
                    setData(res)
                    setError('')
                }
            })
            .catch((err) => {
                if (ignore) return
                if (err.status === 401) onAuthError()
                else setError(err.message)
            })
        return () => {
            ignore = true
        }
    }, [reloadKey, onAuthError])

    function retry() {
        setError('')
        setReloadKey((k) => k + 1)
    }

    // 주간 선물 받기. 응답의 diary_reward · character 로 화면을 바로 바꾼다 (대시보드를 다시 부르지 않는다)
    async function claim(weekStart) {
        if (claiming) return
        setFailedWeek(null)
        setClaiming(true)
        setClaimMsg('')
        try {
            const res = await api('/api/rewards/diary/claim', { method: 'POST', body: { week_start: weekStart } })
            setData((d) => ({ ...d, diary_reward: res.diary_reward, character: res.character }))
            setClaimMsg(`선물을 받았어요: ${res.clothes.name}. 옷장에서 확인해요.`) // 시안 12E
        } catch (err) {
            if (err.status === 401) onAuthError()
            else {
                setFailedWeek(weekStart)
                setClaimMsg(`선물을 받지 못했어요. ${err.message}`)
            } // 시안 12F
        } finally {
            setClaiming(false)
        }
    }

    if (view === 'fixes') {
        return <RecentFixesPage onBack={() => setView('main')} onAuthError={onAuthError} />
    }
    if (view === 'wardrobe') {
        // 옷장에서 옷을 바꿨을 수 있으니 돌아올 때 대시보드를 다시 불러온다
        // 다시 불러오는 동안 예전 캐릭터가 잠깐 보이지 않게 data 를 비우고, 지난 '선물을 받았어요' 문구도 지운다
        function backFromWardrobe() {
            setData(null)
            setFailedWeek(null)
            setClaimMsg('')
            setView('main')
            setReloadKey((k) => k + 1)
        }
        return <WardrobePage onBack={backFromWardrobe} onAuthError={onAuthError} />
    }

    const { week, spelling, expressions, diary_reward: reward, character } = data || {}
    const currentGift = reward?.this_week
    const shortDate = (date) => date?.slice(5).replace('-', '.') || ''

    return <main className="records" aria-labelledby="records-title">
        <header className="records__header">
            <button className="ui-button ui-button--secondary ui-button--small" type="button" onClick={onBack}>
                <span aria-hidden="true">←</span> 목장으로
            </button>
            <h1 className="records__title records__paper ui-title" id="records-title">나의 기록</h1>
        </header>

        <div className="records__panel records__paper">
            <section className="records__character records__card" aria-labelledby="records-character-title">
                <h2 id="records-character-title">내 캐릭터</h2>
                {/* 전신 에셋은 기본 모습이다. 카드용 의상 썸네일을 몸 위에 겹치지 않는다. */}
                <div className="records__portrait"><img src={child} alt="내 캐릭터 기본 모습" /></div>
                <div className="records__equipment">
                    {character ? <details>
                        <summary>지금 입은 옷</summary>
                        <ul>{Object.entries(SLOT_LABEL).map(([slot, label]) => (
                            <li key={slot}><span>{label}</span> {character[slot]?.name || '없음'}</li>
                        ))}</ul>
                    </details> : data && <p className="ui-muted">착용 정보를 불러오지 못했어요.</p>}
                </div>
                <button className="ui-button ui-button--secondary records__wardrobe" type="button" onClick={() => setView('wardrobe')}>옷장</button>
            </section>

            <div className="records__content">
                {error || !data ? <section className="records__state records__card" aria-busy={!error}>
                    {error ? <>
                        <h2 role="alert">기록을 불러오지 못했어요.</h2>
                        <p>잠시 후 다시 불러와 주세요.</p>
                        <details className="records__error-detail"><summary>오류 내용 보기</summary><p>{error}</p></details>
                        <button type="button" className="ui-button ui-button--primary" onClick={retry}>다시 불러오기</button>
                    </> : <p role="status">기록을 불러오고 있어요.</p>}
                </section> : <>
                    <section className="records__week records__card" aria-labelledby="records-week-title">
                        <div className="records__heading">
                            <h2 id="records-week-title">이번 주 일기</h2>
                            <p title={week.start + ' ~ ' + week.end}>{shortDate(week.start)}–{shortDate(week.end)} · {week.count}일 썼어요</p>
                        </div>
                        <ul className="records__days">{week.days.map((day) => (
                            <li key={day.date} aria-label={day.date + ' ' + day.weekday + '요일 ' + (day.written ? '일기를 썼어요' : '아직 기록이 없어요')}>
                                <span className="records__weekday" aria-hidden="true">{day.weekday}</span>
                                <span className={'records__day' + (day.written ? ' records__day--written' : '')} aria-hidden="true">{day.written && '✓'}</span>
                            </li>
                        ))}</ul>
                    </section>

                    <section className="records__gift records__card" aria-labelledby="records-gift-title" tabIndex="0">
                        <div className="records__heading">
                            <h2 id="records-gift-title">이번 주 선물</h2>
                            {reward && <p>{reward.progress.count} / {reward.progress.need}일</p>}
                        </div>
                        {!reward ? <p className="ui-muted">선물 정보를 불러오지 못했어요.</p> : <>
                            <div className="records__gift-row">
                                <div className="records__progress" role="progressbar" aria-label="주간 선물까지 쓴 날" aria-valuemin={0} aria-valuemax={reward.progress.need} aria-valuenow={Math.min(reward.progress.count, reward.progress.need)}>
                                    {Array.from({ length: reward.progress.need }, (_, index) => <span key={index} className={'records__dot' + (index < reward.progress.count ? ' records__dot--filled' : '')} />)}
                                </div>
                                {currentGift.clothes && <img className={'records__gift-image' + (currentGift.status === 'locked' ? ' records__gift-image--locked' : '')}
                                    src={resolveWardrobeImage(currentGift.clothes.image_url) || gift} alt="" onError={(event) => {
                                        if (event.currentTarget.src !== new URL(gift, window.location.href).href) event.currentTarget.src = gift
                                    }} />}
                                <div className="records__gift-status">
                                    {currentGift.status === 'claimable' && <button type="button" className="ui-button ui-button--primary ui-button--small" disabled={claiming} aria-busy={claiming} onClick={() => claim(currentGift.week_start)}>
                                        {claiming ? '받는 중…' : failedWeek === currentGift.week_start ? '다시 받기' : '선물 받기'}
                                    </button>}
                                    {currentGift.status === 'claimed' && <p className="records__badge">✓ 이번 주 선물을 받았어요</p>}
                                    {currentGift.status === 'locked' && <p className="records__badge">{Math.max(0, reward.progress.need - reward.progress.count)}일 더 쓰면 받을 수 있어요</p>}
                                    {currentGift.status === 'none' && <p>준비된 선물을 모두 받았어요.</p>}
                                    {failedWeek ? <p className="records__gift-caption records__gift-error" role="alert">선물을 받지 못했어요.</p>
                                        : <p className="records__gift-caption ui-muted">{currentGift.status === 'claimed' ? '옷장에서 입어 봐요' : '3문장 이상 쓴 일기 기준'}</p>}
                                </div>
                            </div>
                            {currentGift.clothes && <p className="records__gift-name">선물: {currentGift.clothes.name} ({currentGift.clothes.slot_label})</p>}
                            {claimMsg && <p className={'ui-notice records__claim-result' + (failedWeek ? ' ui-notice--error' : '')} role={failedWeek ? 'alert' : 'status'}>{claimMsg}</p>}
                            {reward.unclaimed.length > 0 && <div className="records__unclaimed">
                                <p>지난주 선물도 받을 수 있어요.</p>
                                <ul>{reward.unclaimed.map((item) => <li key={item.week_start}>
                                    <span>{item.week_start} 주 · {item.clothes.name}</span>
                                    <button type="button" className="ui-button ui-button--secondary ui-button--small" disabled={claiming} aria-busy={claiming} onClick={() => claim(item.week_start)}>
                                        {failedWeek === item.week_start ? '다시 받기' : '받기'}
                                    </button>
                                </li>)}</ul>
                            </div>}
                        </>}
                    </section>

                    <div className="records__learning">
                        <section className="records__card records__learning-card" aria-labelledby="records-spelling-title">
                            <h2 id="records-spelling-title">다시 살펴볼 맞춤법</h2>
                            <div className="records__learning-scroll" tabIndex="0" role="region" aria-label="다시 살펴볼 맞춤법 목록">
                                {spelling.items.length === 0 ? <p className="records__empty">아직 여러 글에서 반복해 고친 맞춤법이 없어요.</p> : <ul>
                                    {spelling.items.map((item) => <li key={item.before + '→' + item.after}>
                                        <p className="records__comparison"><span>{item.before}</span><span aria-hidden="true"> → </span><mark>{item.after}</mark></p>
                                        <p className="records__count ui-muted">글 {item.entry_count}개에서 고쳤어요</p>
                                        {item.explanation && <p>{item.explanation}</p>}
                                    </li>)}
                                </ul>}
                            </div>
                        </section>
                        <section className="records__card records__learning-card" aria-labelledby="records-expression-title">
                            <h2 id="records-expression-title">내가 골라 쓴 표현</h2>
                            <div className="records__learning-scroll" tabIndex="0" role="region" aria-label="내가 골라 쓴 표현 목록">
                                {expressions.items.length === 0 ? <p className="records__empty">아직 골라 쓴 표현이 없어요. 동화를 쓰면서 마음에 드는 표현을 골라 보세요.</p> : <ul>
                                    {expressions.items.map((item) => <li key={item.sentence_id}>
                                        <p className="records__book ui-muted">{item.book_title}</p>
                                        <p><span className="records__label">처음 표현</span> {item.original}</p>
                                        <p><span className="records__label">고른 표현</span> <mark>{item.picked}</mark></p>
                                    </li>)}
                                </ul>}
                            </div>
                        </section>
                    </div>
                </>}
                <button className="ui-button ui-button--secondary records__recent" type="button" onClick={() => setView('fixes')}>
                    최근 고친 문장 보기 <span aria-hidden="true">→</span>
                </button>
            </div>
        </div>
    </main>
}
