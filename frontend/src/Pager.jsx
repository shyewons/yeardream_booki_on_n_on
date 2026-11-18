// 쪽 이동 (맨 처음 « · 이전 · 번호 · 다음 · 맨 끝 »). 번호를 누르면 onGo(쪽 번호) 를 부른다.
import { pageNumbers } from './format.js'

export default function Pager({ page, totalPages, total, unit, onGo }) {
    if (!totalPages) return null
    const n = totalPages
    const item = (label, to, off, key) => (
        <button
            key={key}
            type="button"
            disabled={off}
            aria-current={to === page && key.startsWith('p') ? 'page' : undefined}
            onClick={() => onGo(to)}
        >
            {label}
        </button>
    )
    return (
        <div>
            {n > 1 && (
                <nav className="pager" aria-label="쪽 이동">
                    {item('«', 1, page <= 1, 'first')}
                    {item('◀ 이전', page - 1, page <= 1, 'prev')}
                    {pageNumbers(page, n).map((v, i) =>
                        v === null ? <span key={`gap${i}`}> … </span> : item(String(v), v, v === page, `p${v}`),
                    )}
                    {item('다음 ▶', page + 1, page >= n, 'next')}
                    {item('»', n, page >= n, 'last')}
                </nav>
            )}
            <p className="count">{page} / {n}쪽 · 전체 {total}{unit}</p>
        </div>
    )
}
