// 새 책 만들기 화면 (요구사항정의서 차트 - 화면ID 시트 - 03번 화면)
//   1단계: 일기 / 동화 고르기 (FR-002)
//   (동화만) 주제 고르기: 주제 3개(이름 + 쓰기 안내. 시작 상황 opening 은 글쓰기 첫 장에서 보여 준다) · 다른 주제 보기 · 내가 정할래요 (디자인 시안 03D)
//   2단계: 책 이름 정하기 (FR-030, 기능+화면 시트의 '화면 생성 필요' 화면을 같은 파일에 둠)
//          동화는 고른 주제 이름을 책 이름 칸에 미리 적어 둔다 (아이가 고쳐 쓸 수 있다)
// GET /api/topics?others=2 → 주제 3개 { items: [{id, title, prompt, opening}] }
// POST /api/books {kind, title, fairy_topic_id} → 만들어진 책을 onCreated 로 넘긴다.
//   fairy_topic_id 가 null 이면 자유 주제 (서버가 '자유 주제' 줄 번호로 적는다. 일기는 늘 null)
// 뒤로: 책 이름 → (동화) 주제 고르기 → 종류 고르기.

import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import diaryChoice from './assets/illustrations/diary-choice.png'
import fairyChoice from './assets/illustrations/fairy-choice.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import hangingRope from './assets/backgrounds/hanging-rope-hole.png'
import './CreateBookPage.css'

const TITLE_MAX = 20 // backend/books_repo.py 의 MAX_TITLE 과 같은 값
const KIND_LABEL = { diary: '일기', fairy: '동화' }
const TOPIC_COUNT = 3 // 한 번에 보여 주는 주제 수 (추천 1 + 다른 주제 2)

function Ropes() {
    return <>
        <img className="create-book__rope create-book__rope--left" src={hangingRope} alt="" draggable="false" />
        <img className="create-book__rope create-book__rope--right" src={hangingRope} alt="" draggable="false" />
    </>
}

export default function CreateBookPage({ onCreated, onCancel, onAuthError }) {
    const [kind, setKind] = useState(null) // null 이면 1단계
    const [step, setStep] = useState('kind') // kind → (동화) topic → name
    const [topics, setTopics] = useState(null) // 지금 보여 주는 주제 [{id, title, prompt}]
    const [topicsLoading, setTopicsLoading] = useState(false)
    const topicRequest = useRef(0)
    const [shown, setShown] = useState([]) // 지금까지 보여 준 주제 이름 (다른 주제 보기에서 빼고 고른다)
    const [topicError, setTopicError] = useState('')
    const [topic, setTopic] = useState(null) // 고른 주제 {id, title, prompt}. null 이면 자유 주제
    const [title, setTitle] = useState('')
    const [error, setError] = useState('')
    const [sending, setSending] = useState(false)
    const [inputError, setInputError] = useState(false)

    useEffect(() => () => { topicRequest.current += 1 }, [])

    // 주제 3개를 받아 온다. more 면 이미 본 주제는 되도록 빼고 고른다
    async function loadTopics(more) {
        const seen = more ? shown : []
        const request = ++topicRequest.current
        setTopicsLoading(true)
        setTopicError('')
        try {
            const r = await api(`/api/topics?others=${TOPIC_COUNT - 1}&exclude=${encodeURIComponent(seen.join(','))}`)
            if (request !== topicRequest.current) return
            const items = (r.items || []).slice(0, TOPIC_COUNT)
            setTopics(items)
            setShown(seen.concat(items.map((t) => t.title)))
        } catch (err) {
            if (request !== topicRequest.current) return
            if (err.status === 401) {
                onAuthError()
                return
            }
            setTopicError('주제를 불러오지 못했어요. 다시 보거나, 내가 정할래요를 눌러 주세요.')
        } finally {
            if (request === topicRequest.current) setTopicsLoading(false)
        }
    }

    function pickKind(k) {
        setKind(k)
        setError('')
        setInputError(false)
        if (k === 'fairy') {
            setStep('topic')
            if (topics === null || topics.length === 0) loadTopics(false)
        } else {
            setTopic(null)
            setStep('name')
        }
    }

    // 주제를 고르면 책 이름 단계로. 이름 칸이 비어 있거나 앞에서 미리 적은 주제 이름 그대로면 새 주제 이름으로 바꿔 적는다
    function pickTopic(t) {
        topicRequest.current += 1
        setTopicsLoading(false)
        const prefilled = !title.trim() || (topic && title === topic.title)
        setTopic(t)
        if (t && prefilled) setTitle(t.title)
        if (!t && prefilled) setTitle('')
        setError('')
        setInputError(false)
        setStep('name')
    }

    function goBack() {
        topicRequest.current += 1
        setTopicsLoading(false)
        setError('')
        setInputError(false)
        if (step === 'name' && kind === 'fairy') {
            setStep('topic')
            if (topics === null || topics.length === 0) loadTopics(false)
            return
        }
        setKind(null)
        setStep('kind')
    }

    async function handleSubmit(e) {
        e.preventDefault()
        if (sending) return
        if (!title.trim()) {
            setInputError(true)
            setError('책 이름을 적어 주세요.')
            return
        }
        setSending(true)
        setError('')
        setInputError(false)
        try {
            const fairyTopicId = kind === 'fairy' && topic ? topic.id : null
            const book = await api('/api/books', { method: 'POST', body: { kind, title, fairy_topic_id: fairyTopicId } })
            onCreated(book)
        } catch (err) {
            if (err.status === 401) {
                onAuthError()
                return
            }
            setError(err.message) // 고른 종류와 입력한 이름은 그대로 둔다
            setInputError([400, 409, 422].includes(err.status))
            setSending(false)
        }
    }

    if (kind === null || step === 'kind') {
        return (
            <main className="create-book create-book--choice" aria-labelledby="create-book-heading">
                <header className="create-book__header">
                    <button className="ui-button ui-button--secondary create-book__back" type="button" onClick={onCancel}>
                        <span className="create-book__back-icon" aria-hidden="true" />목장으로
                    </button>
                </header>
                <h1 className="ui-title create-book__heading" id="create-book-heading">어떤 이야기를 들려줄까요?</h1>
                <div className="create-book__choices">
                    {['diary', 'fairy'].map((category) => (
                        <button className="create-book__choice create-book__paper" type="button" key={category} onClick={() => pickKind(category)}>
                            <Ropes />
                            <span className="ui-title create-book__choice-title">{KIND_LABEL[category]}</span>
                            <span className="create-book__illustration">
                                <img src={category === 'diary' ? diaryChoice : fairyChoice} alt="" draggable="false" />
                            </span>
                            <span className="ui-body">{category === 'diary' ? '오늘 있었던 일을 써요.' : '상상한 이야기를 써요.'}</span>
                        </button>
                    ))}
                </div>
                <p className="ui-description create-book__hint">쓰고 싶은 이야기를 눌러 주세요.</p>
            </main>
        )
    }

    if (step === 'topic') {
        return (
            <main className="create-book create-book--fairy create-book--topics" id="topic-step" aria-labelledby="create-book-heading">
                <header className="create-book__header">
                    <button className="ui-button ui-button--secondary create-book__back" type="button" onClick={goBack}>
                        <span className="create-book__back-icon" aria-hidden="true" />뒤로
                    </button>
                </header>
                <section className="create-book__form create-book__paper create-book__topic-panel">
                    <Ropes />
                    <div className="create-book__form-content">
                        <p className="create-book__category">동화</p>
                        <h1 className="ui-title create-book__heading" id="create-book-heading">어떤 주제로 써 볼까요?</h1>
                        <div className="create-book__topic-content" aria-busy={topicsLoading}>
                            {!!topics?.length && (
                                <ul className="create-book__topic-list">
                                    {topics.map((t) => (
                                        <li key={t.title}>
                                            <button className="create-book__topic-card" type="button" onClick={() => pickTopic(t)} disabled={topicsLoading}>
                                                <span className="create-book__topic-copy">
                                                    <strong className="create-book__topic-title">{t.title}</strong>
                                                    {t.prompt && <span className="create-book__topic-prompt">{t.prompt}</span>}
                                                </span>
                                                <span className="create-book__topic-chevron" aria-hidden="true" />
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {topicsLoading && <p className={`ui-description ui-muted create-book__topic-loading${topics?.length ? '' : ' create-book__topic-loading--initial'}`} role="status">주제를 불러오고 있어요</p>}
                            {!topicsLoading && topicError && <p className="ui-notice ui-notice--error create-book__topic-error" role="alert">{topicError}</p>}
                            {!topicsLoading && !topicError && topics?.length === 0 && <p className="ui-description ui-muted create-book__topic-empty">지금 보여줄 주제가 없어요. 직접 정해 볼까요?</p>}
                        </div>
                        <div className="ui-actions create-book__topic-actions">
                            <button className="ui-button ui-button--secondary" type="button" id="topic-more" onClick={() => loadTopics(true)} disabled={topicsLoading}>
                                <span className="create-book__refresh-icon" aria-hidden="true" />{topicError ? '다시 불러오기' : '다른 주제 보기'}
                            </button>
                            <button className="ui-button ui-button--secondary" type="button" id="topic-free" onClick={() => pickTopic(null)}>내가 정할래요</button>
                        </div>
                    </div>
                    <div className="create-book__face" aria-hidden="true">
                        <img src={alpaca} alt="" draggable="false" />
                    </div>
                </section>
            </main>
        )
    }

    return (
        <main className={`create-book create-book--${kind}`} aria-labelledby="create-book-heading">
            <header className="create-book__header">
                <button className="ui-button ui-button--secondary create-book__back" type="button" onClick={goBack} disabled={sending} aria-label={kind === 'fairy' ? '주제 다시 고르기' : '종류 다시 고르기'}>
                    <span className="create-book__back-icon" aria-hidden="true" />뒤로
                </button>
            </header>
            <form className="create-book__form create-book__paper" onSubmit={handleSubmit}>
                <Ropes />
                <div className="create-book__form-content">
                    <p className="create-book__category">{KIND_LABEL[kind]}</p>
                    <h1 className="ui-title create-book__heading" id="create-book-heading">{KIND_LABEL[kind]}책 이름을 지어 주세요.</h1>
                    {kind === 'fairy' && <p className="ui-description create-book__selected-topic">{topic ? `고른 주제: ${topic.title}` : '내가 정한 주제로 쓸 거예요.'}</p>}
                    <div className="create-book__field">
                        <label className="ui-field-label" htmlFor="book-title">책 이름</label>
                        <input
                            className="ui-input create-book__input"
                            id="book-title"
                            name="title"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            maxLength={TITLE_MAX}
                            placeholder={`책 이름 (${TITLE_MAX}자까지)`}
                            aria-invalid={inputError || undefined}
                            aria-describedby={error ? 'book-title-error' : undefined}
                            readOnly={sending}
                            autoFocus
                        />
                        <div className="create-book__feedback">
                            {error && <p className={inputError ? 'ui-field-message' : 'ui-notice ui-notice--error'} id="book-title-error" role="alert">{error}</p>}
                        </div>
                    </div>
                    <button className="ui-button ui-button--primary ui-button--large create-book__submit" type="submit" disabled={sending} aria-busy={sending}>
                        {sending ? '만드는 중...' : '책 만들기'}
                    </button>
                </div>
            </form>
            <div className="create-book__face" aria-hidden="true">
                <img src={kind === 'diary' ? sheep : alpaca} alt="" draggable="false" />
            </div>
        </main>
    )
}
