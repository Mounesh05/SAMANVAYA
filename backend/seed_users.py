import asyncio
from core.security import hash_password
from repositories.user_repository import UserRepository

async def seed_users():
    user_repo = UserRepository()
    
    print("Checking users in database...")
    existing_users = await user_repo.find_all({})
    hashed_pwd = hash_password("password123")
    
    for u in existing_users:
        emp_id = u.get("employee_id")
        email = u.get("email")
        role = u.get("role")
        await user_repo.update(
            {"employee_id": emp_id},
            {
                "employee_password": hashed_pwd,
                "organisation_password": hashed_pwd,
                "is_active": True,
            }
        )
        print(f"Set password123 for: {email} | ID: {emp_id} | Role: {role}")

if __name__ == "__main__":
    asyncio.run(seed_users())
