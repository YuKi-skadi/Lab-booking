"""Shared administrator authentication dependency.

The query-string password remains supported for backwards compatibility with
older clients, but the web admin uses the header form so credentials do not
appear in URLs, browser history, or typical access logs.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Query

from .settings_manager import get_settings_manager


def get_admin_password(
    password: Optional[str] = Query(default=None),
    header_password: Optional[str] = Header(default=None, alias="X-Admin-Password"),
) -> str:
    """Accept the safer header first, with legacy query support as fallback."""
    return header_password or password or ""


def require_admin(password: str = Depends(get_admin_password)) -> str:
    if not get_settings_manager().check_admin_password(password):
        raise HTTPException(status_code=403, detail="密码错误")
    return password
