// 새 책 만들기 화면 (요구사항정의서 차트 - 화면ID 시트 - 03번 화면)
//   1단계: 일기 / 동화 고르기 (FR-002)
//   2단계: 책 이름 정하기 (FR-030, 기능+화면 시트의 '화면 생성 필요' 화면을 같은 파일에 둠)
// POST /api/books {kind, title} → 만들어진 책을 onCreated 로 넘긴다.

import { useState } from 'react'
import { api } from './api.js'
import diaryChoice from './assets/illustrations/diary-choice.png'
import fairyChoice from './assets/illustrations/fairy-choice.png'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import hangingRope from './assets/backgrounds/hanging-rope-hole.png'
import './CreateBookPage.css'

const TITLE_MAX = 20 // backend/books_repo.py 의 MAX_TITLE 과 같은 값
const KIND_LABEL = { diary: '일기', fairy: '동화' }

function Ropes() {
  return <>
    <img className="create-book__rope create-book__rope--left" src={hangingRope} alt="" draggable="false" />
    <img className="create-book__rope create-book__rope--right" src={hangingRope} alt="" draggable="false" />
  </>
}

export default function CreateBookPage({ onCreated, onCancel, onAuthError }) {
  const [kind, setKind] = useState(null) // null 이면 1단계
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const [inputError, setInputError] = useState(false)

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
      const book = await api('/api/books', { method: 'POST', body: { kind, title } })
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

  if (kind === null) {
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
            <button className="create-book__choice create-book__paper" type="button" key={category} onClick={() => setKind(category)}>
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

  return (
    <main className={`create-book create-book--${kind}`} aria-labelledby="create-book-heading">
      <header className="create-book__header">
        <button className="ui-button ui-button--secondary create-book__back" type="button" onClick={() => { setKind(null); setError(''); setInputError(false) }} disabled={sending} aria-label="종류 다시 고르기">
          <span className="create-book__back-icon" aria-hidden="true" />뒤로
        </button>
      </header>
      <form className="create-book__form create-book__paper" onSubmit={handleSubmit}>
        <Ropes />
        <div className="create-book__form-content">
          <p className="create-book__category">{KIND_LABEL[kind]}</p>
          <h1 className="ui-title create-book__heading" id="create-book-heading">{KIND_LABEL[kind]}책 이름을 지어 주세요.</h1>
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
