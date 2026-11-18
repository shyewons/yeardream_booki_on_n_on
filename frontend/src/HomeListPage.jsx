// 메인 페이지 화면 : 책 리스트 (요구사항정의서 차트 - 화면ID 시트 - 02번 화면, FR-001 · FR-003)
// GET /api/books?page=N → 한 쪽 6권. 빈 목장과 불러오기 실패를 구분해서 보여 준다 (FR-033).

import { useEffect, useState } from 'react'
import { api } from './api.js'

const KIND_LABEL = { diary: '일기', fairy: '동화' }

export default function HomeListPage({ onCreateBook, onOpenBook, onOpenDashboard, onAuthError }) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null) // { owner, items, page, total, total_pages }
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0) // '다시 불러오기'를 누를 때 바꾼다

  useEffect(() => {
    let ignore = false // 쪽을 빨리 넘길 때 늦게 온 이전 응답이 화면을 덮지 않게
    api(`/api/books?page=${page}`)
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
  }, [page, reloadKey, onAuthError])

  function retry() {
    setError('')
    setReloadKey((k) => k + 1)
  }

  if (error) {
    return (
      <div>
        <p role="alert">책장을 불러오지 못했어요. {error}</p>
        <button type="button" onClick={retry}>다시 불러오기</button>
      </div>
    )
  }
  if (!data) return <p>불러오는 중...</p>

  const totalPages = Math.max(1, data.total_pages)

  return (
    <div>
      <h1>{data.owner}의 목장</h1>
      <button type="button" onClick={onCreateBook}>새 책 만들기</button>
      <button type="button" onClick={onOpenDashboard}>대시보드</button>

      {data.total === 0 ? (
        <p>아직 책이 없어요. 첫 책을 만들어 볼까요?</p>
      ) : (
        <>
          <ul>
            {data.items.map((book) => (
              <li key={book.id}>
                <button type="button" onClick={() => onOpenBook(book)}>
                  [{KIND_LABEL[book.kind] ?? book.kind}] {book.title}
                </button>
              </li>
            ))}
          </ul>
          <div>
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>이전</button>
            <span> {page} / {totalPages} </span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>다음</button>
          </div>
        </>
      )}
    </div>
  )
}
