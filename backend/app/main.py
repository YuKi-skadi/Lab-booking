from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from .config import settings
from .database import init_db
from .routers import bookings, agent, settings_router

app = FastAPI(
    title="实验室预约登记系统",
    description="一个支持问卷式界面、Agent 接入、多存储后端的实验室预约系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bookings.router)
app.include_router(agent.router)
app.include_router(settings_router.router)

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>实验室预约登记系统</h1><p><a href='/static/index.html'>进入预约页面</a></p>")


@app.get("/admin", response_class=HTMLResponse)
async def admin():
    admin_path = os.path.join(static_dir, "admin.html")
    if os.path.exists(admin_path):
        with open(admin_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>管理面板</h1>")


@app.get("/health")
async def health():
    return {"status": "ok", "storage_backend": settings.storage_backend}


@app.on_event("startup")
async def startup():
    if settings.storage_backend.lower() in ("sqlite", "mysql", "postgres"):
        init_db()
