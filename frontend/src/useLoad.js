// 서버에서 화면에 필요한 자료를 불러오는 공통 도우미.
// path 가 바뀌면 다시 불러온다. 늦게 온 이전 응답은 버린다. 401 이면 onAuthError 를 부른다.
import { useEffect, useState } from 'react'
import { api } from './api.js'

export function useLoad(path, onAuthError) {
    const [state, setState] = useState({ path: null, data: null, error: null })
    const [reloadKey, setReloadKey] = useState(0)

    useEffect(() => {
        let ignore = false
        api(path)
            .then((data) => {
                if (!ignore) setState({ path, data, error: null })
            })
            .catch((error) => {
                if (ignore) return
                if (error.status === 401) onAuthError()
                else setState({ path, data: null, error })
            })
        return () => {
            ignore = true
        }
    }, [path, reloadKey, onAuthError])

    const current = state.path === path // 주소가 바뀐 직후에는 이전 화면의 자료를 쓰지 않는다
    return {
        data: current ? state.data : null,
        error: current ? state.error : null,
        retry: () => {
            setState({ path: null, data: null, error: null })
            setReloadKey((k) => k + 1)
        },
    }
}
