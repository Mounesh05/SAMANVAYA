# 🚀 START HERE: Complete Testing Workflow

Follow these steps to test your GitHub + AI integration.

---

## **Step-by-Step Testing Process**

### **🔧 STEP 1: Start the Server**

Open PowerShell in `m:\Samanvaya\backend`:

```powershell
cd m:\Samanvaya\backend
.\.venv\Scripts\Activate.ps1
python start.py
```

**Expected output:**
```
🚀 Starting Samanvaya Backend
==================================================
🔍 Checking dependencies...
   ✅ Environment configuration OK
   ✅ MongoDB connection OK
   ✅ Ollama connection OK
   ✅ GitHub token valid

✅ All checks passed! Starting server...

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**Leave this terminal open!** The server must keep running.

---

### **✅ STEP 2: Quick Health Check**

Open a **NEW PowerShell** terminal:

```powershell
cd m:\Samanvaya\backend
.\.venv\Scripts\Activate.ps1
python quick_test.py
```

**Expected:**
```
✅ Server Running
✅ MongoDB: connected
✅ Ollama AI: connected
✅ GitHub: configured
```

---

### **👤 STEP 3: Create First User**

In the same terminal:

```powershell
python create_first_user.py
```

**Enter when prompted:**
- Employee ID: `EMP001`
- Name: `Your Name`
- Email: `admin@example.com`
- Password: `YourPassword123!`
- Role: `HR` (auto-set)

**✏️ SAVE THESE CREDENTIALS!** You'll need them for testing.

---

### **🧪 STEP 4: Run Full Integration Test**

```powershell
# Install test dependencies (one-time)
pip install httpx rich

# Run comprehensive test
python test_github_ai_workflow.py
```

**You'll be prompted for:**

1. **Login credentials** (from Step 3)
2. **GitHub username** (your GitHub account name)
3. **Repository name** (a repo you have access to)

**The test will:**
- ✅ Test server health
- ✅ Authenticate your user
- ✅ Create a test project
- ✅ Link your GitHub repo
- ✅ Sync pull requests
- ✅ Run code quality analysis **with AI**
- ✅ Query the AI agent

**Expected time:** 2-5 minutes

---

### **📊 STEP 5: View Results**

After the test completes, you'll see:

```
Test Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Passed: 7
❌ Failed: 0

🎉 ALL TESTS PASSED!
```

---

## **📋 Checklist**

Before running tests, make sure:

- [ ] MongoDB is running (`mongod` or Windows service)
- [ ] Ollama is running (`ollama serve`)
- [ ] GitHub token is in `.env` file
- [ ] Backend server is running (`python start.py`)
- [ ] You have a GitHub repo to test with

---

## **🐛 Common Issues**

### **Issue: Server won't start**

**Solution:**
```powershell
# Check MongoDB
net start MongoDB

# Check port 8000
Get-NetTCPConnection -LocalPort 8000
```

### **Issue: GitHub token invalid**

**Solution:**
1. Go to https://github.com/settings/tokens
2. Generate new token with scopes: `repo`, `read:org`, `read:user`, `workflow`
3. Update `GITHUB_TOKEN` in `.env`
4. Restart server

### **Issue: Ollama not responding**

**Solution:**
```powershell
# Check Ollama
ollama list

# Pull model if needed
ollama pull llama3.2

# Test directly
ollama run llama3.2 "Hello"
```

### **Issue: Test fails at "Sync PRs"**

**Cause:** No pull requests in the repository

**Solution:** 
- Use a repo with existing PRs
- Or create a test PR first
- Test will still pass with 0 PRs synced

---

## **🎯 What Success Looks Like**

### **Successful Test Output:**

```
Test 6: Code Quality Analysis (with AI)
✅ Code Analysis: Analysis started
✅   Analysis Status: completed
✅   Quality Score: 85/100
✅   Risk Score: 35/100
✅   AI Analysis: AI recommendations generated  ← THIS CONFIRMS AI WORKS!

Test 7: AI Agent Query
✅ AI Query: Response: Based on the analysis...  ← THIS CONFIRMS OLLAMA WORKS!
```

If you see these, your **AI integration is working perfectly!** 🎉

---

## **📚 After Testing**

Once all tests pass:

1. **View API Docs:** http://localhost:8000/docs
2. **Check MongoDB:** Use MongoDB Compass
   - Database: `samanvaya`
   - Collections: `users`, `projects`, `pull_requests`, `code_quality_runs`
3. **View Logs:** Check server terminal for detailed logs
4. **Customize:** Modify risk weights via `/api/risk-configurations`

---

## **🔥 Quick Commands Reference**

```powershell
# Start server
cd m:\Samanvaya\backend
.\.venv\Scripts\Activate.ps1
python start.py

# Quick test (new terminal)
python quick_test.py

# Create user
python create_first_user.py

# Full test
python test_github_ai_workflow.py

# View API docs
# Open browser: http://localhost:8000/docs

# Stop server
# Press Ctrl+C in server terminal
```

---

## **✨ Next Steps**

After successful testing:

1. Explore the API documentation
2. Test with different repositories
3. Customize risk configurations
4. Set up the frontend (if available)
5. Deploy to production

---

**Need more help?** Check `TESTING_GUIDE.md` for detailed troubleshooting.
