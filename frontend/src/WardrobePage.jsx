// 13A~13D 옷장. 조회·착용 API는 그대로 사용하고 공통 버튼과 목장 디자인을 적용한다.
import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { useLoad } from './useLoad.js'
import { resolveWardrobeImage } from './wardrobeImages.js'
import child from './assets/characters/child-cream-shirt.png'
import blueTop from './assets/icons/wardrobe-top-blue.png'
import greenTop from './assets/icons/wardrobe-top-green.png'
import yellowTop from './assets/icons/wardrobe-top-yellow.png'
import './WardrobePage.css'

const STATUS_LABEL = { wearing: '입고 있어요', owned: '가지고 있어요', locked: '아직 없어요' }
const SLOT_LABEL = { top: '상의', bottom: '하의', hat: '모자', shoes: '신발', gloves: '장갑' }
// 서버가 로컬 에셋 경로를 지정한 경우에만 번들 URL로 연결한다. 의상 ID나 색을 임의로 매핑하지 않는다.
const THUMBNAILS = { 'wardrobe-top-blue.png': blueTop, 'wardrobe-top-green.png': greenTop, 'wardrobe-top-yellow.png': yellowTop }
const SLOT_PATH = {
    top: 'M22 12 10 20 16 33 24 29V54H48V29L56 33 62 20 50 12 43 16H29Z',
    bottom: 'M21 14H51L55 55H39L36 33 33 55H17Z M21 22H51',
    hat: 'M12 43H60V49H12Z M22 42V27C22 10 50 10 50 27V42 M23 34H49',
    shoes: 'M15 19H32V35L53 41Q61 43 60 52H15Z M16 46H57 M31 34 38 31 M37 38 44 35',
    gloves: 'M25 38V17Q25 11 30 17V30 12Q34 7 38 13V30 17Q42 11 45 18V32 23Q50 17 52 25V43Q52 57 37 57 26 57 22 47L14 36Q13 30 19 32Z',
}

function SlotIcon({ slot }) {
    return <svg className="closet__slot-icon" viewBox="0 0 72 72" aria-hidden="true">
        <path d={SLOT_PATH[slot] || SLOT_PATH.top} fill="currentColor" fillOpacity=".18" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
}

function ClothesImage({ item, slot }) {
    const [failedUrl, setFailedUrl] = useState(null)
    const url = item.image_url
    const local = url && !/^https?:/i.test(url) ? THUMBNAILS[url.split('/').at(-1)] : null
    const src = local || resolveWardrobeImage(url)
    return <div className="closet__image">
        {src && failedUrl !== src ? <img src={src} alt="" onError={() => setFailedUrl(src)} /> : <SlotIcon slot={slot} />}
    </div>
}

function LockIcon() {
    return <svg viewBox="0 0 24 28" aria-hidden="true"><path d="M6 12V8a6 6 0 0 1 12 0v4" fill="none" stroke="currentColor" strokeWidth="3" /><rect x="2" y="11" width="20" height="16" rx="4" fill="currentColor" /><path d="M12 17v5" stroke="#fff9e8" strokeWidth="3" strokeLinecap="round" /></svg>
}

export default function WardrobePage({ onBack, onAuthError }) {
    const { data, error, retry } = useLoad('/api/wardrobe', onAuthError)
    const [slot, setSlot] = useState('top')
    const [worn, setWorn] = useState(null)
    const [saving, setSaving] = useState(false)
    const [saveError, setSaveError] = useState(null)
    const [saveNotice, setSaveNotice] = useState('')
    const errorRef = useRef(null)
    const requestPending = useRef(false)

    useEffect(() => {
        if (saveError) errorRef.current?.focus()
    }, [saveError])

    const equipped = worn ?? data?.equipped ?? {}
    const slots = data?.slots ?? Object.entries(SLOT_LABEL).map(([key, label]) => ({ slot: key, label, items: [] }))
    const current = slots.find((item) => item.slot === slot)
    const items = current?.items ?? []
    const ownedCount = items.filter((item) => item.status !== 'locked').length

    function statusOf(item) {
        if (item.status === 'locked') return 'locked'
        return equipped[slot] === item.id ? 'wearing' : 'owned'
    }

    function selectSlot(nextSlot) {
        if (saving || nextSlot === slot) return
        setSlot(nextSlot)
        setSaveError(null)
        setSaveNotice('')
    }

    async function wear(clothesId, targetSlot = slot) {
        if (requestPending.current) return
        requestPending.current = true
        setSaving(true)
        setSaveError(null)
        setSaveNotice('')
        try {
            const res = await api('/api/wardrobe/equip', { method: 'PUT', body: { slot: targetSlot, clothes_id: clothesId } })
            const next = {}
            for (const [key, value] of Object.entries(res.character)) next[key] = value ? value.id : null
            setWorn(next)
            setSaveNotice(clothesId === null ? '옷을 벗었어요.' : '옷을 바꿨어요.')
        } catch (err) {
            if (err.status === 401) onAuthError()
            else setSaveError({ message: err.message, slot: targetSlot, clothesId })
        } finally {
            requestPending.current = false
            setSaving(false)
        }
    }

    return <main className="wardrobe closet" aria-labelledby="closet-title">
        <header className="closet__header">
            <button type="button" className="ui-button ui-button--secondary ui-button--small" disabled={saving} onClick={onBack}>
                <span aria-hidden="true">←</span> 나의 기록
            </button>
        </header>
        <div className="closet__panel">
            <h1 className="ui-title" id="closet-title">옷장</h1>
            <div className="closet__columns">
                <section className="closet__character closet__surface" aria-labelledby="closet-character-title">
                    <h2 id="closet-character-title">내 캐릭터</h2>
                    {/* 전신은 기본 모습. 실제 착용 상태는 서버 응답을 따르고, 썸네일을 착용용 레이어로 사용하지 않는다. */}
                    <div className="closet__portrait"><img src={child} alt="내 캐릭터 기본 모습" /></div>
                    <div className="closet__equipped">
                        {data && !error && <details>
                            <summary>지금 입은 옷</summary>
                            <ul>{slots.map((part) => {
                                const item = part.items.find((clothes) => clothes.id === equipped[part.slot])
                                return <li key={part.slot}><span>{part.label}</span> {item?.name || '없음'}</li>
                            })}</ul>
                        </details>}
                    </div>
                </section>

                <section className="closet__inventory closet__surface" aria-label="의상 고르기">
                    <nav className="wardrobe-tabs closet__tabs" aria-label="의상 부위">
                        {slots.map((part) => <button key={part.slot} type="button"
                            className={'ui-button ui-button--small' + (slot === part.slot ? ' ui-button--primary is-selected' : ' ui-button--secondary')}
                            aria-pressed={slot === part.slot} aria-controls="closet-items" disabled={saving || !data || !!error} onClick={() => selectSlot(part.slot)}>
                            {part.label}
                        </button>)}
                    </nav>

                    {error || !data ? <div className="closet__state" id="closet-items" aria-busy={!error}>
                        {error ? <>
                            <h2 role="alert">옷을 불러오지 못했어요.</h2>
                            <p>잠시 후 다시 불러와 주세요.</p>
                            <details><summary>오류 내용 보기</summary><p>{error.message}</p></details>
                            <button type="button" className="ui-button ui-button--primary" onClick={retry}>다시 불러오기</button>
                        </> : <p role="status">옷을 불러오고 있어요.</p>}
                    </div> : <>
                        <div className="closet__intro">
                            <h2>입고 싶은 옷을 골라요</h2>
                            <p role="status" className="closet__notice">{saving ? '옷을 바꾸고 있어요…' : saveNotice}</p>
                        </div>
                        <div className="closet__scroll" id="closet-items" tabIndex="0" role="region" aria-label={current?.label + ' 의상 목록'}>
                            {ownedCount === 0 && <p className="closet__empty">아직 받은 {current?.label || '옷'}{slot === 'shoes' || slot === 'gloves' ? '이' : '가'} 없어요.<br />글을 쓰고 선물을 받아 모아 봐요.</p>}
                            <ul className="clothes-list closet__cards">
                                {items.map((item) => {
                                    const status = statusOf(item)
                                    return <li key={item.id} className={'clothes-card closet__card is-' + status} data-clothes-id={item.id}>
                                        <div className="closet__tile">
                                            <div className="closet__art">
                                                <ClothesImage item={item} slot={slot} />
                                                {status === 'wearing' && <span className="closet__check" aria-hidden="true">✓</span>}
                                                {status === 'locked' && <span className="closet__lock"><LockIcon /></span>}
                                            </div>
                                            <h3>{item.name}</h3>
                                            <p className="closet__badge">{STATUS_LABEL[status]}</p>
                                            {status !== 'locked' && <button type="button" className={'ui-button ui-button--small ' + (status === 'wearing' ? 'ui-button--secondary' : 'ui-button--primary')}
                                                disabled={saving} aria-busy={saving} aria-label={item.name + (status === 'wearing' ? ' 벗기' : ' 입기')} onClick={() => wear(status === 'wearing' ? null : item.id)}>
                                                {status === 'wearing' ? '벗기' : '입기'}
                                            </button>}
                                        </div>
                                        {status === 'locked' && (item.condition || item.progress) && <div className="clothes-condition closet__condition">
                                            {item.condition && <p>{item.condition}</p>}
                                            {item.progress && <p className="closet__progress">{item.progress}</p>}
                                        </div>}
                                    </li>
                                })}
                            </ul>
                        </div>
                        {saveError && <div className="closet__save-error ui-notice ui-notice--error" ref={errorRef} tabIndex="-1">
                            <div role="alert"><p>옷을 바꾸지 못했어요. 입고 있던 옷은 그대로예요.</p><p>{saveError.message}</p></div>
                            <button type="button" className="ui-button ui-button--primary ui-button--small" disabled={saving} onClick={() => wear(saveError.clothesId, saveError.slot)}>
                                {saveError.clothesId === null ? '다시 벗기' : '다시 입기'}
                            </button>
                        </div>}
                    </>}
                </section>
            </div>
        </div>
    </main>
}
