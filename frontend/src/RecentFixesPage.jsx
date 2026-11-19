// 최근 고친 문장 (요구사항정의서 FR-021). 대시보드 안에서 들어오는 화면.
// GET /api/dashboard/recent-fixes → 교정을 받은 문장을 아이가 직접 다시 써서 바꾼 기록 (최근 것부터)
// '고친 뒤'는 아이가 실제로 다시 쓴 문장이다. AI가 제안한 문장으로 대신 보여 주지 않는다.

import { useLoad } from './useLoad.js'
import { fmtTime } from './format.js'

export default function RecentFixesPage({ onBack, onAuthError }) {
  const { data, error, retry } = useLoad('/api/dashboard/recent-fixes', onAuthError)

  // 조회 실패는 '기록 없음'과 구분해서 보여 준다 (FR-033)
  if (error) {
    return (
      <div>
        <p role="alert">최근 고친 문장을 불러오지 못했어요. {error.message}</p>
        <button type="button" onClick={retry}>다시 불러오기</button>
        <button type="button" onClick={onBack}>대시보드로</button>
      </div>
    )
  }
  if (!data) return <p>불러오는 중...</p>

  return (
    <div>
      <button type="button" onClick={onBack}>대시보드로</button>
      <h1>최근 고친 문장</h1>

      {data.items.length === 0 ? (
        <p>아직 직접 고친 문장이 없어요. 글을 보다가 고쳐 쓰면 여기에 모여요.</p>
      ) : (
        <ul>
          {data.items.map((x) => (
            <li key={x.sentence_id}>
              <div>{fmtTime(x.fixed_at)} · {x.kind_label} · [{x.book_title}]</div>
              <div>고치기 전: {x.before}</div>
              <div>고친 뒤: {x.after}</div>
              {x.reasons.length > 0 && (
                <ul>
                  {x.reasons.map((r, i) => (
                    <li key={i}>
                      {r.before} → {r.after}
                      {r.explanation && <div>{r.explanation}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
