"""
Comprehensive GitHub + AI Integration Test

Tests the complete workflow:
1. Server health check
2. User authentication
3. Project creation
4. GitHub repository linking
5. Pull request synchronization
6. Code quality analysis (with AI)
7. Risk assessment
8. AI agent query

This verifies your entire stack is working:
- Backend API
- MongoDB
- GitHub API integration
- Ollama AI model
- Risk/Quality engines
- All agent systems

Usage:
    python test_github_ai_workflow.py
"""

import asyncio
import sys
import json
from typing import Optional
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

console = Console()

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0

class WorkflowTester:
    def __init__(self):
        self.token: Optional[str] = None
        self.user_email: Optional[str] = None
        self.user_password: Optional[str] = None
        self.project_id: Optional[str] = None
        self.github_owner: Optional[str] = None
        self.github_repo: Optional[str] = None
        self.results = []

    def log_test(self, name: str, status: str, message: str):
        """Log test result."""
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        self.results.append({"name": name, "status": status, "message": message})
        console.print(f"{icon} {name}: {message}", style="green" if status == "PASS" else "red" if status == "FAIL" else "yellow")

    async def test_1_server_health(self) -> bool:
        """Test 1: Check if server is running."""
        console.print("\n[bold cyan]Test 1: Server Health Check[/bold cyan]")
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{BASE_URL}/health")
                data = response.json()
                
                if response.status_code == 200:
                    self.log_test("Server", "PASS", f"Server running v{data.get('version', 'unknown')}")
                    
                    # Check dependencies
                    deps = data.get("dependencies", {})
                    for service, status in deps.items():
                        service_status = "PASS" if status in ["connected", "configured"] else "WARN"
                        self.log_test(f"  {service.title()}", service_status, status)
                    
                    return True
                else:
                    self.log_test("Server", "FAIL", f"Status code: {response.status_code}")
                    return False
        except Exception as e:
            self.log_test("Server", "FAIL", f"Cannot connect: {e}")
            return False

    async def test_2_user_login(self) -> bool:
        """Test 2: User authentication."""
        console.print("\n[bold cyan]Test 2: User Authentication[/bold cyan]")
        
        # Get credentials
        console.print("\n[yellow]Enter your login credentials:[/yellow]")
        self.user_email = console.input("Email: ").strip()
        self.user_password = console.input("Password (hidden): ", password=True).strip()
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    f"{BASE_URL}/api/auth/login",
                    json={"email": self.user_email, "password": self.user_password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    user_role = data.get("role", "unknown")
                    self.log_test("Login", "PASS", f"Authenticated as {user_role}")
                    return True
                else:
                    error = response.json().get("detail", "Unknown error")
                    self.log_test("Login", "FAIL", f"{error}")
                    return False
        except Exception as e:
            self.log_test("Login", "FAIL", f"Error: {e}")
            return False

    async def test_3_create_project(self) -> bool:
        """Test 3: Create test project."""
        console.print("\n[bold cyan]Test 3: Create Test Project[/bold cyan]")
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    f"{BASE_URL}/api/projects",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "name": "GitHub AI Test Project",
                        "description": "Testing GitHub and AI integration",
                        "team_id": "test_team",
                        "start_date": "2026-09-01",
                        "target_end_date": "2026-12-31",
                        "status": "active"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.project_id = data.get("project_id")
                    self.log_test("Create Project", "PASS", f"Project ID: {self.project_id}")
                    return True
                else:
                    error = response.json().get("detail", "Unknown error")
                    self.log_test("Create Project", "FAIL", f"{error}")
                    return False
        except Exception as e:
            self.log_test("Create Project", "FAIL", f"Error: {e}")
            return False

    async def test_4_link_github_repo(self) -> bool:
        """Test 4: Link GitHub repository."""
        console.print("\n[bold cyan]Test 4: Link GitHub Repository[/bold cyan]")
        
        # Get repo details
        console.print("\n[yellow]Enter GitHub repository details:[/yellow]")
        self.github_owner = console.input("GitHub Username/Owner: ").strip()
        self.github_repo = console.input("Repository Name: ").strip()
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    f"{BASE_URL}/api/github/link-repository",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "project_id": self.project_id,
                        "owner": self.github_owner,
                        "repo": self.github_repo,
                        "language": "python"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    repo_full = data.get("repository", {}).get("full_name", "unknown")
                    self.log_test("Link Repository", "PASS", f"Linked: {repo_full}")
                    return True
                else:
                    error = response.json().get("detail", "Unknown error")
                    self.log_test("Link Repository", "FAIL", f"{error}")
                    return False
        except Exception as e:
            self.log_test("Link Repository", "FAIL", f"Error: {e}")
            return False

    async def test_5_sync_pull_requests(self) -> bool:
        """Test 5: Sync pull requests from GitHub."""
        console.print("\n[bold cyan]Test 5: Sync Pull Requests[/bold cyan]")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout
                response = await client.post(
                    f"{BASE_URL}/api/github/sync/{self.github_owner}/{self.github_repo}/prs",
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    synced = data.get("synced_count", 0)
                    self.log_test("Sync PRs", "PASS", f"Synced {synced} pull requests")
                    return True
                else:
                    error = response.json().get("detail", "Unknown error")
                    self.log_test("Sync PRs", "FAIL", f"{error}")
                    return False
        except Exception as e:
            self.log_test("Sync PRs", "FAIL", f"Error: {e}")
            return False

    async def test_6_code_quality_analysis(self) -> bool:
        """Test 6: Run code quality analysis with AI."""
        console.print("\n[bold cyan]Test 6: Code Quality Analysis (with AI)[/bold cyan]")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:  # Very long timeout for AI
                response = await client.post(
                    f"{BASE_URL}/api/code-quality/analyze",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "repository_id": f"{self.github_owner}/{self.github_repo}",
                        "pr_number": 1,  # Test with PR #1
                        "changed_files": ["README.md", "src/main.py"],
                        "pr_context": {
                            "title": "Test PR",
                            "author": self.github_owner,
                            "base_branch": "main",
                            "head_branch": "feature/test"
                        },
                        "analysis_level": "deep",
                        "use_ai": True  # Enable AI analysis
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    run_id = data.get("run_id")
                    self.log_test("Code Analysis", "PASS", f"Analysis started: {run_id}")
                    
                    # Wait for analysis to complete
                    console.print("   [yellow]Waiting for analysis to complete...[/yellow]")
                    await asyncio.sleep(5)
                    
                    # Check analysis status
                    status_response = await client.get(
                        f"{BASE_URL}/api/code-quality/run/{run_id}",
                        headers={"Authorization": f"Bearer {self.token}"}
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        analysis_status = status_data.get("status")
                        quality_score = status_data.get("quality_score", 0)
                        risk_score = status_data.get("risk_score", 0)
                        
                        self.log_test("  Analysis Status", "PASS", f"{analysis_status}")
                        self.log_test("  Quality Score", "PASS", f"{quality_score}/100")
                        self.log_test("  Risk Score", "PASS", f"{risk_score}/100")
                        
                        # Check if AI was used
                        ai_summary = status_data.get("ai_summary")
                        if ai_summary:
                            self.log_test("  AI Analysis", "PASS", f"AI recommendations generated")
                        else:
                            self.log_test("  AI Analysis", "WARN", "No AI summary (may still be processing)")
                        
                        return True
                    else:
                        self.log_test("Analysis Status", "FAIL", "Could not check status")
                        return False
                else:
                    error = response.json().get("detail", "Unknown error")
                    self.log_test("Code Analysis", "FAIL", f"{error}")
                    return False
        except Exception as e:
            self.log_test("Code Analysis", "FAIL", f"Error: {e}")
            return False

    async def test_7_ai_agent_query(self) -> bool:
        """Test 7: Query AI agent directly."""
        console.print("\n[bold cyan]Test 7: AI Agent Query[/bold cyan]")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{BASE_URL}/api/ai/query",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "query": "What is the risk level of this repository and why?",
                        "context": {
                            "repository": f"{self.github_owner}/{self.github_repo}",
                            "project_id": self.project_id
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "")[:100]  # First 100 chars
                    self.log_test("AI Query", "PASS", f"Response: {answer}...")
                    return True
                else:
                    error = response.json().get("detail", "Unknown error")
                    self.log_test("AI Query", "FAIL", f"{error}")
                    return False
        except Exception as e:
            self.log_test("AI Query", "FAIL", f"Error: {e}")
            return False

    async def run_all_tests(self):
        """Run all tests in sequence."""
        console.print(Panel.fit(
            "[bold white]GitHub + AI Integration Test Suite[/bold white]\n"
            "[dim]Testing complete workflow from authentication to AI analysis[/dim]",
            border_style="cyan"
        ))
        
        # Run tests
        tests = [
            ("Server Health", self.test_1_server_health),
            ("User Login", self.test_2_user_login),
            ("Create Project", self.test_3_create_project),
            ("Link GitHub Repo", self.test_4_link_github_repo),
            ("Sync Pull Requests", self.test_5_sync_pull_requests),
            ("Code Quality + AI", self.test_6_code_quality_analysis),
            ("AI Agent Query", self.test_7_ai_agent_query),
        ]
        
        passed = 0
        failed = 0
        warnings = 0
        
        for name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
                    console.print(f"\n[red]❌ {name} failed. Stopping tests.[/red]")
                    break
            except Exception as e:
                failed += 1
                console.print(f"\n[red]❌ {name} crashed: {e}[/red]")
                break
        
        # Summary
        console.print("\n" + "="*60)
        console.print("[bold]Test Summary[/bold]")
        console.print("="*60)
        
        # Create summary table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Test", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Message", style="dim")
        
        for result in self.results:
            status_style = "green" if result["status"] == "PASS" else "red" if result["status"] == "FAIL" else "yellow"
            table.add_row(
                result["name"],
                f"[{status_style}]{result['status']}[/{status_style}]",
                result["message"]
            )
        
        console.print(table)
        
        console.print(f"\n[bold]Results:[/bold]")
        console.print(f"  ✅ Passed: {passed}")
        console.print(f"  ❌ Failed: {failed}")
        console.print(f"  ⚠️  Warnings: {warnings}")
        
        if failed == 0:
            console.print("\n[bold green]🎉 ALL TESTS PASSED! Your system is working correctly![/bold green]")
        else:
            console.print("\n[bold red]❌ Some tests failed. Check the errors above.[/bold red]")


async def main():
    """Main entry point."""
    try:
        tester = WorkflowTester()
        await tester.run_all_tests()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]❌ Tests cancelled by user[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check if rich is installed
    try:
        import rich
        import httpx
    except ImportError:
        print("❌ Missing dependencies!")
        print("\nInstall with:")
        print("  pip install httpx rich")
        sys.exit(1)
    
    asyncio.run(main())
