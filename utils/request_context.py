#!/usr/bin/env python3
"""Request-scoped authenticated user context."""

from contextvars import ContextVar, Token
from typing import Any, Dict, Optional

UserContext = Optional[Dict[str, Any]]
_current_user: ContextVar[UserContext] = ContextVar("current_user", default=None)


def set_user_context(user: UserContext) -> Token:
    """Set the authenticated user for the current request context."""
    return _current_user.set(user)


def get_user_context() -> UserContext:
    """Return the authenticated user for the current request context."""
    return _current_user.get()


def is_current_user_admin() -> bool:
    """Return whether the current request's user is an administrator.

    This fails closed. Without a request context there is no authenticated
    identity to authorize, so the caller is treated as a non-administrator.
    """
    user = get_user_context()

    if user is None:
        # No request context: nobody has been authenticated, so deny admin.
        return False

    if "is_admin" not in user:
        # Authenticated, but no role was resolved for this request: deny admin.
        return False

    return bool(user["is_admin"])


def reset_user_context(token: Token) -> None:
    """Restore the user context that existed before the current request."""
    _current_user.reset(token)
