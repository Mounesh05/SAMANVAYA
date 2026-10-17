"""
Integration tests for comment routes authorization.

Tests that comment API endpoints correctly enforce dual authorization:
1. User must be the comment author (for edit/delete)
2. User must have access to the parent resource
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from repositories.comment_repository import CommentRepository
from repositories.activity_repository import ActivityRepository


def create_user(
    employee_id: str = "E001",
    role: str = "DEVELOPER",
    project_ids: list = None,
) -> dict:
    """Create a mock user dict (simulates JWT payload)."""
    return {
        "employee_id": employee_id,
        "id": employee_id,
        "name": "Test User",
        "role": role,
        "organizational_role": role,
        "project_ids": project_ids or [],
    }


# ── POST /comments/ Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAddComment:
    """Test POST /comments/ authorization."""

    async def test_user_can_comment_on_accessible_task(self):
        """User can comment on tasks in their assigned projects."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "insert") as mock_insert:
                    with patch.object(ActivityRepository, "insert") as mock_activity:
                        mock_task_repo.find_by_id = AsyncMock(return_value={
                            "id": "TASK-1", "project_id": "PRJ-A"
                        })
                        mock_project_repo.find_by_id = AsyncMock(return_value={
                            "id": "PRJ-A"
                        })
                        mock_insert.return_value = None
                        mock_activity.return_value = None
                        
                        from api.routes.comments import add_comment
                        from domain.models.comment import CommentCreate
                        
                        body = CommentCreate(
                            parent_type="task",
                            parent_id="TASK-1",
                            body="Great work!"
                        )
                        
                        result = await add_comment(body, user=user)
                        assert result["parent_id"] == "TASK-1"
                        assert result["author_id"] == "E001"

    async def test_user_cannot_comment_on_inaccessible_task(self):
        """User cannot comment on tasks in unassigned projects."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={
                    "id": "TASK-2", "project_id": "PRJ-B"
                })
                mock_project_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-B"
                })
                
                from api.routes.comments import add_comment
                from domain.models.comment import CommentCreate
                
                body = CommentCreate(
                    parent_type="task",
                    parent_id="TASK-2",
                    body="Trying to comment"
                )
                
                with pytest.raises(HTTPException) as exc_info:
                    await add_comment(body, user=user)
                
                assert exc_info.value.status_code == 403

    async def test_user_can_comment_on_accessible_story(self):
        """User can comment on stories in their assigned projects."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._story_repo") as mock_story_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "insert") as mock_insert:
                    with patch.object(ActivityRepository, "insert") as mock_activity:
                        mock_story_repo.find_by_id = AsyncMock(return_value={
                            "id": "STORY-1", "project_id": "PRJ-A"
                        })
                        mock_project_repo.find_by_id = AsyncMock(return_value={
                            "id": "PRJ-A"
                        })
                        mock_insert.return_value = None
                        mock_activity.return_value = None
                        
                        from api.routes.comments import add_comment
                        from domain.models.comment import CommentCreate
                        
                        body = CommentCreate(
                            parent_type="story",
                            parent_id="STORY-1",
                            body="Good user story!"
                        )
                        
                        result = await add_comment(body, user=user)
                        assert result["parent_type"] == "story"

    async def test_invalid_parent_type_rejected(self):
        """Invalid parent_type is rejected."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch.object(CommentRepository, "insert") as mock_insert:
            with patch.object(ActivityRepository, "insert") as mock_activity:
                mock_insert.return_value = None
                mock_activity.return_value = None
                
                from api.routes.comments import add_comment
                from domain.models.comment import CommentCreate
                
                body = CommentCreate(
                    parent_type="invalid",
                    parent_id="SOME-ID",
                    body="Test"
                )
                
                with pytest.raises(HTTPException) as exc_info:
                    await add_comment(body, user=user)
                
                assert exc_info.value.status_code == 400


# ── GET /comments/{parent_type}/{parent_id} Tests ─────────────────────────


@pytest.mark.asyncio
class TestListComments:
    """Test GET /comments/{parent_type}/{parent_id} authorization."""

    async def test_user_can_list_comments_on_accessible_task(self):
        """User can read comments on tasks they have access to."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "find_by_parent") as mock_find:
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-1", "project_id": "PRJ-A"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-A"
                    })
                    mock_find.return_value = [
                        {"id": "CMT-1", "body": "Comment 1"},
                        {"id": "CMT-2", "body": "Comment 2"}
                    ]
                    
                    from api.routes.comments import list_comments
                    
                    result = await list_comments("task", "TASK-1", user=user)
                    assert len(result) == 2

    async def test_user_cannot_list_comments_on_inaccessible_task(self):
        """User cannot read comments on tasks they don't have access to."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={
                    "id": "TASK-2", "project_id": "PRJ-B"
                })
                mock_project_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-B"
                })
                
                from api.routes.comments import list_comments
                
                with pytest.raises(HTTPException) as exc_info:
                    await list_comments("task", "TASK-2", user=user)
                
                assert exc_info.value.status_code == 403


# ── PUT /comments/{comment_id} Tests ──────────────────────────────────────


@pytest.mark.asyncio
class TestEditComment:
    """Test PUT /comments/{comment_id} dual authorization."""

    async def test_author_can_edit_own_comment_with_access(self):
        """Comment author can edit if they still have access to parent."""
        user = create_user(employee_id="E001", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "find_by_id") as mock_find:
                    with patch.object(CommentRepository, "update") as mock_update:
                        mock_find.return_value = {
                            "id": "CMT-1",
                            "author_id": "E001",
                            "parent_type": "task",
                            "parent_id": "TASK-1",
                            "body": "Old comment"
                        }
                        mock_task_repo.find_by_id = AsyncMock(return_value={
                            "id": "TASK-1", "project_id": "PRJ-A"
                        })
                        mock_project_repo.find_by_id = AsyncMock(return_value={
                            "id": "PRJ-A"
                        })
                        mock_update.return_value = None
                        
                        from api.routes.comments import edit_comment
                        from domain.models.comment import CommentUpdate
                        
                        body = CommentUpdate(body="Updated comment")
                        result = await edit_comment("CMT-1", body, user=user)
                        assert result["body"] == "Updated comment"

    async def test_non_author_cannot_edit_comment(self):
        """Non-author cannot edit comment even with parent access."""
        user = create_user(employee_id="E002", project_ids=["PRJ-A"])
        
        with patch.object(CommentRepository, "find_by_id") as mock_find:
            mock_find.return_value = {
                "id": "CMT-1",
                "author_id": "E001",  # Different author
                "parent_type": "task",
                "parent_id": "TASK-1",
                "body": "Someone else's comment"
            }
            
            from api.routes.comments import edit_comment
            from domain.models.comment import CommentUpdate
            
            body = CommentUpdate(body="Trying to edit")
            
            with pytest.raises(HTTPException) as exc_info:
                await edit_comment("CMT-1", body, user=user)
            
            assert exc_info.value.status_code == 403
            assert "own comments" in str(exc_info.value.detail)

    async def test_author_cannot_edit_without_parent_access(self):
        """Author cannot edit if they lost access to parent resource."""
        user = create_user(employee_id="E001", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "find_by_id") as mock_find:
                    mock_find.return_value = {
                        "id": "CMT-1",
                        "author_id": "E001",
                        "parent_type": "task",
                        "parent_id": "TASK-2",  # In different project
                        "body": "Old comment"
                    }
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-2", "project_id": "PRJ-B"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-B"
                    })
                    
                    from api.routes.comments import edit_comment
                    from domain.models.comment import CommentUpdate
                    
                    body = CommentUpdate(body="Trying to edit")
                    
                    with pytest.raises(HTTPException) as exc_info:
                        await edit_comment("CMT-1", body, user=user)
                    
                    assert exc_info.value.status_code == 403


# ── DELETE /comments/{comment_id} Tests ───────────────────────────────────


@pytest.mark.asyncio
class TestDeleteComment:
    """Test DELETE /comments/{comment_id} dual authorization."""

    async def test_author_can_delete_own_comment_with_access(self):
        """Comment author can delete if they still have access to parent."""
        user = create_user(employee_id="E001", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "find_by_id") as mock_find:
                    with patch.object(CommentRepository, "delete") as mock_delete:
                        mock_find.return_value = {
                            "id": "CMT-1",
                            "author_id": "E001",
                            "parent_type": "task",
                            "parent_id": "TASK-1"
                        }
                        mock_task_repo.find_by_id = AsyncMock(return_value={
                            "id": "TASK-1", "project_id": "PRJ-A"
                        })
                        mock_project_repo.find_by_id = AsyncMock(return_value={
                            "id": "PRJ-A"
                        })
                        mock_delete.return_value = None
                        
                        from api.routes.comments import delete_comment
                        
                        # Should not raise
                        await delete_comment("CMT-1", user=user)

    async def test_non_author_cannot_delete_comment(self):
        """Non-author cannot delete comment."""
        user = create_user(employee_id="E002", project_ids=["PRJ-A"])
        
        with patch.object(CommentRepository, "find_by_id") as mock_find:
            mock_find.return_value = {
                "id": "CMT-1",
                "author_id": "E001",  # Different author
                "parent_type": "task",
                "parent_id": "TASK-1"
            }
            
            from api.routes.comments import delete_comment
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_comment("CMT-1", user=user)
            
            assert exc_info.value.status_code == 403
            assert "own comments" in str(exc_info.value.detail)

    async def test_author_cannot_delete_without_parent_access(self):
        """Author cannot delete if they lost access to parent resource."""
        user = create_user(employee_id="E001", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(CommentRepository, "find_by_id") as mock_find:
                    mock_find.return_value = {
                        "id": "CMT-1",
                        "author_id": "E001",
                        "parent_type": "task",
                        "parent_id": "TASK-2"  # In different project
                    }
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-2", "project_id": "PRJ-B"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-B"
                    })
                    
                    from api.routes.comments import delete_comment
                    
                    with pytest.raises(HTTPException) as exc_info:
                        await delete_comment("CMT-1", user=user)
                    
                    assert exc_info.value.status_code == 403


# ── Comment Not Found Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
class TestCommentNotFound:
    """Test 404 handling for missing comments."""

    async def test_missing_comment_returns_404(self):
        """Non-existent comment returns 404."""
        user = create_user(employee_id="E001")
        
        with patch.object(CommentRepository, "find_by_id") as mock_find:
            mock_find.return_value = None
            
            from api.routes.comments import edit_comment
            from domain.models.comment import CommentUpdate
            
            body = CommentUpdate(body="Test")
            
            with pytest.raises(HTTPException) as exc_info:
                await edit_comment("CMT-MISSING", body, user=user)
            
            assert exc_info.value.status_code == 404
