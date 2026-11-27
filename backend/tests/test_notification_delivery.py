from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import notification_preferences
from core import database
from core.dependencies import get_current_user
from domain.models.notification_preferences import NotificationPreferences
from domain.services import enhanced_notification_service as notifications
from domain.services.webhook_event_processor import WebhookEventProcessor


@pytest.mark.anyio
@pytest.mark.parametrize("preference", [
    {"enable_in_app": False}, {"min_priority": "high"}, {"mute_categories": ["pr_opened"]},
])
async def test_saved_preferences_control_routine_project_alerts(mock_db, monkeypatch, preference):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    processor = WebhookEventProcessor()
    monkeypatch.setattr(processor, "_get_project_team_lead", AsyncMock(return_value="lead"))
    service = processor.notification_service
    monkeypatch.setattr(notification_preferences, "repo", service.preferences)
    app = FastAPI()
    app.include_router(notification_preferences.router, prefix="/api/notifications")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "lead"}
    url = "/api/notifications/preferences"
    pr = {"id": "P1", "number": 1, "title": "Update search"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(url, json={"user_id": "someone-else", **preference})
        assert response.status_code == 200
        assert await service.preferences.find_by_user("someone-else") is None
        saved = (await client.get(url)).json()
        assert saved["user_id"] == "lead" and all(saved[key] == value for key, value in preference.items())
        assert await processor._notify_pr_opened(pr, "low", "project") == []
        assert await service.get_unread_count("lead") == 0
        assert await service.notify("lead", "approval_request", "Approval required", "Review the request")

        assert (await client.delete(url)).status_code == 200
        assert len(await processor._notify_pr_opened(pr, "low", "project")) == 1
        assert await service.get_unread_count("lead") == 2


@pytest.mark.anyio
async def test_saved_digest_frequency_preserves_immediate_inbox_delivery(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    service = notifications.EnhancedNotificationService()
    await service.preferences.upsert("lead", {"digest_frequency": "daily"})
    notification_id = await service.notify_with_template(
        "lead", notifications.NotificationTemplate.PR_OPENED, "tech_lead",
        {"pr_number": 1, "pr_title": "Update search", "risk_emoji": "", "risk_level": "low",
         "author": "dev", "files_changed": 1},
    )
    assert notification_id and (await service.repo.find_by_id(notification_id))["user_id"] == "lead"


@pytest.mark.anyio
async def test_active_dnd_allows_urgent_notifications(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    service = notifications.EnhancedNotificationService()
    await service.preferences.upsert("lead", {"dnd_enabled": True})
    monkeypatch.setattr(service, "_is_dnd_time", lambda prefs: prefs.dnd_enabled)
    assert not await service.allows_optional_notification("lead", "pr_opened")
    assert await service.allows_optional_notification("lead", "recommendation_urgent", notifications.NotificationPriority.URGENT)


@pytest.mark.parametrize("start,end,at,active", [
    ("22:00", "08:00", "22:00", True),
    ("22:00", "08:00", "07:59", True),
    ("22:00", "08:00", "08:00", False),
    ("09:00", "17:00", "12:30", True),
    ("09:00", "17:00", "18:00", False),
    ("09:00", "09:00", "09:00", False),
    ("invalid", "08:00", "06:00", False),
])
def test_dnd_uses_utc_start_inclusive_end_exclusive(monkeypatch, start, end, at, active):
    class Clock(datetime):
        @classmethod
        def now(cls, tz):
            assert tz is timezone.utc
            return datetime.fromisoformat(f"2026-01-01T{at}:00+00:00")

    monkeypatch.setattr(notifications, "datetime", Clock)
    prefs = NotificationPreferences(user_id="lead", dnd_enabled=True, dnd_start_utc=start, dnd_end_utc=end)
    assert notifications.EnhancedNotificationService._is_dnd_time(prefs) is active
