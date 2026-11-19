// 백엔드 요청 도우미. 모든 화면은 fetch 대신 api() 를 쓴다.
// - 별명을 만들 때 받은 토큰을 브라우저에 보관하고, 요청마다 X-User-Token 헤더로 보낸다 (backend/auth.py).
// - 주소는 '/api/books' 처럼 앞부분 없이 쓴다. vite.config.js 의 프록시가 백엔드로 넘겨 준다.

const TOKEN_KEY = 'booksil_token'

// 개인정보 보호 모드 등에서 localStorage 가 막혀 있어도 화면이 죽지 않게 try 로 감싼다
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // 저장이 막힌 브라우저: 이번 접속 동안만 쓰고, 다시 오면 별명을 새로 만든다
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // 무시
  }
}

// status: 0 = 서버에 연결 못 함, 그 외는 HTTP 상태 코드 (400, 401, 404, 409, 503 ...)
export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// keepalive: true 면 화면이 닫히는 중에도 요청이 끝까지 간다 (글쓰기 화면이 가려질 때 쓰던 문장을 보낼 때 쓴다)
export async function api(path, { method = 'GET', body, keepalive = false, signal } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers['X-User-Token'] = token
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      keepalive,
      signal,
    })
  } catch {
    throw new ApiError(0, '서버에 연결하지 못했어요. 잠시 후 다시 해 주세요. (오류 코드: 서버-연결)')   // 백엔드 서버 자체에 닿지 못함 (DB 오류 DB-… 와 구분)
  }

  let data = null
  try {
    data = await res.json()
  } catch {
    // 본문이 JSON 이 아닌 응답 (프록시 오류 등)
  }

  if (!res.ok) {
    // FastAPI 는 detail 에 글자를 주지만, 요청 형식 오류(422)는 목록을 주므로 글자일 때만 그대로 쓴다
    // 서버가 문구를 주지 않은 오류(예기치 못한 500, 프록시 오류)는 HTTP 코드를 오류 코드로 붙인다
    const detail = typeof data?.detail === 'string' ? data.detail : `요청을 처리하지 못했어요. (오류 코드: HTTP-${res.status})`
    throw new ApiError(res.status, detail)
  }
  return data
}

// 한 줄에 JSON 하나씩 흘러오는 응답(/correct)을 받는다. 줄이 올 때마다 onEvent(객체)를 부른다.
export async function apiStream(path, body, onEvent) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['X-User-Token'] = token
  let res
  try {
    res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body) })
  } catch {
    throw new ApiError(0, '서버에 연결하지 못했어요. 잠시 후 다시 해 주세요. (오류 코드: 서버-연결)')   // 백엔드 서버 자체에 닿지 못함 (DB 오류 DB-… 와 구분)
  }
  if (!res.ok || !res.body) throw new ApiError(res.status, '요청을 처리하지 못했어요.')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    let i
    while ((i = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, i).trim()
      buffer = buffer.slice(i + 1)
      if (line) onEvent(JSON.parse(line))
    }
    if (done) break
  }
}

// 화면 동작 기록: 무엇을 눌렀는지를 서버의 logs/ui_날짜.log 로 보낸다 (backend/devlog.py).
// 결과를 기다리지 않고, 실패해도 무시한다. 문장 내용은 보내지 않는다 (번호 · 개수 · 고른 항목만).
const SESSION_ID = Math.random().toString(36).slice(2, 10) // 화면을 연 한 번을 묶는 번호

export function track(event, data, page = 'app') {
  try {
    const headers = { 'Content-Type': 'application/json' }
    const token = getToken()
    if (token) headers['X-User-Token'] = token
    fetch('/log/ui', {
      method: 'POST',
      headers,
      body: JSON.stringify({ event, sid: SESSION_ID, page, data: data || null }),
      keepalive: true,
    }).catch(() => {})
  } catch {
    // 기록을 못 해도 화면은 그대로
  }
}
