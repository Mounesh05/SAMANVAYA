import pytest

from domain.services.sprint_service import SprintService


class FakeSprintRepository:
    async def find_by_id(self, _sprint_id):
        return {
            "id": "SPR-1",
            "name": "Sprint 1",
            "project_id": "PROJECT-1",
            "goal": "Test",
            "start_date": "2026-10-05",
            "end_date": "2026-10-12",
            "status": "planning",
        }


class FakeStoryRepository:
    async def find_by_sprint(self, _sprint_id):
        return []


class FakeTaskRepository:
    async def find_by_sprint(self, _sprint_id):
        return [
            {"id": "TASK-1", "status": "done", "story_id": None},
            {"id": "TASK-2", "status": "todo", "story_id": None},
        ]


@pytest.mark.anyio
async def test_sprint_health_counts_standalone_tasks_as_work_items():
    service = SprintService()
    service.sprint_repo = FakeSprintRepository()
    service.story_repo = FakeStoryRepository()
    service.task_repo = FakeTaskRepository()

    health = await service.calculate_sprint_health("SPR-1")

    assert health["total_stories"] == 2
    assert health["completed_stories"] == 1
    assert health["total_points"] == 2
    assert health["completed_points"] == 1
    assert health["completion_pct"] == 50.0
