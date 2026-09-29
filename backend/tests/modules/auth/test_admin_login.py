from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from modules.auth import router, schemas
from modules.auth.models import Role


@pytest.mark.parametrize("role,deleted,suspended,valid_password", [
    (Role.creator, False, False, True),
    (Role.organisation, False, False, True),
    (Role.admin, True, False, True),
    (Role.admin, False, True, True),
    (Role.admin, False, False, False),
])
async def test_admin_login_rejects_without_creating_session(monkeypatch, role, deleted, suspended, valid_password):
    user = SimpleNamespace(role=role, deleted_at=datetime.now(timezone.utc) if deleted else None,
        suspended_at=datetime.now(timezone.utc) if suspended else None, suspension_scopes=["access"],
        has_password=True, password_hash="hash")
    monkeypatch.setattr(router, "_user_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(router, "verify_password", lambda *_: valid_password)
    start = AsyncMock()
    monkeypatch.setattr(router.sessions, "start_session", start)
    with pytest.raises(HTTPException) as error:
        await router.admin_login.__wrapped__(Request({"type": "http"}), schemas.LoginRequest(email="admin@example.com", password="bad"), AsyncMock())
    assert error.value.status_code == 401
    start.assert_not_awaited()


async def test_admin_login_issues_session(monkeypatch):
    import uuid
    user = SimpleNamespace(id=uuid.uuid4(), email="admin@example.com", full_name="Admin", role=Role.admin,
        created_at=datetime.now(timezone.utc), email_verified=True, onboarding_completed=True,
        deleted_at=None, suspended_at=None, has_password=True, password_hash="hash")
    monkeypatch.setattr(router, "_user_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(router, "verify_password", lambda *_: True)
    monkeypatch.setattr(router.sessions, "start_session", AsyncMock(return_value=SimpleNamespace(access_token="access", refresh_token="refresh")))
    db = AsyncMock()
    result = await router.admin_login.__wrapped__(Request({"type": "http"}), schemas.LoginRequest(email=user.email, password="valid"), db)
    assert result.user.role == Role.admin
    assert result.access_token == "access"
    db.commit.assert_awaited_once()
