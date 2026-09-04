# 🧪 Testing Guide: GitHub + AI Integration

Complete guide to test your Samanvaya system end-to-end.

---

## **📋 Prerequisites**

Make sure these are running:

1. ✅ **MongoDB** - `mongod` or `net start MongoDB`
2. ✅ **Ollama** - `ollama serve` (with llama3.2 model)
3. ✅ **Backend Server** - `python start.py`
4. ✅ **GitHub Token** - Set in `.env` file

---

## **🚀 Quick Start (3 Steps)**

### **Step 1: Quick Health Check**

```powershell
cd m:\Samanvaya\backend
.\.venv\Scripts\Activate.ps1
python quick_test.py
```

**Expected output:**
```
✅ Server Running
✅ MongoDB: connected
✅ Ollama AI: connected
✅ GitHub: configured
```

### **Step 2: Create First User**

```powershell
python create_first_user.py
```

Enter your details:
- Employee ID: `EMP001`
- Name: Your Name
- Email: your@email.com
- Password: (min 8 characters)
- Role: HR (automatically set)

**Save these credentials!**

### **Step 3: Full Workflow Test**

```powershell
# Install test dependencies
pip install httpx rich

# Run comprehensive test
python test_github_ai_workflow.py
```

You'll be prompted for:
1. Login credentials (from Step 2)
2. GitHub username/owner
3. GitHub repository name

---

## **🔬 What Gets Tested**

The full workflow test verifies:

| # | Test | What It Checks |
|---|------|----------------|
| 1 | **Server Health** | API responding, MongoDB connected, Ollama running, GitHub token valid |
| 2 | **User Login** | Authentication works, JWT tokens generated |
| 3 | **Create Project** | Project management API functional |
| 4 | **Link GitHub Repo** | GitHub API integration, repo access |
| 5 | **Sync Pull Requests** | Fetches PRs from GitHub, stores in MongoDB |
| 6 | **Code Quality Analysis** | NEW analyzer system, risk calculation, **AI recommendations** |
| 7 | **AI Agent Query** | Ollama model responding, context-aware answers |

---

## **📊 Sample Test Output**

```
╭─────────────────────────────────────────────────────────╮
│ GitHub + AI Integration Test Suite                     │
│ Testing complete workflow from authentication to AI...  │
╰─────────────────────────────────────────────────────────╯

Test 1: Server Health Check
✅ Server: Server running v1.0.0
✅   Database: connected
✅   Ollama: connected
✅   GitHub: configured

Test 2: User Authentication
Enter your login credentials:
Email: admin@example.com
Password: ********
✅ Login: Authenticated as HR

Test 3: Create Test Project
✅ Create Project: Project ID: proj_abc123

Test 4: Link GitHub Repository
Enter GitHub repository details:
GitHub Username/Owner: your-username
Repository Name: your-repo
✅ Link Repository: Linked: your-username/your-repo

Test 5: Sync Pull Requests
✅ Sync PRs: Synced 3 pull requests

Test 6: Code Quality Analysis (with AI)
   Waiting for analysis to complete...
✅ Code Analysis: Analysis started: run_xyz789
✅   Analysis Status: completed
✅   Quality Score: 85/100
✅   Risk Score: 35/100
✅   AI Analysis: AI recommendations generated

Test 7: AI Agent Query
✅ AI Query: Response: Based on the analysis, this repository has...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Test Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Passed: 7
❌ Failed: 0
⚠️  Warnings: 0

🎉 ALL TESTS PASSED! Your system is working correctly!
```

---

## **🔍 Manual Testing (Without Scripts)**

If you prefer manual testing via API:

### **1. Test Health Endpoint**

```powershell
curl http://localhost:8000/health
```

### **2. Login and Get Token**

```powershell
$body = @{
    email = "admin@example.com"
    password = "your-password"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

$token = $response.access_token
Write-Output "Token: $token"
```

### **3. Link GitHub Repo**

```powershell
$headers = @{ "Authorization" = "Bearer $token" }

$body = @{
    project_id = "test_project"
    owner = "your-username"
    repo = "your-repo"
    language = "python"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/github/link-repository" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"
```

### **4. Analyze Code with AI**

```powershell
$body = @{
    repository_id = "your-username/your-repo"
    pr_number = 1
    changed_files = @("README.md", "src/main.py")
    pr_context = @{
        title = "Test PR"
        author = "your-username"
        base_branch = "main"
        head_branch = "feature/test"
    }
    analysis_level = "deep"
    use_ai = $true
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:8000/api/code-quality/analyze" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"
```

### **5. Query AI Agent**

```powershell
$body = @{
    query = "What is the code quality of this repository?"
    context = @{
        repository = "your-username/your-repo"
    }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "http://localhost:8000/api/ai/query" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"
```

---

## **🐛 Troubleshooting**

### **Server won't start**
```powershell
# Check if MongoDB is running
Get-Process mongod

# Check if port 8000 is free
Get-NetTCPConnection -LocalPort 8000
```

### **MongoDB connection failed**
```powershell
# Start MongoDB
net start MongoDB

# Or manually
mongod --dbpath "C:\data\db"
```

### **Ollama not responding**
```powershell
# Check if Ollama is running
ollama list

# Test Ollama directly
ollama run llama3.2 "Hello"

# Check Ollama service
Get-Process ollama
```

### **GitHub token invalid**
1. Go to https://github.com/settings/tokens
2. Generate new token with scopes: `repo`, `read:org`, `read:user`, `workflow`
3. Update `GITHUB_TOKEN` in `.env`
4. Restart server

### **AI analysis takes too long**
- First run downloads AI model (large file)
- Subsequent runs are faster
- Check Ollama logs: `ollama logs`

---

## **📈 Performance Benchmarks**

Expected response times:

| Operation | Time | Notes |
|-----------|------|-------|
| Health Check | <100ms | Instant |
| Login | <500ms | Database query |
| Link Repo | 1-2s | GitHub API call |
| Sync PRs | 2-10s | Depends on PR count |
| Code Analysis (no AI) | 5-10s | Static analysis only |
| Code Analysis (with AI) | 20-60s | AI model inference |
| AI Query | 10-30s | Depends on question complexity |

---

## **✅ Success Criteria**

Your system is working if:

1. ✅ All 7 tests pass in `test_github_ai_workflow.py`
2. ✅ GitHub PRs sync successfully
3. ✅ Risk scores are calculated (not all 0)
4. ✅ Quality scores are calculated (not all 0)
5. ✅ AI summaries are generated (not empty)
6. ✅ AI agent responds to queries

---

## **📚 Next Steps**

After testing:

1. **Explore API**: http://localhost:8000/docs
2. **View Data**: MongoDB Compass → `samanvaya` database
3. **Check Logs**: Server terminal output
4. **Run More Tests**: Create more PRs, analyze different repos
5. **Customize Config**: Modify risk weights via API

---

## **🎯 Key Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System status |
| `/api/auth/login` | POST | Authentication |
| `/api/github/link-repository` | POST | Connect repo |
| `/api/github/sync/{owner}/{repo}/prs` | POST | Fetch PRs |
| `/api/code-quality/analyze` | POST | Run analysis |
| `/api/ai/query` | POST | Ask AI |
| `/api/risk-configurations/global` | GET | View config |
| `/docs` | GET | API documentation |

---

**Need help?** Check the API docs or server logs for detailed error messages.
