// 14A~14C 최근 고친 문장. 서버가 보내는 직접 수정 기록과 순서를 그대로 표시한다.
// after는 아이가 다시 쓴 문장이다. 교정 모델의 제안문으로 바꾸지 않는다.
import { useLoad } from './useLoad.js'
import { fmtTime } from './format.js'
import './RecentFixesPage.css'

// 어절 단위로 실제 달라진 부분만 강조한다. 같은 표현이 반복되어도 일치한 위치는 강조하지 않는다.
function ChangedSentence({ before, after }) {
    const original = (before || '').split(/(\s+)/u).filter(Boolean)
    const updated = (after || '').split(/(\s+)/u).filter(Boolean)
    // 비정상적으로 긴 기록도 전체 텍스트는 표시하되, 비교 때문에 화면이 멈추지 않게 한다.
    if (original.length * updated.length > 250000) return after

    const rows = Array.from({ length: original.length + 1 }, () => new Uint32Array(updated.length + 1))
    for (let i = original.length - 1; i >= 0; i--) {
        for (let j = updated.length - 1; j >= 0; j--) {
            rows[i][j] = original[i] === updated[j]
                ? rows[i + 1][j + 1] + 1
                : Math.max(rows[i + 1][j], rows[i][j + 1])
        }
    }
    const unchanged = new Set()
    let i = 0
    let j = 0
    while (i < original.length && j < updated.length) {
        if (original[i] === updated[j]) {
            unchanged.add(j)
            i++
            j++
        } else if (rows[i + 1][j] >= rows[i][j + 1]) i++
        else j++
    }
    return updated.map((part, index) => unchanged.has(index)
        ? part
        : <mark key={index}>{part}</mark>)
}

function EmptyIllustration() {
    return <div className="recent-fixes__illustration" aria-hidden="true">
        <div className="recent-fixes__bubble recent-fixes__bubble--large"><span /><span /><span /></div>
        <div className="recent-fixes__bubble recent-fixes__bubble--small"><span /><span /><span /></div>
    </div>
}

export default function RecentFixesPage({ onBack, onAuthError }) {
    const { data, error, retry } = useLoad('/api/dashboard/recent-fixes', onAuthError)

    return <main className="recent-fixes" aria-labelledby="recent-fixes-title">
        <header className="recent-fixes__header">
            <button type="button" className="ui-button ui-button--secondary ui-button--small" onClick={onBack}>
                <span aria-hidden="true">←</span> 나의 기록
            </button>
        </header>

        <section className="recent-fixes__panel">
            <h1 className="ui-title" id="recent-fixes-title">최근 고친 문장</h1>
            {error ? <div className="recent-fixes__state recent-fixes__state--error">
                <div className="recent-fixes__error-card">
                    <h2 role="alert">기록을 불러오지 못했어요.</h2>
                    <p>잠시 후 다시 불러와 주세요.</p>
                    <details>
                        <summary>오류 내용 보기</summary>
                        <p>{error.message}</p>
                    </details>
                </div>
                <button type="button" className="ui-button ui-button--primary" onClick={retry}>다시 불러오기</button>
            </div> : !data ? <div className="recent-fixes__state" aria-busy="true">
                <p role="status">고친 문장을 불러오고 있어요.</p>
            </div> : data.items.length === 0 ? <div className="recent-fixes__state recent-fixes__state--empty">
                <EmptyIllustration />
                <h2>아직 고친 문장이 없어요.</h2>
                <p>문장을 직접 고쳐 쓰면 이곳에서 다시 볼 수 있어요.</p>
            </div> : <div className="recent-fixes__scroll" tabIndex="0" role="region" aria-label="최근 고친 문장 목록">
                <ul className="recent-fixes__list">
                    {data.items.map((item) => <li key={item.sentence_id}>
                        <article className="recent-fixes__card" aria-labelledby={'fix-' + item.sentence_id}>
                            <header className="recent-fixes__card-heading">
                                <h2 id={'fix-' + item.sentence_id}>{item.kind_label} · <time dateTime={item.fixed_at}>{fmtTime(item.fixed_at)}</time></h2>
                                <p className="recent-fixes__book ui-muted">{item.book_title}</p>
                            </header>
                            <dl className="recent-fixes__comparison">
                                <dt>처음 쓴 문장</dt>
                                <dd className="recent-fixes__sentence recent-fixes__before">{item.before}</dd>
                                <dt>내가 고친 문장</dt>
                                <dd className="recent-fixes__sentence recent-fixes__after"><ChangedSentence before={item.before} after={item.after} /></dd>
                                {item.reasons.length > 0 && <>
                                    <dt>이렇게 고쳤어요</dt>
                                    <dd className="recent-fixes__reasons">
                                        <ul>{item.reasons.map((reason, index) => <li key={index}>
                                            <p className="recent-fixes__reason-pair"><span>{reason.before}</span><span aria-hidden="true"> → </span><span>{reason.after}</span></p>
                                            {reason.explanation && <p>{reason.explanation}</p>}
                                        </li>)}</ul>
                                    </dd>
                                </>}
                            </dl>
                        </article>
                    </li>)}
                </ul>
            </div>}
        </section>
    </main>
}
