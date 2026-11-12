"""
CR-001 drift guard: the frontend's permission names must match the backend enum.

The frontend reads each user's permissions from /api/auth/me, so it no longer
holds a role matrix; it only names permissions. If a permission is added,
renamed or removed on one side only, this test fails.
"""

import re
from pathlib import Path

from core.permissions import Permission

FRONTEND_PERMISSIONS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "auth" / "permissions.js"


def _frontend_permission_names():
    source = FRONTEND_PERMISSIONS.read_text(encoding="utf-8")
    block = source.split("export const PERMISSIONS = Object.freeze({", 1)[1].split("});", 1)[0]
    pairs = re.findall(r"^\s*([A-Z_]+):\s*'([A-Z_]+)'", block, re.M)
    assert pairs, "Could not read PERMISSIONS from permissions.js"
    for key, value in pairs:
        assert key == value, f"Frontend key {key} maps to a different value {value}"
    return {value for _, value in pairs}


def test_frontend_and_backend_permission_names_match():
    backend = {permission.value for permission in Permission}
    frontend = _frontend_permission_names()
    assert frontend - backend == set(), f"Frontend-only permissions: {sorted(frontend - backend)}"
    assert backend - frontend == set(), f"Backend-only permissions: {sorted(backend - frontend)}"


def test_frontend_keeps_no_role_matrix():
    source = FRONTEND_PERMISSIONS.read_text(encoding="utf-8")
    assert "ROLE_PERMISSIONS" not in source


ROLE_FIXTURE = FRONTEND_PERMISSIONS.parents[1] / "tests" / "fixtures" / "rolePermissions.json"


def test_frontend_test_fixture_matches_backend_role_matrix():
    """Frontend tests use the permission lists /api/auth/me would return.
    Regenerate the fixture whenever ROLE_PERMISSIONS changes."""
    import json
    from core.permissions import ADMIN_PERMISSIONS, OrganizationalRole, ROLE_PERMISSIONS
    fixture = json.loads(ROLE_FIXTURE.read_text(encoding="utf-8"))
    expected = {role.value: sorted(p.value for p in ROLE_PERMISSIONS[role]) for role in OrganizationalRole}
    expected["_ADMIN"] = sorted(p.value for p in ADMIN_PERMISSIONS)
    assert fixture == expected, "Regenerate frontend/src/tests/fixtures/rolePermissions.json from ROLE_PERMISSIONS"
