from __future__ import annotations

import asyncio
import socket

import httpx


def is_retryable_browser_use_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, socket.gaierror)):
        return True
    if isinstance(exc, httpx.HTTPError):
        return True
    return False
