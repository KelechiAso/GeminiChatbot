# app/main.py
print("--- app/main.py: TOP OF FILE (minimal) ---")
from fastapi import FastAPI
print("--- app/main.py: FastAPI IMPORTED (minimal) ---")

app = FastAPI(title="Minimal Railway Test")
print("--- app/main.py: FastAPI INSTANCE CREATED (minimal) ---")

@app.get("/")
async def read_root():
    print("--- app/main.py: / endpoint CALLED (minimal) ---")
    return {"message": "Minimal app is alive!"}

@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED (minimal) ---")
    return {"status": "ok_minimal"}

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED (minimal) ---")