"""Errors the engine returns to the portal."""

from __future__ import annotations


class EngineError(Exception):
    def __init__(self, status: int, message: str, issues: list[dict] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.issues = issues or []
