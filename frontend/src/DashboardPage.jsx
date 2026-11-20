// 대시보드 메인 (요구사항정의서 FR-042, 시안 12A · 12D). 아이와 어른이 같은 화면을 본다.
// GET /api/dashboard → 이번 주 일기 작성 요일(FR-024) · 다시 살펴볼 맞춤법(FR-043) · 내가 골라 쓴 표현(FR-044)
//                      · 일기 주간 선물(FR-039, diary_reward) · 내 캐릭터가 입은 옷(character)
// POST /api/rewards/diary/claim → 주간 선물 받기 (자동으로 주지 않고 아이가 눌러서 받는다)
// 대시보드 안의 화면: 최근 고친 문장(FR-021), 캐릭터 옷장(FR-041).
// 대시보드 안의 화면 이동은 이 파일 안에서 한다 (App.jsx 는 대시보드 하나만 연결).

import { useEffect, useState } from 'react'
import { api } from './api.js'
import RecentFixesPage from './RecentFixesPage.jsx'
import WardrobePage from './WardrobePage.jsx'

const SLOT_LABEL = { top: '상의', bottom: '하의', hat: '모자', shoes: '신발', gloves: '장갑' }

export default function DashboardPage({ onBack, onAuthError }) {
  const [view, setView] = useState('main') // 'main' 대시보드 메인 / 'fixes' 최근 고친 문장 / 'wardrobe' 옷장
  const [data, setData] = useState(null) // { owner, week, spelling, expressions, diary_reward, character }
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [claiming, setClaiming] = useState(false)
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
    setClaiming(true)
    setClaimMsg('')
    try {
      const res = await api('/api/rewards/diary/claim', { method: 'POST', body: { week_start: weekStart } })
      setData((d) => ({ ...d, diary_reward: res.diary_reward, character: res.character }))
      setClaimMsg(`선물을 받았어요: ${res.clothes.name}. 옷장에서 확인해요.`) // 시안 12E
    } catch (err) {
      if (err.status === 401) onAuthError()
      else setClaimMsg(`선물을 받지 못했어요. ${err.message}`) // 시안 12F
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
      setClaimMsg('')
      setView('main')
      setReloadKey((k) => k + 1)
    }
    return <WardrobePage onBack={backFromWardrobe} onAuthError={onAuthError} />
  }

  // 조회 실패는 '기록 없음'과 구분해서 보여 준다 (FR-033)
  if (error) {
    return (
      <div>
        <p role="alert">대시보드를 불러오지 못했어요. {error}</p>
        <button type="button" onClick={retry}>다시 불러오기</button>
        <button type="button" onClick={onBack}>목장으로</button>
      </div>
    )
  }
  if (!data) return <p>불러오는 중...</p>

  const { week, spelling, expressions, diary_reward: reward, character } = data

  return (
    <div>
      <button type="button" onClick={onBack}>목장으로</button>
      <h1>{data.owner}의 대시보드</h1>

      {/* 내 캐릭터: 그림이 아직 없어서 입은 옷 이름을 글자로 보여 준다 */}
      <section className="dashboard-character">
        <h2>내 캐릭터</h2>
        {character ? (
          <ul>
            {Object.entries(SLOT_LABEL).map(([slot, label]) => (
              <li key={slot}>{label}: {character[slot] ? character[slot].name : '없음'}</li>
            ))}
          </ul>
        ) : (
          <p>캐릭터를 불러오지 못했어요.</p>
        )}
        <button type="button" onClick={() => setView('wardrobe')}>옷장</button>
      </section>

      {/* FR-039 일기 주간 선물: 3문장 이상 쓴 일기가 있는 날이 한 주에 5일이면 받는다 */}
      <section className="dashboard-gift">
        <h2>이번 주 선물</h2>
        {!reward ? (
          <p>선물 정보를 불러오지 못했어요.</p>
        ) : (
          <>
            <p>{reward.progress.count} / {reward.progress.need}일 (3문장 이상 쓴 일기 기준)</p>
            {reward.this_week.clothes && <p>선물: {reward.this_week.clothes.name} ({reward.this_week.clothes.slot_label})</p>}
            {reward.this_week.status === 'claimable' && (
              <button type="button" disabled={claiming} onClick={() => claim(reward.this_week.week_start)}>선물 받기</button>
            )}
            {reward.this_week.status === 'claimed' && <p>이번 주 선물을 받았어요.</p>}
            {reward.this_week.status === 'locked' && (
              <p>{reward.progress.need - reward.progress.count}일 더 쓰면 선물을 받을 수 있어요.</p>
            )}
            {reward.this_week.status === 'none' && <p>준비된 선물을 모두 받았어요.</p>}

            {reward.unclaimed.length > 0 && (
              <div className="dashboard-gift-unclaimed">
                <p>지난 주 선물도 받을 수 있어요.</p>
                <ul>
                  {reward.unclaimed.map((u) => (
                    <li key={u.week_start}>
                      {u.week_start} 주 · {u.clothes.name}{' '}
                      <button type="button" disabled={claiming} onClick={() => claim(u.week_start)}>받기</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {claimMsg && <p role="status">{claimMsg}</p>}
          </>
        )}
      </section>

      {/* FR-024 이번 주 일기 작성 요일 */}
      <section>
        <h2>이번 주 일기</h2>
        <p>{week.start} ~ {week.end} · {week.count}일 썼어요</p>
        <ul>
          {week.days.map((d) => (
            <li key={d.date}>
              {d.weekday} {d.written ? '○' : '·'}
            </li>
          ))}
        </ul>
      </section>

      {/* FR-043 다시 살펴볼 맞춤법: 서로 다른 글 여러 개에서 반복해 고친 항목 */}
      <section>
        <h2>다시 살펴볼 맞춤법</h2>
        {spelling.items.length === 0 ? (
          <p>아직 여러 글에서 반복해 고친 맞춤법이 없어요.</p>
        ) : (
          <ul>
            {spelling.items.map((x) => (
              <li key={`${x.before}→${x.after}`}>
                <div>{x.before} → {x.after} (글 {x.entry_count}개에서 고쳤어요)</div>
                {x.explanation && <div>{x.explanation}</div>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* FR-044 내가 골라 쓴 표현 (원래 표현을 틀린 것처럼 보이지 않게 '→ 골라 쓴 표현'으로만 보여 준다) */}
      <section>
        <h2>내가 골라 쓴 표현</h2>
        {expressions.items.length === 0 ? (
          <p>아직 골라 쓴 표현이 없어요. 동화를 쓰면서 마음에 드는 표현을 골라 보세요.</p>
        ) : (
          <ul>
            {expressions.items.map((x) => (
              <li key={x.sentence_id}>
                <div>[{x.book_title}]</div>
                <div>처음 쓴 문장: {x.original}</div>
                <div>골라 쓴 문장: {x.picked}</div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* FR-021 · FR-041: 대시보드 안의 다른 화면 */}
      <nav>
        <button type="button" onClick={() => setView('fixes')}>최근 고친 문장</button>
        <button type="button" onClick={() => setView('wardrobe')}>캐릭터 옷장</button>
      </nav>
    </div>
  )
}
