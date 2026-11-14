"""
Create the first accounts of a production install (CR-012).

Creates two separate accounts, using existing roles only:
- the Chief Executive (CEO role, no admin rights);
- the platform administrator (DevOps role with admin rights).

Run once, after deployment, before anyone else signs in:

    python create_first_user.py

The script uses the configured database (MONGO_URI / DB_NAME), asks for
passwords without showing them, applies the project's password rules, never
prints a password, and refuses to run when any account already exists.
"""

import asyncio
import getpass
import sys

from domain.services.first_accounts import FirstAccount, build_accounts, validate_pair


def _ask(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  This field is required.")


def _ask_password(prompt: str) -> str:
    while True:
        first = getpass.getpass(prompt)
        if first and first == getpass.getpass("  Repeat to confirm: "):
            return first
        print("  The passwords did not match (or were empty). Try again.")


def ask_account(label: str) -> FirstAccount:
    print(f"\n{label}")
    print("-" * len(label))
    return FirstAccount(
        employee_id=_ask("  Employee ID: "),
        name=_ask("  Full name: "),
        email=_ask("  Email: "),
        organisation_password=_ask_password("  Organisation password: "),
        employee_password=_ask_password("  Employee password: "),
    )


def summary(records: list) -> str:
    """What will be created, without any password or hash."""
    lines = []
    for record in records:
        lines.append(f"  {record['employee_id']:<14} {record['name']:<24} {record['email']:<32} "
                     f"role={record['role']} admin={'yes' if record['is_admin'] else 'no'}")
    return "\n".join(lines)


async def create_first_accounts(db, ceo: FirstAccount, admin: FirstAccount, org_id: str = "ORG001") -> list:
    """Insert the pair into `db`. Raises RuntimeError when accounts exist or insertion fails."""
    users = db["users"]
    if await users.count_documents({}) > 0:
        raise RuntimeError("Accounts already exist. This script only sets up a new, empty install.")
    validate_pair(ceo, admin)
    records = build_accounts(ceo, admin, created_by="create_first_user", org_id=org_id)
    await users.create_index("employee_id", unique=True)
    await users.create_index("email", unique=True)
    try:
        await users.insert_many(records, ordered=True)
    except Exception as error:
        await users.delete_many({"employee_id": {"$in": [r["employee_id"] for r in records]},
                                 "created_by": "create_first_user"})
        raise RuntimeError(f"Could not create both accounts; nothing was created ({type(error).__name__})")
    return records


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from core.config import settings

    print("\nSAMANVAYA - create the first accounts")
    print(f"Database: {settings.DB_NAME}\n")
    client = AsyncIOMotorClient(settings.MONGO_URI)
    try:
        db = client[settings.DB_NAME]
        if await db["users"].count_documents({}) > 0:
            print("Accounts already exist. Nothing was changed.")
            return 1
        org_id = input(f"Organisation ID [{settings.DEFAULT_ORG_ID}]: ").strip() or settings.DEFAULT_ORG_ID
        ceo = ask_account("Chief Executive (no admin rights)")
        admin = ask_account("Platform administrator (DevOps role, admin rights)")
        try:
            validate_pair(ceo, admin)
        except ValueError as error:
            print(f"\nNot created: {error}")
            return 1
        print("\nAbout to create:")
        print(f"Organisation: {org_id}")
        print(summary(build_accounts(ceo, admin, created_by="create_first_user", org_id=org_id)))
        if input("\nProceed? (y/n): ").strip().lower() != "y":
            print("Cancelled. Nothing was changed.")
            return 1
        records = await create_first_accounts(db, ceo, admin, org_id)
        print("\nCreated:")
        print(summary(records))
        print("\nKeep the passwords in your password manager. Sign in as the platform administrator to "
              "create the other employees; account changes then need a second approver (CR-010).")
        return 0
    except RuntimeError as error:
        print(f"\nNot created: {error}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was changed.")
        sys.exit(1)
