"""
Tests for the Workflow Service.
"""

import pytest
from domain.services.workflow_service import WorkflowService
from domain.models.workflow import WORKFLOWS


class TestWorkflowTransitions:
    """Test workflow state transition validation."""

    @pytest.fixture
    def service(self):
        return WorkflowService()

    def test_valid_task_transitions(self, service):
        # todo -> in_progress is valid
        assert service.validate_transition("todo", "in_progress", "task") is True
        # in_progress -> review is valid
        assert service.validate_transition("in_progress", "review", "task") is True
        # review -> done is valid
        assert service.validate_transition("review", "done", "task") is True

    def test_invalid_task_transitions(self, service):
        # todo -> done is invalid (must go through in_progress)
        assert service.validate_transition("todo", "done", "task") is False
        # done -> todo is invalid (can't go backwards)
        assert service.validate_transition("done", "todo", "task") is False

    def test_valid_story_transitions(self, service):
        assert service.validate_transition("todo", "in_progress", "story") is True
        assert service.validate_transition("in_progress", "review", "story") is True
        assert service.validate_transition("review", "done", "story") is True

    def test_invalid_story_transitions(self, service):
        assert service.validate_transition("todo", "done", "story") is False
        assert service.validate_transition("done", "todo", "story") is False

    def test_get_allowed_transitions(self, service):
        allowed = service.get_allowed_transitions("todo", "task")
        assert "in_progress" in allowed
        assert "done" not in allowed

    def test_unknown_workflow_returns_empty(self, service):
        allowed = service.get_allowed_transitions("todo", "unknown_type")
        assert allowed == []

    def test_all_task_statuses_exist_in_workflow(self):
        task_workflow = WORKFLOWS.get("task", {})
        assert len(task_workflow) > 0
        # Check that common statuses exist
        assert "todo" in task_workflow
        assert "in_progress" in task_workflow
        assert "review" in task_workflow
        assert "done" in task_workflow


class TestWorkflowModel:
    """Test workflow model definitions."""

    def test_task_workflow_has_required_statuses(self):
        task_wf = WORKFLOWS.get("task", {})
        required = {"todo", "in_progress", "review", "done"}
        assert required.issubset(set(task_wf.keys()))

    def test_story_workflow_has_required_statuses(self):
        story_wf = WORKFLOWS.get("story", {})
        required = {"todo", "in_progress", "review", "done"}
        assert required.issubset(set(story_wf.keys()))
