"""
CR-012: a new install starts with a separate Chief Executive (no admin rights)
and platform administrator (DevOps role with admin rights), from both the
development setup and the production bootstrap script.
"""

import pytest
from fastapi import HTTPException

from core.security import verify_password
from domain.services.first_accounts import FirstAccount, build_accounts, validate_pair

GOOD = {"ceo": ("Ceo-Org-Pass1!", "Ceo-Emp-Pass2!"), "admin": ("Adm-Org-Pass3!", "Adm-Emp-Pass4!")}


def account(who="ceo", **overrides):
    org, emp = GOOD[who]
    values = dict(employee_id=f"{who.upper()}-1", name=who.title(), email=f"{who}@samanvaya.com",
                  organisation_password=org, employee_password=emp)
    values.update(overrides)
    return FirstAccount(**values)


class TestPair:
    def test_records_separate_ceo_and_admin(self):
        ceo, admin = build_accounts(account("ceo"), account("admin"), created_by="t", org_id="ORG001")
        assert ceo["org_id"] == admin["org_id"] == "ORG001"
        assert (ceo["role"], ceo["is_admin"]) == ("CEO", False)
        assert (admin["role"], admin["is_admin"]) == ("DEVOPS", True)
        assert verify_password("Adm-Emp-Pass4!", admin["employee_password"])
        assert "Adm-Emp-Pass4!" not in str(admin)

    @pytest.mark.parametrize("ceo, admin, message", [
        (account("ceo", employee_password="weak"), account("admin"), "Chief Executive employee password"),
        (account("ceo"), account("admin", organisation_password="Adm-Emp-Pass4!"), "must be different"),
        (account("ceo"), account("admin", email="ceo@samanvaya.com"), "different email"),
        (account("ceo"), account("admin", employee_id="ceo-1"), "different employee IDs"),
        (account("ceo"), account("admin", employee_password="Ceo-Emp-Pass2!"), "share a password"),
        (account("ceo", name=" "), account("admin"), "name is required"),
    ])
    def test_unacceptable_pairs(self, ceo, admin, message):
        with pytest.raises(ValueError) as error:
            validate_pair(ceo, admin)
        assert message in str(error.value)


# ── Development first-run setup ─────────────────────────────────────────────

def payload(**overrides):
    from api.routes import setup
    values = {
        "setup_secret": "right-secret",
        "ceo": {"email": "ceo@samanvaya.com", "organisation_password": GOOD["ceo"][0], "employee_password": GOOD["ceo"][1]},
        "admin": {"email": "it@samanvaya.com", "organisation_password": GOOD["admin"][0], "employee_password": GOOD["admin"][1]},
    }
    values.update(overrides)
    return setup.SetupRequest(**values)


@pytest.fixture
def dev_setup(mock_db, monkeypatch):
    from api.routes import setup
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr(setup.settings, "DEMO_SETUP_SECRET", "right-secret")
    monkeypatch.setattr(type(setup.settings), "is_development", lambda self: True)
    return mock_db


class TestSetup:
    @pytest.mark.anyio
    async def test_setup_creates_exactly_the_two_accounts(self, dev_setup):
        from api.routes import setup
        result = await setup.initialize_demo_admin(payload())
        assert "platform administrator" in result.reason
        users = {u["employee_id"]: u async for u in dev_setup.users.find({})}
        assert set(users) == {"DEMO-CEO", "DEMO-ADMIN"}
        assert users["DEMO-CEO"]["is_admin"] is False and users["DEMO-CEO"]["role"] == "CEO"
        assert users["DEMO-ADMIN"]["is_admin"] is True and users["DEMO-ADMIN"]["role"] == "DEVOPS"
        assert {u["org_id"] for u in users.values()} == {"ORG001"}  # E2E finding: organisation recorded

    @pytest.mark.anyio
    async def test_a_weak_password_creates_nothing(self, dev_setup):
        from api.routes import setup
        bad = {"email": "it@samanvaya.com", "organisation_password": "short", "employee_password": GOOD["admin"][1]}
        with pytest.raises(HTTPException) as error:
            await setup.initialize_demo_admin(payload(admin=bad))
        assert error.value.status_code == 422
        assert await dev_setup.users.count_documents({}) == 0

    @pytest.mark.anyio
    async def test_a_second_run_is_refused(self, dev_setup):
        from api.routes import setup
        await setup.initialize_demo_admin(payload())
        with pytest.raises(HTTPException) as error:
            await setup.initialize_demo_admin(payload())
        assert error.value.status_code == 409
        assert await dev_setup.users.count_documents({}) == 2

    @pytest.mark.anyio
    async def test_setup_is_unavailable_outside_development(self, dev_setup, monkeypatch):
        from api.routes import setup
        monkeypatch.setattr(type(setup.settings), "is_development", lambda self: False)
        with pytest.raises(HTTPException) as error:
            await setup.initialize_demo_admin(payload())
        assert error.value.status_code == 404


# ── Production bootstrap script ─────────────────────────────────────────────

class TestBootstrapScript:
    @pytest.mark.anyio
    async def test_script_creates_the_pair_and_never_prints_passwords(self, mock_db):
        import create_first_user as script
        records = await script.create_first_accounts(mock_db, account("ceo"), account("admin"))
        text = script.summary(records)
        assert "admin=yes" in text and "admin=no" in text
        assert not any(p in text for pair in GOOD.values() for p in pair)
        assert "$2" not in text and "password" not in text.lower()  # no hashes either
        assert await mock_db.users.count_documents({}) == 2

    @pytest.mark.anyio
    async def test_script_refuses_an_install_with_accounts(self, mock_db):
        import create_first_user as script
        await mock_db.users.insert_one({"employee_id": "X"})
        with pytest.raises(RuntimeError):
            await script.create_first_accounts(mock_db, account("ceo"), account("admin"))
        assert await mock_db.users.count_documents({}) == 1

    def test_script_reads_passwords_hidden_and_uses_configured_database(self):
        import inspect

        import create_first_user as script
        source = inspect.getsource(script)
        assert "getpass.getpass" in source and "settings.MONGO_URI" in source
        assert "localhost:27017" not in source
