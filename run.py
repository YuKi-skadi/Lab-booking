#!/usr/bin/env python3
"""实验室预约登记系统 - 启动入口"""
import uvicorn

from backend.app.config import settings
from backend.app.runner import main

if __name__ == "__main__":
    if settings.app_role.strip().lower() == "split":
        main()
    else:
        uvicorn.run(
            "backend.app.main:app",
            host="0.0.0.0",
            port=settings.port,
            reload=True,
            log_level="info",
        )
