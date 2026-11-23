// 불러오기 실패 안내 (없는 것 404 / 그 밖은 서버가 준 문구 그대로)
// 서버 문구에는 끝에 짧은 오류 코드가 붙어 있다 (예: '… (오류 코드: DB-1054)'. backend/db.py 의 DBError). 원문은 서버 로그에 있다
export default function LoadError({ error, what, onRetry, onHome }) {
    const message =
        error.status === 404 ? `${what}을(를) 찾을 수 없어요.`
        : error.message
    return (
        <div>
            <p role="alert">{message}</p>
            <button type="button" onClick={onRetry}>다시 시도</button>{' '}
            <button type="button" onClick={onHome}>목장으로</button>
        </div>
    )
}
