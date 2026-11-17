// 불러오기 실패 안내 (없는 것 404 / DB 연결 실패 503 / 그 밖)
export default function LoadError({ error, what, onRetry, onHome }) {
    const message =
        error.status === 404 ? `${what}을(를) 찾을 수 없어요.`
        : error.status === 503 ? `서버가 DB에 연결하지 못했어요. ${error.message}`
        : error.message
    return (
        <div>
            <p role="alert">{message}</p>
            <button type="button" onClick={onRetry}>다시 시도</button>{' '}
            <button type="button" onClick={onHome}>목장으로</button>
        </div>
    )
}
