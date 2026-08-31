# AI Agents Layer (Layer 6) - LangGraph + Ollama

## Overview

The AI Agents layer interprets **objective evidence** from the Intelligence Engine (Layer 5) and provides:
- Natural language analysis
- Actionable recommendations
- Risk assessments with confidence scores

**Key Principle:** Agents DO NOT calculate metrics. They interpret metrics already computed by Layer 5.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Supervisor Agent                       │
│              (LangGraph StateGraph)                      │
└──────┬──────────┬─────────────┬──────────────┬─────────┘
       │          │             │              │
       ▼          ▼             ▼              ▼
┌──────────┐ ┌─────────┐ ┌──────────┐ ┌───────────────┐
│   Code   │ │   QA    │ │ DevOps   │ │   Meeting     │
│  Agent   │ │ Agent   │ │  Agent   │ │   Agent       │
└──────────┘ └─────────┘ └──────────┘ └───────────────┘
```

## Agents

### 1. Code Agent (`code_agent.py`)
**Purpose:** Interprets PR evidence for code review insights

**Input Evidence:**
- Complexity score, files changed, lines added/deleted
- Review metrics (comments, cycles, time)
- Risk assessment from Layer 5

**Output:**
- Analysis: Key insights about code quality
- Recommendations: Specific improvements (3-5 bullets)
- Risk level: low/medium/high/critical
- Confidence: 0.0-1.0

**Use Case:** Post-PR analysis, automated code review summaries

---

### 2. QA Agent (`qa_agent.py`)
**Purpose:** Test coverage and quality assurance recommendations

**Input Evidence:**
- Test coverage metrics (%, delta, files without tests)
- Quality metrics (untested lines, critical paths)
- QA risk assessment

**Output:**
- Analysis: Quality gaps and patterns
- Recommendations: Specific tests to add
- Risk level: QA risk assessment
- Confidence: 0.0-1.0

**Use Case:** Test planning, QA strategy for features

---

### 3. DevOps Agent (`devops_agent.py`)
**Purpose:** Deployment risk and infrastructure recommendations

**Input Evidence:**
- Deployment risk score, breaking changes, migrations
- CI/CD status (build, tests, pipeline duration)
- Infrastructure signals (large PR, hot paths)

**Output:**
- Analysis: Deployment readiness
- Recommendations: CI/CD improvements, deployment strategy
- Risk level: Deployment risk
- Confidence: 0.0-1.0

**Use Case:** Pre-deployment checks, infrastructure planning

---

### 4. Meeting Agent (`meeting_agent.py`)
**Purpose:** Sprint insights for standups and retrospectives

**Input Evidence:**
- Sprint metrics (velocity, burndown, scope changes)
- Team performance (review time, WIP, blockers)
- Risk indicators (at-risk stories, capacity)

**Output:**
- Analysis: Sprint health insights
- Recommendations: Standup talking points or retrospective actions
- Risk level: Sprint health
- Confidence: 0.0-1.0

**Use Case:** Automated standup prep, retrospective generation

---

## LLM Provider: Ollama

**Why Ollama?**
- ✅ Local deployment (no API costs)
- ✅ Full data privacy
- ✅ No external dependencies
- ✅ Great for development and testing

**Supported Models:**
- `llama3.2` (default) - fast, efficient
- `llama3.1` - larger, more capable
- `mistral` - alternative option
- Any Ollama-supported model

**Configuration:**
```bash
# .env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

**Prerequisites:**
1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull llama3.2`
3. Verify: `ollama list`

---

## API Usage

### Endpoint: `POST /api/ai/invoke`

**Request:**
```json
{
  "task_type": "code_review",
  "evidence": {
    "complexity_score": 45,
    "files_changed": 12,
    "risk_level": "medium",
    "risk_score": 65,
    "review_comments": 8
  },
  "context": {
    "pr_title": "Add authentication",
    "author": "dev@example.com",
    "sprint_name": "Sprint 23"
  },
  "save_run": true
}
```

**Response:**
```json
{
  "run_id": "uuid",
  "task_type": "code_review",
  "analysis": "The PR shows moderate complexity with 12 files changed...",
  "recommendations": [
    "Add unit tests for authentication middleware",
    "Refactor token validation logic into separate function",
    "Document security considerations in README"
  ],
  "risk_level": "medium",
  "confidence": 0.85,
  "agent_history": ["code_agent"],
  "errors": [],
  "execution_time_ms": 1250.5
}
```

---

## Task Types

| Task Type          | Agent           | Use Case                        |
|--------------------|-----------------|---------------------------------|
| `code_review`      | Code Agent      | PR analysis, code quality       |
| `qa_analysis`      | QA Agent        | Test planning, coverage gaps    |
| `devops_risk`      | DevOps Agent    | Deployment readiness            |
| `meeting_insights` | Meeting Agent   | Sprint health, standup prep     |

---

## Development Workflow

### 1. Start Ollama
```bash
ollama serve
# In another terminal:
ollama pull llama3.2
```

### 2. Test Agent Locally
```python
from agents.supervisor import create_supervisor_graph

graph = create_supervisor_graph()
result = graph.invoke({
    "task_type": "code_review",
    "evidence": {"complexity_score": 45},
    "context": {"pr_title": "Test PR"},
    "agent_history": [],
    "errors": [],
})

print(result["analysis"])
print(result["recommendations"])
```

### 3. API Testing
```bash
# Health check
curl http://localhost:8000/api/ai/health

# Invoke agent
curl -X POST http://localhost:8000/api/ai/invoke \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "code_review",
    "evidence": {"complexity_score": 45},
    "context": {}
  }'
```

---

## Integration with Layer 5

**Pattern:**
```python
# Layer 5: Calculate evidence
from intelligence.evidence import build_pr_evidence

evidence = build_pr_evidence(pr_data, pr_metadata)
# Returns: {complexity_score, risk_level, files_changed, ...}

# Layer 6: Interpret evidence
from agents.supervisor import create_supervisor_graph

graph = create_supervisor_graph()
result = graph.invoke({
    "task_type": "code_review",
    "evidence": evidence,  # Pass Layer 5 output directly
    "context": {"pr_title": pr_data.title},
    "agent_history": [],
    "errors": [],
})

# Use AI insights
print(result["analysis"])
print(result["recommendations"])
```

---

## Error Handling

Agents gracefully handle failures:
- LLM connection errors → captured in `errors` list
- Parsing failures → default values used
- Ollama unavailable → 503 Service Unavailable response

**Health Check:**
```bash
GET /api/ai/health
```

Returns Ollama connection status.

---

## Future Enhancements

- [ ] Streaming responses for real-time feedback
- [ ] Multi-agent collaboration (e.g., Code + QA agents together)
- [ ] Custom prompt templates per project
- [ ] Fine-tuning on historical agent runs
- [ ] Confidence-based auto-approval workflows

---

## Files

```
agents/
├── __init__.py           # Module exports
├── state.py              # LangGraph state definitions
├── llm_provider.py       # Ollama integration
├── supervisor.py         # LangGraph orchestrator
├── code_agent.py         # Code review agent
├── qa_agent.py           # QA recommendations agent
├── devops_agent.py       # DevOps risk agent
├── meeting_agent.py      # Meeting insights agent
└── README.md             # This file
```

---

## Troubleshooting

**Problem:** `Ollama service not available`
- Solution: Ensure Ollama is running (`ollama serve`)

**Problem:** `Model not found`
- Solution: Pull the model (`ollama pull llama3.2`)

**Problem:** Slow responses
- Solution: Use smaller model (llama3.2 vs llama3.1) or adjust temperature

**Problem:** Low-quality recommendations
- Solution: Improve evidence quality from Layer 5, or adjust prompts

---

## References

- LangGraph: https://langchain-ai.github.io/langgraph/
- Ollama: https://ollama.ai/
- Langchain Community: https://python.langchain.com/docs/integrations/llms/ollama
