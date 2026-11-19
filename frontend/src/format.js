// 보기 좋게 바꾸는 함수들 (여러 화면이 함께 쓴다)

const WEEK = ['일', '월', '화', '수', '목', '금', '토']
const pad = (n) => String(n).padStart(2, '0')

export const KIND_LABEL = { diary: '일기', fairy: '동화' }
export const COVER = { sheep: '🐑', alpaca: '🦙' }

// '2026-11-16' → '2026-11-16 (월)'. 날짜가 없으면(동화) '이야기'
export function fmtDate(s) {
    if (!s) return '이야기'
    const [y, m, d] = String(s).slice(0, 10).split('-').map(Number)
    return `${y}-${pad(m)}-${pad(d)} (${WEEK[new Date(y, m - 1, d).getDay()]})`
}

// '2026-11-16T09:30:00' → '2026-11-16 09:30'
export const fmtTime = (s) => (s ? String(s).replace('T', ' ').slice(0, 16) : '')

// 오늘 날짜 (한국 시간) '2026-11-16'
export const todayKST = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())

// 동화 장을 글쓰기 화면에 넘기는 값 (App.jsx 의 writeDate 자리에 날짜 대신 들어간다. writer.js 의 openBody 가 읽는다)
//   chapterTarget(3) → 'ch3' (3장)   NEW_CHAPTER → 'new' (새 장)   null → 마지막 장
export const chapterTarget = (n) => `ch${n}`
export const NEW_CHAPTER = 'new'

// 근거 표시: "근거: 한글 맞춤법 제43항 100쪽 · ...".
// 문서 이름을 붙이는 이유: 두 문서(한글 맞춤법 / 표준어 사정 원칙)에 같은 조항 번호가 있다.
// 근거가 여러 개(evidences)면 모두, 없으면 대표 근거(evidence) 하나. 예전 글은 문서 이름이 없어 조항과 쪽만 나온다.
export function evidenceText(c) {
    const one = (e) => [e.part, e.article, e.page ? `${e.page}쪽` : null].filter(Boolean).join(' ')
    const list = (c.evidences && c.evidences.length ? c.evidences : c.evidence ? [c.evidence] : []).map(one).filter(Boolean)
    return list.length ? `근거: ${list.join(' · ')}` : ''
}

// 쪽 번호 목록: 1 … 4 5 6 … 12 처럼 줄여서 (null 은 '…')
export function pageNumbers(page, total) {
    const keep = new Set([1, total, page - 1, page, page + 1])
    const out = []
    let prev = 0
    for (let n = 1; n <= total; n += 1) {
        if (!keep.has(n)) continue
        if (n - prev > 1) out.push(null)
        out.push(n)
        prev = n
    }
    return out
}
