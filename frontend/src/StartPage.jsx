import logo from './assets/icons/buksilbuksil-logo.png'
import './StartPage.css'

// 사용자 확인은 App이 담당하고, 이 화면은 전달받은 상태만 표시한다.
export default function StartPage({ status, error, onStart, onRetry }) {
  return (
    <main className="start-screen" aria-label="북실북실 시작">
      <div className="start-screen__content">
        <img className="start-screen__logo" src={logo} alt="북실북실" width="1820" height="807" fetchPriority="high" />
        <div className="start-screen__status" aria-live="polite">
          {status === 'loading' && (
            <div className="start-screen__progress" role="progressbar" aria-label="불러오는 중">
              <div className="start-screen__fill" />
            </div>
          )}
          {status === 'ready' && (
            <button className="ui-button ui-button--primary ui-button--large start-screen__button" type="button" onClick={onStart}>
              <span>시작하기</span>
            </button>
          )}
          {status === 'error' && (
            <div className="start-screen__error">
              <p className="ui-notice ui-notice--error" role="alert">{error}</p>
              <button className="ui-button ui-button--primary ui-button--large start-screen__button" type="button" onClick={onRetry}>
                <span>다시 시도</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
