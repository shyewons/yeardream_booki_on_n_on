// 신규유저 첫화면 : 별명 설정 (요구사항정의서 차트 - 화면ID 시트 - 01번 화면, FR-025)
// 별명을 입력하고 '시작하기' → POST /api/users → 받은 토큰을 보관 → 02번 목장으로
// 별명 규칙 검사(길이·글자·비속어 등)는 서버가 한다 (backend/users_repo.py). 여기서는 빈 값만 먼저 막는다.

import { useState } from 'react'
import { api, setToken } from './api.js'

const NICKNAME_MAX = 10 // backend/users_repo.py 의 NICKNAME_MAX 와 같은 값

export default function NicknamePage({ onDone }) {
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (sending) return // 두 번 눌러도 한 번만 보낸다
    if (!nickname.trim()) {
      setError('별명을 적어 주세요.')
      return
    }
    setSending(true)
    setError('')
    try {
      const user = await api('/api/users', { method: 'POST', body: { nickname } })
      setToken(user.token)
      onDone(user.nickname)
    } catch (err) {
      setError(err.message) // 입력한 별명은 그대로 둔다
      setSending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>별명 설정</h1>
      <p>목장에서 불릴 별명을 지어 주세요.</p>
      <input
        value={nickname}
        onChange={(e) => setNickname(e.target.value)}
        maxLength={NICKNAME_MAX}
        placeholder={`별명 (${NICKNAME_MAX}자까지)`}
        autoFocus
      />
      <button type="submit" disabled={sending}>
        {sending ? '만드는 중...' : '시작하기'}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
