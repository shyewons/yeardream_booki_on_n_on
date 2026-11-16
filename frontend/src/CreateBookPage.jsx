// 새 책 만들기 화면 (요구사항정의서 차트 - 화면ID 시트 - 03번 화면)
//   1단계: 일기 / 동화 고르기 (FR-002)
//   2단계: 책 이름 정하기 (FR-030, 기능+화면 시트의 '화면 생성 필요' 화면을 같은 파일에 둠)
// POST /api/books {kind, title} → 만들어진 책을 onCreated 로 넘긴다.

import { useState } from 'react'
import { api } from './api.js'

const TITLE_MAX = 20 // backend/books_repo.py 의 MAX_TITLE 과 같은 값
const KIND_LABEL = { diary: '일기', fairy: '동화' }

export default function CreateBookPage({ onCreated, onCancel, onAuthError }) {
  const [kind, setKind] = useState(null) // null 이면 1단계
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

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
      const book = await api('/api/books', { method: 'POST', body: { kind, title } })
      onCreated(book)
    } catch (err) {
      if (err.status === 401) {
        onAuthError()
        return
      }
      setError(err.message) // 고른 종류와 입력한 이름은 그대로 둔다
      setSending(false)
    }
  }

  if (kind === null) {
    return (
      <div>
        <h1>새 책 만들기</h1>
        <p>어떤 책을 만들까요?</p>
        <button type="button" onClick={() => setKind('diary')}>일기</button>
        <button type="button" onClick={() => setKind('fairy')}>동화</button>
        <div>
          <button type="button" onClick={onCancel}>책장으로</button>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>{KIND_LABEL[kind]}책 이름 정하기</h1>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={TITLE_MAX}
        placeholder={`책 이름 (${TITLE_MAX}자까지)`}
        autoFocus
      />
      <button type="submit" disabled={sending}>
        {sending ? '만드는 중...' : '책 만들기'}
      </button>
      <button type="button" onClick={() => { setKind(null); setError('') }} disabled={sending}>
        종류 다시 고르기
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
