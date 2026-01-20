# FinCLI Complete Setup Guide

Comprehensive installation and configuration guide for FinCLI with all LLM provider options.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Gmail API Setup](#gmail-api-setup)
4. [LLM Provider Setup](#llm-provider-setup)
   - [Option 1: Ollama (Free, Local)](#option-1-ollama-free-local)
   - [Option 2: Anthropic Claude](#option-2-anthropic-claude)
   - [Option 3: OpenAI GPT](#option-3-openai-gpt)
   - [Option 4: AWS Bedrock](#option-4-aws-bedrock)
5. [Multi-Provider Strategy](#multi-provider-strategy)
6. [Configuration](#configuration)
7. [Initialization & Testing](#initialization--testing)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- ✅ **Python 3.8+** installed
- ✅ **pip** package manager
- ✅ **Google Cloud account** (for Gmail API - free tier is sufficient)
- ✅ **At least ONE LLM provider** (see options below)

**LLM Provider Options:**
- **Ollama** - 100% free, runs locally, no API key needed ⭐ **Recommended for beginners**
- **Anthropic** - Best quality for extraction, requires API key (~$0.003 per 1K tokens)
- **OpenAI** - Best for conversations, requires API key (~$0.03 per 1K tokens)
- **AWS Bedrock** - Enterprise option, requires AWS account

---

## Installation

### Step 1: Download Project

```bash
# Option A: Clone with Git
git clone <repository-url>
cd gmail-cli-expense-agent

# Option B: Download and extract ZIP
cd gmail-cli-expense-agent
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# You should see (venv) in your prompt
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Verify installation:**
```bash
python -c "import typer, rich, sqlalchemy; print('✓ Dependencies installed')"
```

---

## Gmail API Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"New Project"**
3. Name: `fincli-expense-tracker`
4. Click **"Create"**

### 2. Enable Gmail API

1. In your project, go to **"APIs & Services"** → **"Library"**
2. Search for **"Gmail API"**
3. Click **"Enable"**

### 3. Create OAuth Credentials

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. If prompted, configure OAuth consent screen:
   - User Type: **External**
   - App name: **FinCLI**
   - User support email: your email
   - Developer email: your email
   - Scopes: Add `gmail.readonly`
   - Test users: Add your email
   - Click **"Save and Continue"**
4. Create credentials:
   - Application type: **Desktop app**
   - Name: **FinCLI Desktop**
   - Click **"Create"**
5. **Download JSON** and save as `credentials.json` in project root

**⚠️ Security:** Never commit `credentials.json` to version control!

---

## LLM Provider Setup

Choose **at least ONE** provider. You can set up multiple and switch between them or use different providers for different tasks.

### Option 1: Ollama (Free, Local)

**Best for:** Beginners, development, privacy-focused users, zero cost

#### Install Ollama

**macOS:**
```bash
brew install ollama
# Or download from https://ollama.ai
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download from [ollama.ai/download](https://ollama.ai/download)

#### Pull a Model

```bash
# Start Ollama service (runs in background)
ollama serve

# In another terminal, pull a model
ollama pull llama3  # Recommended: 4.7GB, fast and accurate

# Or try other models:
ollama pull mistral     # 4.1GB, very fast
ollama pull phi3        # 2.3GB, smaller but good
ollama pull llama3:70b  # 40GB, highest quality (needs 64GB+ RAM)
```

**Model Comparison:**

| Model | Size | RAM | Speed | Quality | Best For |
|-------|------|-----|-------|---------|----------|
| llama3 | 4.7GB | 8GB | Fast | Excellent | **Recommended** |
| mistral | 4.1GB | 8GB | Very Fast | Good | Speed-focused |
| phi3 | 2.3GB | 4GB | Fastest | Good | Low-resource systems |
| llama3:70b | 40GB | 64GB+ | Slow | Best | Maximum quality |

#### Test Ollama

```bash
ollama run llama3 "Extract transaction: Spent Rs.500 at Amazon on 2025-11-15"
# Should output structured response
```

#### Configure FinCLI

```bash
# Copy .env.example
cp .env.example .env

# Edit .env and set:
FINCLI_LLM_PROVIDER=ollama
FINCLI_OLLAMA_BASE_URL=http://localhost:11434
FINCLI_OLLAMA_MODEL_NAME=llama3
```

✅ **Done!** Skip to [Initialization & Testing](#initialization--testing)

---

### Option 2: Anthropic Claude

**Best for:** Transaction extraction, structured data, high accuracy

#### Get API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / Log in
3. Go to **"API Keys"**
4. Click **"Create Key"**
5. Copy the API key (starts with `sk-ant-api03-`)

**Pricing:** ~$0.003 per 1K tokens (very affordable for personal use)

#### Configure FinCLI

```bash
cp .env.example .env

# Edit .env:
FINCLI_LLM_PROVIDER=anthropic
FINCLI_ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
FINCLI_ANTHROPIC_MODEL_NAME=claude-3-sonnet-20240229
```

✅ **Done!** Skip to [Initialization & Testing](#initialization--testing)

---

### Option 3: OpenAI GPT

**Best for:** Conversational chat, natural language queries

#### Get API Key

1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up / Log in
3. Go to **"API keys"**
4. Click **"Create new secret key"**
5. Copy the API key (starts with `sk-`)

**Pricing:** ~$0.03 per 1K tokens for GPT-4

#### Configure FinCLI

```bash
cp .env.example .env

# Edit .env:
FINCLI_LLM_PROVIDER=openai
FINCLI_OPENAI_API_KEY=sk-your-key-here
FINCLI_OPENAI_MODEL_NAME=gpt-4  # or gpt-3.5-turbo for lower cost
```

✅ **Done!** Skip to [Initialization & Testing](#initialization--testing)

---

### Option 4: AWS Bedrock

**Best for:** Enterprise deployments, existing AWS infrastructure

#### Prerequisites

- AWS account with billing enabled
- AWS CLI installed and configured
- IAM permissions for Bedrock

#### Setup AWS CLI

```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure
# Enter: Access Key, Secret Key, Region (us-east-1), Format (json)
```

#### Enable Bedrock Model Access

1. Go to [AWS Console](https://console.aws.amazon.com) → **Bedrock**
2. Navigate to **"Model access"**
3. Click **"Manage model access"**
4. Enable **"Claude 3 Sonnet"**
5. Click **"Save changes"** (may take a few minutes)

#### Verify Access

```bash
aws bedrock list-foundation-models --region us-east-1 | grep claude
```

#### Configure FinCLI

```bash
cp .env.example .env

# Edit .env:
FINCLI_LLM_PROVIDER=bedrock
FINCLI_BEDROCK_REGION=us-east-1
FINCLI_BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

✅ **Done!** Skip to [Initialization & Testing](#initialization--testing)

---

## Multi-Provider Strategy

You can use **multiple providers simultaneously** for cost and quality optimization!

### Strategy 1: Free Default + Paid Extraction

Use Ollama for most tasks, Claude only for critical extraction:

```bash
# .env configuration
FINCLI_LLM_PROVIDER=ollama                     # Default: free for everything
FINCLI_LLM_EXTRACTION_PROVIDER=anthropic       # Override: use Claude for extraction only
FINCLI_ANTHROPIC_API_KEY=your-key
```

**Result:** Save 90% on costs, maintain high extraction quality

### Strategy 2: Best-of-Breed

Use the best provider for each task:

```bash
FINCLI_LLM_PROVIDER=ollama                     # Default: free
FINCLI_LLM_EXTRACTION_PROVIDER=anthropic       # Best for structured data
FINCLI_LLM_CHAT_PROVIDER=openai               # Best for conversation
FINCLI_LLM_SUMMARY_PROVIDER=ollama            # Free for summaries
```

### Use Case Routing

FinCLI automatically routes requests based on task type:

| Use Case | Best Provider | Why |
|----------|---------------|-----|
| **Extraction** | Anthropic Claude | Excellent at structured JSON output |
| **Chat** | OpenAI GPT-4 | Best conversational abilities |
| **Summary** | Ollama Llama3 | Free, good enough for summaries |
| **Analysis** | Your choice | All work well |

---

## Configuration

Your `.env` file controls all settings. Key options:

### Gmail Settings

```bash
FINCLI_GMAIL_CREDENTIALS_PATH=credentials.json
FINCLI_GMAIL_TOKEN_PATH=token.json
FINCLI_GMAIL_MAX_RESULTS=100
```

### Email Query Filter

Customize which emails to fetch:

```bash
# Default (works for most Indian banks)
FINCLI_EMAIL_QUERY=subject:("transaction alert" OR "debited" OR "credited")

# For specific banks
FINCLI_EMAIL_QUERY=from:alerts@hdfcbank.net subject:(debited OR credited)

# Multiple banks
FINCLI_EMAIL_QUERY=(from:alerts@hdfcbank.net OR from:alerts@icicibank.com) subject:(transaction)
```

### Database Settings

```bash
# SQLite (default, recommended for personal use)
FINCLI_DATABASE_URL=sqlite:///./fincli.db

# PostgreSQL (for production/multi-user)
FINCLI_DATABASE_URL=postgresql://user:password@localhost:5432/fincli
```

### Logging

```bash
FINCLI_LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR
FINCLI_LOG_FORMAT=console       # console or json
FINCLI_LOG_FILE=./fincli.log    # Optional: log to file
```

### Retry Configuration

```bash
FINCLI_MAX_RETRIES=3            # API retry attempts
FINCLI_RETRY_MIN_WAIT=1         # Min wait between retries (seconds)
FINCLI_RETRY_MAX_WAIT=10        # Max wait between retries (seconds)
```

---

## Initialization & Testing

### Initialize FinCLI

```bash
python cli.py init
```

This will:
1. ✅ Create database tables
2. ✅ Test Gmail connection (opens browser for first-time auth)
3. ✅ Test LLM provider connection
4. ✅ Validate configuration

**Expected output:**
```
Initializing FinCLI...

Creating database tables...
✓ Database initialized

Testing Gmail connection...
[Browser opens for OAuth authorization]
✓ Gmail connection successful

Testing LLM connection (ollama)...
✓ LLM connection successful (ollama)

Initialization complete!
Run 'fetch' to start importing transactions.
```

### First Run

```bash
# Fetch your first batch of transactions
python cli.py fetch --max 20
```

**Expected output:**
```
Fetching transaction emails...
✓ Found 20 emails
Processing emails... ████████████████████ 100%

Summary:
  New transactions: 18
  Skipped (duplicates): 2
  Errors: 0
  Total in database: 18
```

### Test Chat

```bash
python cli.py chat
```

Try asking:
- "How much did I spend this month?"
- "What was my biggest expense?"
- "Show me all Amazon transactions"

---

## Troubleshooting

### Gmail Issues

**Problem:** "Credentials file not found"
```bash
# Check file exists
ls credentials.json

# Verify path in .env
grep GMAIL_CREDENTIALS_PATH .env
```

**Problem:** "Authentication failed"
```bash
# Delete token and re-authenticate
rm token.json
python cli.py init
```

**Problem:** "No emails found"
```bash
# Test your Gmail query manually in Gmail web interface
# Then update FINCLI_EMAIL_QUERY in .env
```

### Ollama Issues

**Problem:** "Connection refused to localhost:11434"
```bash
# Start Ollama service
ollama serve

# In another terminal, verify it's running
ollama list
```

**Problem:** "Model not found"
```bash
# Pull the model
ollama pull llama3

# Verify it's installed
ollama list
```

**Problem:** "Out of memory"
```bash
# Use a smaller model
ollama pull phi3
# Update .env: FINCLI_OLLAMA_MODEL_NAME=phi3
```

### Anthropic/OpenAI Issues

**Problem:** "Invalid API key"
```bash
# Verify key format
# Anthropic: starts with sk-ant-api03-
# OpenAI: starts with sk-

# Test API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $FINCLI_ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

**Problem:** "Rate limit exceeded"
```bash
# Wait a few minutes or upgrade your API plan
# Or switch to free Ollama temporarily
```

### AWS Bedrock Issues

**Problem:** "Access denied"
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify Bedrock access
aws bedrock list-foundation-models --region us-east-1

# Check IAM permissions (need bedrock:InvokeModel)
```

**Problem:** "Model access not enabled"
```bash
# Go to AWS Console → Bedrock → Model access
# Enable Claude 3 Sonnet
```

### Database Issues

**Problem:** "Database locked"
```bash
# Close other instances of FinCLI
# Or reset database
rm fincli.db
python cli.py init
```

### Import Errors

**Problem:** "ModuleNotFoundError"
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Verify virtual environment is activated
which python  # Should show venv/bin/python
```

---

## Next Steps

✅ **Setup complete!** You can now:

1. **Fetch transactions**: `python cli.py fetch`
2. **View summary**: `python cli.py summarize`
3. **Chat with expenses**: `python cli.py chat`
4. **Start API server**: `python run_api.py` (see [API_GUIDE.md](API_GUIDE.md))

For API usage, see **[API_GUIDE.md](API_GUIDE.md)**

For development and contributing, see **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**

---

## Quick Reference

```bash
# Common commands
python cli.py init                      # Initialize
python cli.py fetch --max 50            # Fetch 50 emails
python cli.py list-transactions         # List transactions
python cli.py summarize                 # View summary
python cli.py chat                      # Start chat

# API server
python run_api.py                       # Start API
open http://localhost:8000/docs         # View API docs

# Testing
pytest                                  # Run tests
pytest --cov=fincli                     # With coverage
```

---

**Need help?** Check [API_GUIDE.md](API_GUIDE.md) or [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
