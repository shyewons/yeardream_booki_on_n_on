// 캐릭터 옷장 (요구사항정의서 FR-041, 시안 13A). 대시보드 안에서 들어오는 화면.
// GET /api/wardrobe → 부위(상의·하의·모자·신발·장갑)별 옷과 상태 (입고 있어요 / 가지고 있어요 / 아직 없어요)
// PUT /api/wardrobe/equip {slot, clothes_id} → 고른 부위만 바꾸고 다른 부위는 그대로 둔다. 벗기기는 clothes_id: null
// 스타일은 넣지 않았다. 상태는 글자와 버튼 막기(disabled)로 구분하고, 디자인용 className 만 붙였다.

import { useState } from 'react'
import { api } from './api.js'
import { useLoad } from './useLoad.js'

const STATUS_LABEL = { wearing: '입고 있어요', owned: '가지고 있어요', locked: '아직 없어요' }

export default function WardrobePage({ onBack, onAuthError }) {
  const { data, error, retry } = useLoad('/api/wardrobe', onAuthError)
  const [slot, setSlot] = useState('top') // 지금 보고 있는 부위 탭
  const [worn, setWorn] = useState(null) // 입히기 · 벗기기 뒤의 입은 옷 {부위: 옷 번호} (처음에는 서버 값)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  // 조회 실패는 '옷 없음'과 구분해서 보여 준다 (FR-033, 시안 13C)
  if (error) {
    return (
      <div className="wardrobe">
        <p role="alert">옷장을 불러오지 못했어요. {error.message}</p>
        <button type="button" onClick={retry}>다시 불러오기</button>
        <button type="button" onClick={onBack}>나의 기록으로</button>
      </div>
    )
  }
  if (!data) return <p>불러오는 중...</p>

  const equipped = worn ?? data.equipped
  const current = data.slots.find((s) => s.slot === slot)
  const ownedCount = data.slots.reduce((n, s) => n + s.items.filter((i) => i.status !== 'locked').length, 0)

  // 서버 상태(owned / locked)에 지금 입은 옷을 덮어 쓴다 (입히기 뒤 다시 불러오지 않아도 맞게 보이도록)
  function statusOf(item) {
    if (item.status === 'locked') return 'locked'
    return equipped[slot] === item.id ? 'wearing' : 'owned'
  }

  async function wear(clothesId) {
    setSaving(true)
    setSaveError('')
    try {
      const res = await api('/api/wardrobe/equip', { method: 'PUT', body: { slot, clothes_id: clothesId } })
      const next = {}
      for (const [k, v] of Object.entries(res.character)) next[k] = v ? v.id : null
      setWorn(next)
    } catch (err) {
      if (err.status === 401) onAuthError()
      else setSaveError(err.message) // 시안 13D 의상 착용 저장 실패: 입고 있던 옷은 그대로
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="wardrobe">
      <button type="button" onClick={onBack}>나의 기록으로</button>
      <h1>옷장</h1>

      {/* 내 캐릭터: 그림이 아직 없어서 입은 옷 이름을 글자로 보여 준다 */}
      <section className="wardrobe-character">
        <h2>내 캐릭터</h2>
        <ul>
          {data.slots.map((s) => {
            const item = s.items.find((i) => i.id === equipped[s.slot])
            return <li key={s.slot}>{s.label}: {item ? item.name : '없음'}</li>
          })}
        </ul>
      </section>

      <section className="wardrobe-closet">
        <nav className="wardrobe-tabs">
          {data.slots.map((s) => (
            <button key={s.slot} type="button" className={s.slot === slot ? 'is-selected' : ''}
              disabled={s.slot === slot} onClick={() => setSlot(s.slot)}>
              {s.label}{s.slot === slot ? ' (보는 중)' : ''}
            </button>
          ))}
        </nav>

        <h2>입고 싶은 옷을 골라요</h2>
        {ownedCount === 0 && <p>아직 받은 옷이 없어요. 일기와 동화를 쓰고 선물을 받아 보세요.</p>}
        {saveError && <p role="alert">옷을 바꾸지 못했어요. {saveError}</p>}

        <ul className="clothes-list">
          {current.items.map((item) => {
            const status = statusOf(item)
            return (
              <li key={item.id} className={`clothes-card is-${status}`}>
                <div>{item.name}</div>
                <div>{STATUS_LABEL[status]}</div>
                {status === 'owned' && (
                  <button type="button" disabled={saving} onClick={() => wear(item.id)}>입기</button>
                )}
                {status === 'wearing' && (
                  <button type="button" disabled={saving} onClick={() => wear(null)}>벗기</button>
                )}
                {status === 'locked' && (
                  <div className="clothes-condition">
                    {item.condition}
                    {item.progress && <div>{item.progress}</div>}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
