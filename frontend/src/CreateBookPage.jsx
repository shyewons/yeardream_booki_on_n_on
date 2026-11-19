// 새 책 만들기 화면 (요구사항정의서 차트 - 화면ID 시트 - 03번 화면)
//   1단계: 일기 / 동화 고르기 (FR-002)
//   (동화만) 주제 고르기: 주제 3개(이름 + 이야기 시작 문장) · 다른 주제 보기 · 내가 정할래요 (디자인 시안 03D)
//   2단계: 책 이름 정하기 (FR-030, 기능+화면 시트의 '화면 생성 필요' 화면을 같은 파일에 둠)
//          동화는 고른 주제 이름을 책 이름 칸에 미리 적어 둔다 (아이가 고쳐 쓸 수 있다)
// GET /api/topics?others=2 → 주제 3개 { items: [{id, title, prompt}] }
// POST /api/books {kind, title, fairy_topic_id} → 만들어진 책을 onCreated 로 넘긴다.
//   fairy_topic_id 가 null 이면 자유 주제 (일기는 늘 null)
// 뒤로: 책 이름 → (동화) 주제 고르기 → 종류 고르기. 모양(CSS)은 아직 입히지 않았다.

import { useState } from 'react'
import { api } from './api.js'

const TITLE_MAX = 20 // backend/books_repo.py 의 MAX_TITLE 과 같은 값
const KIND_LABEL = { diary: '일기', fairy: '동화' }
const TOPIC_COUNT = 3 // 한 번에 보여 주는 주제 수 (추천 1 + 다른 주제 2)

export default function CreateBookPage({ onCreated, onCancel, onAuthError }) {
  const [kind, setKind] = useState(null) // null 이면 1단계
  const [step, setStep] = useState('kind') // kind → (동화) topic → name
  const [topics, setTopics] = useState(null) // 지금 보여 주는 주제 [{id, title, prompt}] (null: 불러오는 중)
  const [shown, setShown] = useState([]) // 지금까지 보여 준 주제 이름 (다른 주제 보기에서 빼고 고른다)
  const [topicError, setTopicError] = useState('')
  const [topic, setTopic] = useState(null) // 고른 주제 {id, title, prompt}. null 이면 자유 주제
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  // 주제 3개를 받아 온다. more 면 이미 본 주제는 되도록 빼고 고른다
  async function loadTopics(more) {
    const seen = more ? shown : []
    setTopics(null)
    setTopicError('')
    try {
      const r = await api(`/api/topics?others=${TOPIC_COUNT - 1}&exclude=${encodeURIComponent(seen.join(','))}`)
      const items = (r.items || []).slice(0, TOPIC_COUNT)
      setTopics(items)
      setShown(seen.concat(items.map((t) => t.title)))
    } catch (err) {
      if (err.status === 401) {
        onAuthError()
        return
      }
      setTopics([])
      setTopicError('주제를 불러오지 못했어요. 다시 보거나, 내가 정할래요를 눌러 주세요.')
    }
  }

  function pickKind(k) {
    setKind(k)
    setError('')
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
    const prefilled = !title.trim() || (topic && title === topic.title)
    setTopic(t)
    if (t && prefilled) setTitle(t.title)
    if (!t && prefilled) setTitle('')
    setError('')
    setStep('name')
  }

  function goBack() {
    setError('')
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
      setError('책 이름을 적어 주세요.')
      return
    }
    setSending(true)
    setError('')
    try {
      const fairyTopicId = kind === 'fairy' && topic ? topic.id : null
      const book = await api('/api/books', { method: 'POST', body: { kind, title, fairy_topic_id: fairyTopicId } })
      onCreated(book)
    } catch (err) {
      if (err.status === 401) {
        onAuthError()
        return
      }
      setError(err.message) // 고른 종류 · 주제와 입력한 이름은 그대로 둔다
      setSending(false)
    }
  }

  if (kind === null || step === 'kind') {
    return (
      <div>
        <h1>새 책 만들기</h1>
        <p>어떤 책을 만들까요?</p>
        <button type="button" onClick={() => pickKind('diary')}>일기</button>
        <button type="button" onClick={() => pickKind('fairy')}>동화</button>
        <div>
          <button type="button" onClick={onCancel}>책장으로</button>
        </div>
      </div>
    )
  }

  if (step === 'topic') {
    return (
      <div id="topic-step">
        <button type="button" className="back" onClick={goBack}>뒤로</button>
        <p className="kind-pill">동화</p>
        <h1>어떤 주제로 써 볼까요?</h1>
        {topics === null && <p>주제를 고르고 있어요...</p>}
        {topics !== null && (
          <ul className="topic-list">
            {topics.map((t) => (
              <li key={t.title}>
                <button type="button" className="topic-card" onClick={() => pickTopic(t)}>
                  <strong className="topic-title">{t.title}</strong>
                  {t.prompt && <><br /><span className="topic-prompt">{t.prompt}</span></>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {topicError && <p role="alert">{topicError}</p>}
        <div className="row">
          <button type="button" id="topic-more" onClick={() => loadTopics(true)} disabled={topics === null}>
            다른 주제 보기
          </button>{' '}
          <button type="button" id="topic-free" onClick={() => pickTopic(null)}>
            내가 정할래요
          </button>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      <button type="button" className="back" onClick={goBack} disabled={sending}>뒤로</button>
      <p className="kind-pill">{KIND_LABEL[kind]}</p>
      <h1>{KIND_LABEL[kind]}책 이름을 지어 주세요.</h1>
      {kind === 'fairy' && (
        <p id="picked-topic">{topic ? `고른 주제: ${topic.title}` : '주제는 내가 정해요'}</p>
      )}
      <label>
        책 이름
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={TITLE_MAX}
          placeholder={`책 이름 (${TITLE_MAX}자까지)`}
          autoFocus
        />
      </label>
      <button type="submit" disabled={sending}>
        {sending ? '만드는 중...' : '책 만들기'}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
