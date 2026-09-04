"""Run one normal app or two role-separated listeners in one container."""

import asyncio

import uvicorn

from .config import settings
from .main import create_app


async def _serve(app, port: int):
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def _run_split():
    await asyncio.gather(
        _serve(create_app("public"), settings.port),
        _serve(create_app("admin"), settings.admin_port),
    )


def main():
    if settings.app_role.strip().lower() == "split":
        asyncio.run(_run_split())
        return

    uvicorn.run(
        create_app(settings.app_role),
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
