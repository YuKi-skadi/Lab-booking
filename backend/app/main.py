from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict, deque
from time import monotonic
import os

from .config import settings
from .database import init_db
from .routers import bookings, agent, settings_router

PUBLIC_BOOKING_RATE_WINDOW = 10 * 60
PUBLIC_BOOKING_RATE_LIMIT = 60
_public_booking_attempts = defaultdict(deque)
_db_initialized = False


def _blocked_in_public_role(request: Request) -> bool:
    path = request.url.path
    method = request.method.upper()

    if path == "/admin" or path.startswith("/static/admin"):
        return True
    if path.startswith("/api/admin") and path != "/api/admin/public/form-config":
        return True
    if path in {
        "/api/bookings/all",
        "/api/bookings/batch-status",
        "/api/bookings/batch-delete",
    }:
        return True
    if path in {"/api/bookings", "/api/bookings/batch"}:
        # 公网预约页面通过 POST 提交；其它方法仍保持禁止，避免把管理能力暴露到公网。
        return method != "POST"
    if path.startswith("/api/bookings/"):
        # Keep only the POST self-cancellation flow available; GET must not mutate data.
        return not (method == "POST" and path.endswith("/cancel"))
    if path in {"/api/agent/query", "/api/agent/bookings"}:
        # These endpoints include personal booking details and stay local-only.
        return True
    return False


def _public_booking_rate_limited(request: Request) -> bool:
    if request.method.upper() != "POST" or request.url.path not in {"/api/bookings", "/api/bookings/batch"}:
        return False
    client_ip = request.client.host if request.client else "unknown"
    now = monotonic()
    attempts = _public_booking_attempts[client_ip]
    while attempts and now - attempts[0] >= PUBLIC_BOOKING_RATE_WINDOW:
        attempts.popleft()
    if len(attempts) >= PUBLIC_BOOKING_RATE_LIMIT:
        return True
    attempts.append(now)
    return False

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def create_app(role: str | None = None) -> FastAPI:
    """Create an application instance for one network role.

    In split mode the same container hosts two instances: public on port 8000
    and admin on port 8001. Keeping the role on the app instance avoids making
    route access depend on a client-controlled header or query parameter.
    """
    public_role = (role or settings.app_role).strip().lower() == "public"
    app = FastAPI(
        title="实验室预约登记系统",
        description="一个支持问卷式界面、Agent 接入、多存储后端的实验室预约系统",
        version="1.0.0",
        docs_url=None if public_role else "/docs",
        redoc_url=None if public_role else "/redoc",
        openapi_url=None if public_role else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Password"],
    )

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        if public_role and _blocked_in_public_role(request):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if public_role and _public_booking_rate_limited(request):
            return JSONResponse(
                status_code=429,
                content={"detail": "提交过于频繁，请稍后再试"},
                headers={"Retry-After": str(PUBLIC_BOOKING_RATE_WINDOW)},
            )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path == "/admin" or request.url.path.startswith("/api/admin"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(bookings.router)
    app.include_router(agent.router)
    app.include_router(settings_router.router)
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
        global _db_initialized
        if not _db_initialized and settings.storage_backend.lower() in ("sqlite", "mysql", "postgres"):
            init_db()
            _db_initialized = True

    return app


app = create_app(settings.app_role)
