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

export async function api(path, { method = 'GET', body } = {}) {
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
    })
  } catch {
    throw new ApiError(0, '서버에 연결하지 못했어요. 잠시 후 다시 해 주세요.')
  }

  let data = null
  try {
    data = await res.json()
  } catch {
    // 본문이 JSON 이 아닌 응답 (프록시 오류 등)
  }

  if (!res.ok) {
    // FastAPI 는 detail 에 글자를 주지만, 요청 형식 오류(422)는 목록을 주므로 글자일 때만 그대로 쓴다
    const detail = typeof data?.detail === 'string' ? data.detail : '요청을 처리하지 못했어요.'
    throw new ApiError(res.status, detail)
  }
  return data
}
