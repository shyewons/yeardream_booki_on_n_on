// 대시보드 메인 (요구사항정의서 FR-042). 아이와 어른이 같은 화면을 본다.
// GET /api/dashboard → 이번 주 일기 작성 요일(FR-024) · 다시 살펴볼 맞춤법(FR-043) · 내가 골라 쓴 표현(FR-044)
// 대시보드 안의 화면: 최근 고친 문장(FR-021). 캐릭터 옷장(FR-041)은 아직 준비 중.
// 대시보드 안의 화면 이동은 이 파일 안에서 한다 (App.jsx 는 대시보드 하나만 연결).

import { useEffect, useState } from 'react'
import { api } from './api.js'
import RecentFixesPage from './RecentFixesPage.jsx'

export default function DashboardPage({ onBack, onAuthError }) {
  const [view, setView] = useState('main') // 'main' 대시보드 메인 / 'fixes' 최근 고친 문장
  const [data, setData] = useState(null) // { owner, week, spelling, expressions }
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

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

  if (view === 'fixes') {
    return <RecentFixesPage onBack={() => setView('main')} onAuthError={onAuthError} />
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

  const { week, spelling, expressions } = data

  return (
    <div>
      <button type="button" onClick={onBack}>목장으로</button>
      <h1>{data.owner}의 대시보드</h1>

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

      {/* FR-021 · FR-041: 대시보드 안의 다른 화면 (아직 없음) */}
      <nav>
        <button type="button" onClick={() => setView('fixes')}>최근 고친 문장</button>
        <button type="button" disabled>캐릭터 옷장 (준비 중)</button>
      </nav>
    </div>
  )
}
