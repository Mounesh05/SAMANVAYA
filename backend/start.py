#!/usr/bin/env python3
"""
Start the Samanvaya backend server.
Performs health checks and starts uvicorn server.
"""

import asyncio
import sys
import os
from pathlib import Path

# Ensure UTF-8 output in Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.config import settings
from core.database import col

async def check_dependencies():
    """Check system dependencies before starting."""
    print("🔍 Checking dependencies...")
    
    # Check environment file
    env_file = backend_dir / ".env"
    if not env_file.exists():
        print("❌ .env file not found!")
        print("   Copy .env.example to .env and configure settings")
        return False
    
    # Check SECRET_KEY
    if not settings.SECRET_KEY or settings.SECRET_KEY == "change-me-to-a-random-32-byte-hex-string":
        print("❌ SECRET_KEY not configured!")
        print("   Set SECRET_KEY in .env file")
        return False
    
    print("   ✅ Environment configuration OK")
    
    # Check database connection
    try:
        await col("users").count_documents({})
        print("   ✅ MongoDB connection OK")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print(f"   Check MONGO_URI: {settings.MONGO_URI}")
        return False
    
    # Check Ollama (optional)
    try:
        from agents.llm_provider import check_ollama_connection
        if check_ollama_connection():
            print("   ✅ Ollama connection OK")
        else:
            print("   ⚠️  Ollama not available (AI features disabled)")
    except Exception:
        print("   ⚠️  Could not check Ollama connection")
    
    # Check GitHub token (optional)
    if settings.GITHUB_TOKEN:
        try:
            from integrations.github.client import GitHubClient
            client = GitHubClient()
            if await client.check_token_validity():
                print("   ✅ GitHub token valid")
            else:
                print("   ❌ GitHub token invalid")
        except Exception:
            print("   ⚠️  Could not validate GitHub token")
    else:
        print("   ⚠️  GitHub token not configured (GitHub features disabled)")
    
    return True

def main():
    """Main entry point."""
    print("🚀 Starting Samanvaya Backend")
    print("=" * 50)
    
    # Check dependencies
    dependencies_ok = asyncio.run(check_dependencies())
    
    if not dependencies_ok:
        print("\n❌ Dependency check failed!")
        print("Fix the issues above and try again.")
        sys.exit(1)
    
    print("\n✅ All checks passed! Starting server...\n")
    
    # Start uvicorn server
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable hot reload in development
        log_level="info",
    )

if __name__ == "__main__":
    main()
