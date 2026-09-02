"""
Create First HR/Admin User - Production Mode

Run this script ONCE during deployment to bootstrap Samanvaya with the first HR admin.
After this, use the HR account to create other users via the API or UI.

PRODUCTION MODE:
- No default values
- No sample/dummy data
- All fields are required
- Password minimum 8 characters
- Email validation

Usage:
    python create_first_user.py
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime, timezone

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# MongoDB connection (update if needed)
MONGODB_URI = "mongodb://localhost:27017"
DATABASE_NAME = "samanvaya"


async def create_first_hr_user():
    """Create the first HR/Admin user to bootstrap the system."""
    
    print("\n" + "="*60)
    print(" SAMANVAYA - CREATE FIRST HR USER")
    print("="*60 + "\n")
    
    # Connect to MongoDB
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        users = db["users"]
        
        # Test connection
        await client.server_info()
        print(f"✅ Connected to MongoDB")
        print(f"   Database: {DATABASE_NAME}\n")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print(f"   Make sure MongoDB is running on {MONGODB_URI}")
        sys.exit(1)
    
    # Check if any HR user already exists
    existing_hr = await users.find_one({"role": "HR"})
    if existing_hr:
        print("⚠️  HR user already exists!")
        print(f"   Employee ID: {existing_hr['employee_id']}")
        print(f"   Email: {existing_hr['email']}")
        print(f"\n   Use this account to create other users.")
        print(f"   Or delete it from MongoDB and run this script again.\n")
        return
    
    # Get user input - NO DEFAULTS (Production Mode)
    print("Creating first HR/Admin user...")
    print("-" * 60)
    
    employee_id = ""
    while not employee_id:
        employee_id = input("Employee ID (required): ").strip()
        if not employee_id:
            print("❌ Employee ID is required!")
    
    name = ""
    while not name:
        name = input("Full Name (required): ").strip()
        if not name:
            print("❌ Full Name is required!")
    
    email = ""
    while not email:
        email = input("Email (required): ").strip()
        if not email:
            print("❌ Email is required!")
        elif "@" not in email:
            print("❌ Invalid email format!")
            email = ""
    
    password = ""
    while not password:
        password = input("Password (required, min 8 characters): ").strip()
        if not password:
            print("❌ Password is required!")
        elif len(password) < 8:
            print("❌ Password must be at least 8 characters!")
            password = ""
    
    print("-" * 60)
    print("\nCreating user with:")
    print(f"  Employee ID: {employee_id}")
    print(f"  Name: {name}")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print(f"  Role: HR")
    print(f"  Admin: Yes")
    
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n❌ Cancelled")
        return
    
    # Create HR user
    hr_user = {
        "employee_id": employee_id,
        "name": name,
        "email": email,
        "role": "HR",
        "dept": "Human Resources",
        "employee_password": pwd_context.hash(password),  # Fixed: use employee_password
        "github_username": None,
        "team_id": None,
        "is_active": True,
        "is_admin": True,
        "avatar": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        result = await users.insert_one(hr_user)
        
        print("\n" + "="*60)
        print(" ✅ SUCCESS - HR USER CREATED")
        print("="*60)
        print(f"\nEmployee ID: {employee_id}")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"MongoDB ID: {result.inserted_id}")
        print(f"\n⚠️  IMPORTANT:")
        print(f"1. Save these credentials in a secure password manager")
        print(f"2. Delete this terminal output after saving credentials")
        print(f"3. Use this account to create other users via API or UI")
        print(f"4. Do NOT share these credentials\n")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Failed to create user: {e}")
        sys.exit(1)


async def create_sample_users():
    """Sample user creation removed for production."""
    # Production mode: No sample/dummy users
    print("\n✅ Done! Use the HR account to create other users via API or UI.\n")
    return


async def main():
    """Main entry point."""
    try:
        # Create first HR user
        await create_first_hr_user()
        
        # Optionally create sample users
        await create_sample_users()
        
        print("="*60)
        print(" 🎉 SETUP COMPLETE")
        print("="*60)
        print("\nNext steps:")
        print("1. Start backend: python main.py")
        print("2. Login with your HR credentials")
        print("3. Create teams and other users via API or UI")
        print("\nAPI Documentation: http://localhost:8000/docs")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
