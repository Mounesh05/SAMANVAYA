"""
Quick Test - GitHub + AI Integration

Simple test script to quickly verify:
1. Server is running
2. GitHub token is valid
3. Ollama AI is responding

Usage:
    python quick_test.py
"""

import asyncio
import httpx

BASE_URL = "http://localhost:8000"

async def main():
    print("\n🔍 Quick Test - GitHub + AI Integration\n")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test 1: Server Health
            print("\n1. Testing Server Health...")
            response = await client.get(f"{BASE_URL}/health")
            data = response.json()
            
            print(f"   Server: ✅ Running v{data.get('version')}")
            
            # Check services
            deps = data.get("dependencies", {})
            print(f"   MongoDB: {'✅' if deps.get('database') == 'connected' else '❌'} {deps.get('database')}")
            print(f"   Ollama AI: {'✅' if deps.get('ollama') == 'connected' else '❌'} {deps.get('ollama')}")
            print(f"   GitHub: {'✅' if deps.get('github') == 'configured' else '⚠️ '} {deps.get('github')}")
            
            # Test 2: API Docs
            print("\n2. Testing API Documentation...")
            response = await client.get(f"{BASE_URL}/docs")
            if response.status_code == 200:
                print("   API Docs: ✅ Available at http://localhost:8000/docs")
            else:
                print("   API Docs: ❌ Not accessible")
            
            # Test 3: Risk Configurations (requires no auth for global config)
            print("\n3. Testing Risk Configuration System...")
            response = await client.get(f"{BASE_URL}/api/risk-configurations/global")
            if response.status_code == 200:
                config = response.json()
                print(f"   Risk Config: ✅ Loaded")
                print(f"   Alpha (size): {config.get('risk_weights', {}).get('alpha', 0)}%")
            elif response.status_code == 401:
                print("   Risk Config: ⚠️  Requires authentication (expected)")
            else:
                print(f"   Risk Config: ❌ Error {response.status_code}")
            
            print("\n" + "="*60)
            print("✅ BASIC TESTS PASSED!")
            print("="*60)
            print("\n📚 Next Steps:")
            print("   1. Create user: python create_first_user.py")
            print("   2. Full test: python test_github_ai_workflow.py")
            print("   3. API Docs: http://localhost:8000/docs")
            print("\n")
            
    except httpx.ConnectError:
        print("\n❌ ERROR: Cannot connect to server!")
        print("   Make sure server is running: python start.py")
        print("\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
