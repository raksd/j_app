from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import applications, cv, files, jobs

app = FastAPI(title="Job Application Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (cv, jobs, applications, files):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
