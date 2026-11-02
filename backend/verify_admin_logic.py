import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
os.chdir(str(backend_dir))
sys.path.insert(0, str(backend_dir))

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

async def main():
    print("1. Loading admin modules...")
    from api.routes.admin import (
        verify_admin_access,
        CompanyProvisionRequest,
        LeaderAssignment,
        provision_company_with_leaders,
    )
    from core.security import create_access_token
    print("   Modules loaded successfully!")

    print("2. Verifying admin master secret...")
    req = MagicMock()
    req.query_params = {}
    auth_master = await verify_admin_access(req, authorization=None, x_admin_secret="samanvaya-admin-2026")
    assert auth_master["authenticated"] is True
    print("   Master secret auth: PASS")

    print("3. Verifying CEO Bearer token...")
    tok = create_access_token({"employee_id": "EMP-CEO-001", "role": "CEO", "name": "Alexander Sterling", "email": "ceo@samanvaya.io", "is_admin": True})
    auth_ceo = await verify_admin_access(req, authorization=f"Bearer {tok}", x_admin_secret=None)
    assert auth_ceo["authenticated"] is True
    print("   CEO Bearer token auth: PASS")

    print("4. Testing Company Provisioning Logic (Mock DB)...")
    with patch("api.routes.admin.col") as mock_col:
        mock_db = {}
        def get_col(name):
            if name not in mock_db:
                m = MagicMock()
                m.find_one = AsyncMock(return_value=None)
                m.count_documents = AsyncMock(return_value=1)
                m.insert_one = AsyncMock()
                mock_db[name] = m
            return mock_db[name]
        mock_col.side_effect = get_col

        prov_req = CompanyProvisionRequest(
            code="NEX",
            name="Nexus Cybernetics",
            domain="nexus.io",
            company_password="Nexus@org123",
            ceo=LeaderAssignment(name="Dr. Dev Sharma", email="dev@nexus.io", employee_id="EMP-CEO-NEX-001", password="Emp@ceo123"),
            hr=LeaderAssignment(name="Ritu Verma", email="ritu@nexus.io", employee_id="EMP-HR-NEX-001", password="Emp@hr123")
        )
        res = await provision_company_with_leaders(prov_req, {"name": "SuperAdmin", "role": "SUPERADMIN"})
        assert res["success"] is True
        assert res["company"]["code"] == "NEX"
        assert res["assigned_leaders"]["ceo"]["employee_id"] == "EMP-CEO-NEX-001"
        assert res["assigned_leaders"]["hr"]["employee_id"] == "EMP-HR-NEX-001"
        print(f"   Provisioning result: {res['message']}")
        print("   Company, CEO, and HR atomically registered: PASS")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
