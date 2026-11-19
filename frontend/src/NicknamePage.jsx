// 신규유저 첫화면 : 별명 설정 (요구사항정의서 차트 - 화면ID 시트 - 01번 화면, FR-025)
// 별명을 입력하고 '시작하기' → POST /api/users → 받은 토큰을 보관 → 02번 목장으로
// 별명 규칙 검사(길이·글자·비속어 등)는 서버가 한다 (backend/users_repo.py). 여기서는 빈 값만 먼저 막는다.

import { useState } from 'react'
import { api, setToken } from './api.js'
import hangingRope from './assets/backgrounds/hanging-rope-hole.png'
import './NicknamePage.css'

const NICKNAME_MAX = 10 // backend/users_repo.py 의 NICKNAME_MAX 와 같은 값

export default function NicknamePage({ onDone }) {
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState('')
  const [inputError, setInputError] = useState(false)
  const [sending, setSending] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (sending) return // 두 번 눌러도 한 번만 보낸다
    if (!nickname.trim()) {
      setInputError(true)
      setError('별명을 적어 주세요.')
      return
    }
    setSending(true)
    setError('')
    setInputError(false)
    try {
      const user = await api('/api/users', { method: 'POST', body: { nickname } })
      setToken(user.token)
      onDone(user.nickname)
    } catch (err) {
      setError(err.message) // 입력한 별명은 그대로 둔다
      // 연결 실패는 별명이 틀렸다는 표시와 구분한다.
      setInputError([400, 409, 422].includes(err.status))
      setSending(false)
    }
  }

  return (
    <main className="nickname-screen" aria-labelledby="nickname-heading">
      <form className="nickname-screen__sign" onSubmit={handleSubmit}>
        <img className="nickname-screen__rope nickname-screen__rope--left" src={hangingRope} alt="" aria-hidden="true" draggable="false" />
        <img className="nickname-screen__rope nickname-screen__rope--right" src={hangingRope} alt="" aria-hidden="true" draggable="false" />
        <div className="nickname-screen__content">
          <h1 className="ui-title nickname-screen__heading" id="nickname-heading">
            <label htmlFor="nickname">어떤 별명으로 불러줄까요?</label>
          </h1>
          <div className="nickname-screen__name">
            <input
              className="ui-input nickname-screen__input"
              id="nickname"
              name="nickname"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              maxLength={NICKNAME_MAX}
              placeholder={`별명 (${NICKNAME_MAX}자까지)`}
              aria-invalid={inputError || undefined}
              aria-describedby={error ? 'nickname-error' : undefined}
              autoFocus
            />
            <span className="ui-title nickname-screen__suffix" aria-hidden="true">의 목장</span>
          </div>
          <div className="nickname-screen__feedback">
            {error && (
              <p className={inputError ? 'ui-field-message' : 'ui-notice ui-notice--error'} id="nickname-error" role="alert">
                {error}
              </p>
            )}
          </div>
          <button className="ui-button ui-button--primary ui-button--large nickname-screen__submit" type="submit" disabled={sending} aria-busy={sending}>
            {sending ? '만드는 중...' : '시작하기'}
          </button>
        </div>
      </form>
    </main>
  )
}
