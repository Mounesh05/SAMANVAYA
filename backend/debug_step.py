import sys
import time

def log(msg):
    print(f"[{time.strftime('%X')}] {msg}", flush=True)

log("Starting debug...")
log("Importing os...")
import os
os.chdir('c:/Users/sushi/OneDrive/Desktop/Samanvaya/backend')
sys.path.insert(0, '.')

log("Importing pydantic...")
from pydantic import BaseModel, EmailStr

log("Importing core.security...")
from core.security import hash_password, create_access_token

log("Importing core.database...")
from core.database import col

log("Importing api.routes.admin...")
from api.routes.admin import verify_admin_access, CompanyProvisionRequest, LeaderAssignment, provision_company_with_leaders

log("All imported! Starting test...")
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

async def test():
    log("Creating provision request...")
    prov_req = CompanyProvisionRequest(
        code="VAL",
        name="Valence",
        company_password="Password123",
        ceo=LeaderAssignment(name="CEO", email="ceo@val.io", employee_id="EMP-CEO-1", password="Pwd"),
        hr=LeaderAssignment(name="HR", email="hr@val.io", employee_id="EMP-HR-1", password="Pwd")
    )
    with patch("api.routes.admin.col") as mock_col:
        m = MagicMock()
        m.find_one = AsyncMock(return_value=None)
        m.count_documents = AsyncMock(return_value=1)
        m.insert_one = AsyncMock()
        mock_col.return_value = m

        log("Calling provision_company_with_leaders...")
        res = await provision_company_with_leaders(prov_req, {"name": "Admin", "role": "SUPERADMIN"})
        log(f"Result: {res['message']}")

asyncio.run(test())
log("COMPLETE!")
