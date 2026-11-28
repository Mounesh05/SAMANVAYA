"""v4 REC-15: a refused recommendation read is reported as refused, not as a server error.

``/recommendations/user/{id}`` and ``/recommendations/role/{role}`` wrapped the
authorization check in ``except Exception`` and turned its 403 into a 500.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from api.routes import recommendations

pytestmark = pytest.mark.anyio
DEVELOPER = {"employee_id": "E-DEV-1", "role": "DEVELOPER", "org_id": "O1"}


async def test_reading_another_users_recommendations_is_403_not_500():
    with pytest.raises(HTTPException) as refused:
        await recommendations.get_user_recommendations("E-OTHER-9", status="pending", current_user=DEVELOPER)
    assert refused.value.status_code == 403


async def test_own_recommendations_are_still_returned():
    with patch.object(recommendations.engine, "get_recommendations_for_user", AsyncMock(return_value=[])):
        body = await recommendations.get_user_recommendations("E-DEV-1", status="pending", current_user=DEVELOPER)
    assert body["count"] == 0


async def test_role_listing_keeps_authorization_errors():
    with patch.object(recommendations.engine, "get_recommendations_for_role", AsyncMock(return_value=[])), \
            patch.object(recommendations, "get_accessible_project_ids",
                         AsyncMock(side_effect=HTTPException(403, "Inactive account"))):
        with pytest.raises(HTTPException) as refused:
            await recommendations.get_role_recommendations("DEVELOPER", None, status="pending", current_user=DEVELOPER)
    assert refused.value.status_code == 403
