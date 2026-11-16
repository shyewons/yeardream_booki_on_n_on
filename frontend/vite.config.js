import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 백엔드(FastAPI) 주소. 개발 서버(npm run dev)가 아래 주소로 온 요청을 백엔드로 넘겨 준다.
// 그래서 화면 코드에서는 fetch('/api/books') 처럼 주소 앞부분 없이 쓰면 된다 (CORS 설정도 필요 없다).
const BACKEND = 'http://127.0.0.1:8000'
const toBackend = ['/api', '/question', '/topics', '/validate', '/correct', '/suggest', '/health']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(toBackend.map((path) => [path, BACKEND])),
  },
})
