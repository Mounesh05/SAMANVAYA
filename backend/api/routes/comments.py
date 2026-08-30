"""
Comments API endpoints.
Supports comments on tasks, stories, and PRs.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from core.dependencies import get_current_user
from domain.models.comment import CommentCreate, CommentUpdate, Comment
from repositories.comment_repository import CommentRepository
from repositories.activity_repository import ActivityRepository

router = APIRouter()
comment_repo = CommentRepository()
activity_repo = ActivityRepository()


@router.post("/", response_model=Comment, status_code=201)
async def add_comment(
    body: CommentCreate,
    user: dict = Depends(get_current_user),
):
    """Add a comment to a task, story, or PR."""
    now = datetime.now(timezone.utc).isoformat()
    comment = {
        "id": f"CMT-{uuid.uuid4().hex[:8].upper()}",
        "parent_type": body.parent_type,
        "parent_id": body.parent_id,
        "author_id": user.get("employee_id", user.get("id", "")),
        "author_name": user.get("name", "Unknown"),
        "body": body.body,
        "created_at": now,
        "edited_at": None,
    }

    await comment_repo.insert(comment)

    # Log activity
    await activity_repo.insert({
        "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
        "event_type": "comment_added",
        "item_type": body.parent_type,
        "item_id": body.parent_id,
        "actor_id": comment["author_id"],
        "actor_name": comment["author_name"],
        "summary": f"{comment['author_name']} commented on {body.parent_type} {body.parent_id}",
        "details": {"comment_id": comment["id"], "preview": body.body[:100]},
        "created_at": now,
    })

    return comment


@router.get("/{parent_type}/{parent_id}", response_model=list[Comment])
async def list_comments(
    parent_type: str,
    parent_id: str,
    user: dict = Depends(get_current_user),
):
    """List all comments on a task, story, or PR."""
    if parent_type not in ("task", "story", "pr"):
        raise HTTPException(
            status_code=400, detail="parent_type must be 'task', 'story', or 'pr'"
        )
    return await comment_repo.find_by_parent(parent_type, parent_id)


@router.put("/{comment_id}", response_model=Comment)
async def edit_comment(
    comment_id: str,
    body: CommentUpdate,
    user: dict = Depends(get_current_user),
):
    """Edit a comment. Only the original author can edit."""
    comment = await comment_repo.find_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user_id = user.get("employee_id", user.get("id", ""))
    if comment["author_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")

    now = datetime.now(timezone.utc).isoformat()
    await comment_repo.update(
        {"id": comment_id},
        {"body": body.body, "edited_at": now},
    )
    return {**comment, "body": body.body, "edited_at": now}


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a comment. Only the original author can delete."""
    comment = await comment_repo.find_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user_id = user.get("employee_id", user.get("id", ""))
    if comment["author_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    await comment_repo.delete({"id": comment_id})
