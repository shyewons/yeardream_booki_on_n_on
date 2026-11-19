// 메인 페이지 화면 : 책 리스트 (요구사항정의서 차트 - 화면ID 시트 - 02번 화면, FR-001 · FR-003)
// GET /api/books?page=N → 한 쪽 6권. 빈 목장과 불러오기 실패를 구분해서 보여 준다 (FR-033).

import { useEffect, useState } from 'react'
import { api } from './api.js'
import sheep from './assets/characters/sheep.png'
import alpaca from './assets/characters/alpaca.png'
import './HomeListPage.css'

const KIND_LABEL = { diary: '일기', fairy: '동화' }

export default function HomeListPage({ onCreateBook, onOpenBook, onOpenDashboard, onAuthError }) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null) // { owner, items, page, total, total_pages }
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0) // '다시 불러오기'를 누를 때 바꾼다
  const [loadedRequest, setLoadedRequest] = useState(null)
  const requestKey = `${page}:${reloadKey}`
  const loading = loadedRequest !== requestKey
  const showError = !loading && !!error

  useEffect(() => {
    let ignore = false // 쪽을 빨리 넘길 때 늦게 온 이전 응답이 화면을 덮지 않게
    api(`/api/books?page=${page}`)
      .then((res) => {
        if (!ignore) {
          setData(res)
          setError('')
          setLoadedRequest(`${page}:${reloadKey}`)
        }
      })
      .catch((err) => {
        if (ignore) return
        if (err.status === 401) onAuthError()
        else {
          setError(err.message)
          setLoadedRequest(`${page}:${reloadKey}`)
        }
      })
    return () => {
      ignore = true
    }
  }, [page, reloadKey, onAuthError])

  function retry() {
    setError('')
    setReloadKey((k) => k + 1)
  }

  const totalPages = Math.max(1, data?.total_pages ?? 1)

  return (
    <main className="farm-screen" aria-labelledby="farm-heading">
      <header className="farm-screen__header">
        <div className="farm-screen__sign-wrap">
          <span className="farm-screen__rope farm-screen__rope--left" aria-hidden="true" />
          <span className="farm-screen__rope farm-screen__rope--right" aria-hidden="true" />
          <h1 className="ui-title farm-screen__sign farm-screen__paper" id="farm-heading">
            {data?.owner ? `${data.owner}의 목장` : '나의 목장'}
          </h1>
        </div>
        <div className="farm-screen__actions">
          <button className="ui-button ui-button--secondary" type="button" onClick={onOpenDashboard}>
            <span className="farm-screen__icon farm-screen__icon--records" aria-hidden="true" />나의 기록
          </button>
          <button className="ui-button ui-button--primary" type="button" onClick={onCreateBook}>
            <span className="farm-screen__icon farm-screen__icon--plus" aria-hidden="true" />새 책 만들기
          </button>
        </div>
      </header>

      <section className="farm-screen__content" aria-label="내 책 목록" aria-busy={loading}>
        <div inert={loading || showError}>
          {data?.total === 0 && !loading && !showError && (
            <div className="farm-screen__panel farm-screen__paper farm-screen__welcome">
              <p className="ui-body">{data.owner}, 반가워!</p>
              <h2 className="ui-title">첫 책을 만들어 볼까요?</h2>
              <button className="ui-button ui-button--primary ui-button--large" type="button" onClick={onCreateBook}>
                <span className="farm-screen__icon farm-screen__icon--plus" aria-hidden="true" />새 책 만들기
              </button>
            </div>
          )}
          {!!data?.items.length && (
            <>
              <ul className="farm-screen__books">
                {data.items.map((book) => (
                  <li key={book.id} className="farm-screen__book">
                    <button className="farm-screen__book-button" type="button" onClick={() => onOpenBook(book)} aria-label={`${KIND_LABEL[book.kind] ?? book.kind}, ${book.title} 열기`}>
                      <span className="farm-screen__animal-wrap">
                        <img className={`farm-screen__animal farm-screen__animal--${book.kind}`} src={book.kind === 'fairy' ? alpaca : sheep} alt="" />
                      </span>
                      <span className="farm-screen__category farm-screen__paper">{KIND_LABEL[book.kind] ?? book.kind}</span>
                      <span className="farm-screen__book-title farm-screen__paper">{book.title}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <nav className="farm-screen__pagination" aria-label="책 목록 페이지">
                <button className="ui-button ui-button--secondary farm-screen__arrow farm-screen__arrow--previous" type="button" aria-label="이전 페이지" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>
                  <span className="farm-screen__icon farm-screen__icon--chevron" aria-hidden="true" />
                </button>
                <div className="farm-screen__dots">
                  {Array.from({ length: totalPages }, (_, index) => index + 1).map((number) => (
                    <button className="farm-screen__dot" type="button" key={number} aria-label={`${number}페이지`} aria-current={page === number ? 'page' : undefined} disabled={loading} onClick={() => setPage(number)} />
                  ))}
                </div>
                <button className="ui-button ui-button--secondary farm-screen__arrow farm-screen__arrow--next" type="button" aria-label="다음 페이지" disabled={page >= totalPages || loading} onClick={() => setPage(page + 1)}>
                  <span className="farm-screen__icon farm-screen__icon--chevron" aria-hidden="true" />
                </button>
              </nav>
            </>
          )}
        </div>

        {loading && (
          <div className="farm-screen__overlay farm-screen__overlay--loading">
            <p className="ui-notice" role="status">목장을 불러오는 중이에요...</p>
          </div>
        )}
        {showError && (
          <div className="farm-screen__overlay">
            <div className="farm-screen__panel farm-screen__paper">
              <h2 className="ui-title" role="alert">목장을 불러오지 못했어요.</h2>
              <p className="ui-description">잠시 후 다시 확인해 주세요.</p>
              <button className="ui-button ui-button--primary" type="button" onClick={retry}>다시 불러오기</button>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
