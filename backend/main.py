from fastapi import FastAPI

app = FastAPI()

# api 상태 확인용 테스트 코드
@app.get("/health")
def health():
    return {"status": "ok"}