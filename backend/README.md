# Samanvaya Backend

AI-powered developer performance evaluation system with FastAPI and Ollama.

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **MongoDB** (running on localhost:27017)
- **Ollama** (optional, for AI features)
- **GitHub Token** (optional, for GitHub integration)

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env and configure:
# - SECRET_KEY (required)
# - GITHUB_TOKEN (optional)
```

### 3. Install Dependencies

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Optional: Install development tools
pip install -r dev-requirements.txt
```

### 4. Initialize Database

```bash
python init_db.py
```

### 5. Start Server

```bash
python start.py
```

The API will be available at `http://localhost:8000`

### 6. Verify Installation

```bash
python test_backend.py
```

## 📁 Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── start.py               # Enhanced startup script with health checks
├── init_db.py            # Database initialization
├── test_backend.py       # Comprehensive backend tests
├── core/                 # Core infrastructure
│   ├── config.py         # Configuration management
│   ├── database.py       # MongoDB connection
│   ├── security.py       # JWT and password handling
│   ├── dependencies.py   # FastAPI dependencies
│   └── permissions.py    # RBAC system
├── api/                  # REST API routes
│   ├── routes/           # Feature-specific routes
│   └── roles/            # Role-specific dashboards
├── domain/               # Business logic
│   ├── models/           # Pydantic models
│   └── services/         # Business services
├── agents/               # AI agents (Ollama)
├── intelligence/         # Analytics engine
├── integrations/         # External integrations
│   └── github/           # GitHub API client
└── repositories/         # Database access layer
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | JWT signing key (32+ chars) |
| `MONGO_URI` | ❌ | MongoDB connection string |
| `GITHUB_TOKEN` | ❌ | GitHub PAT for repo access |
| `OLLAMA_BASE_URL` | ❌ | Ollama server URL |
| `OLLAMA_MODEL` | ❌ | Ollama model name |
| `ALLOWED_ORIGINS` | ❌ | CORS allowed origins |

### Generate SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### GitHub Token Setup

1. Go to [GitHub Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Create new token with scopes: `repo`, `read:org`, `read:user`
3. Add to `.env` file as `GITHUB_TOKEN=your_token_here`

### Ollama Setup (Optional)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull llama3.2

# Start server
ollama serve
```

## 🌐 API Endpoints

### Core Features

- **Authentication**: `/api/auth/*` - User login, registration, JWT
- **Performance**: `/api/performance/*` - Developer evaluations  
- **GitHub**: `/api/github/*` - Repository and PR analysis
- **Teams**: `/api/teams/*` - Team management
- **Employees**: `/api/employees/*` - Employee management

### Role Dashboards

- `/api/role/developer` - Developer dashboard
- `/api/role/lead` - Tech Lead dashboard
- `/api/role/pm` - Project Manager dashboard
- `/api/role/ceo` - Executive dashboard
- `/api/role/hr` - HR dashboard
- `/api/role/qa` - QA dashboard
- `/api/role/devops` - DevOps dashboard

### Health & Monitoring

- `/health` - System health check
- `/` - API information

## 🧪 Testing

```bash
# Run comprehensive tests
python test_backend.py

# Test specific components
python -c "from agents.llm_provider import check_ollama_connection; print(check_ollama_connection())"
```

## 🐛 Troubleshooting

### Common Issues

**MongoDB Connection Failed**
```bash
# Start MongoDB
sudo systemctl start mongod
# or
brew services start mongodb-community
```

**Ollama Not Available**
```bash
# Start Ollama server
ollama serve

# Check models
ollama list
```

**GitHub API Errors**
- Verify token has correct scopes
- Check rate limits: `/api/github/health`

**Import Errors**
- Install missing dependencies: `pip install -r requirements.txt`
- Check Python path and virtual environment

## 📊 Performance Monitoring

The system provides built-in monitoring:

- **Health Check**: `/health` - Dependencies status
- **GitHub Status**: `/api/github/health` - Token validity and rate limits
- **Database**: Connection and query performance
- **AI Status**: Ollama availability and model info

## 🔒 Security Features

- **JWT Authentication** - Secure token-based auth
- **RBAC System** - Role-based access control with 30+ permissions
- **Password Hashing** - bcrypt with salt
- **CORS Protection** - Configurable origin restrictions
- **Input Validation** - Pydantic models for all inputs

## 🚀 Production Deployment

1. **Environment**:
   - Set strong `SECRET_KEY`
   - Configure `ALLOWED_ORIGINS` for production domains
   - Use production MongoDB instance

2. **Security**:
   - Enable HTTPS
   - Set up reverse proxy (nginx/traefik)
   - Configure firewall rules

3. **Monitoring**:
   - Set up health check monitoring
   - Configure log aggregation
   - Monitor GitHub API rate limits

4. **Scaling**:
   - Run multiple uvicorn workers
   - Use MongoDB replica sets
   - Consider load balancing

## 📚 Development

### Adding New Features

1. **Models**: Add Pydantic models to `domain/models/`
2. **Services**: Add business logic to `domain/services/`
3. **Routes**: Add API endpoints to `api/routes/`
4. **Tests**: Add tests to verify functionality

### Code Quality

```bash
# Format code
ruff format .

# Check types
mypy .

# Security scan
bandit -r .

# Run tests
pytest
```

## 🤝 Contributing

1. Follow the existing code structure
2. Add type hints for all functions
3. Include docstrings for public methods
4. Test new features with `test_backend.py`
5. Update this README for new configuration options

## 📄 License

AI-powered developer performance evaluation system for engineering teams.
