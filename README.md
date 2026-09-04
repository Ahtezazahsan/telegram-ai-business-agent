# Telegram AI Business Agent

An end-to-end AI-powered Telegram customer-support and sales agent built with FastAPI, n8n, Gemini, OpenRouter, Qdrant, Neon PostgreSQL, Vercel, and Cloudflare Tunnel.

The bot answers business questions using approved knowledge, remembers recent conversations, classifies customer intent, supports model fallback, stores messages, and notifies an administrator when human assistance is requested.

## Key Features

- Automated Telegram customer support
- Retrieval-Augmented Generation (RAG)
- Business knowledge retrieval from Qdrant
- Gemini primary language model
- OpenRouter free fallback model
- Persistent conversation memory
- Customer and message storage in PostgreSQL
- Intent classification:
  - `pricing`
  - `sales`
  - `support`
  - `human_handoff`
  - `general`
- Automatic human-handoff detection
- Telegram admin alerts for human requests
- Duplicate Telegram update protection
- Secured Telegram and n8n webhooks
- Vercel-based FastAPI deployment
- Cloudflare Tunnel for local n8n access

## System Architecture

```mermaid
flowchart TD
    A["Telegram Customer"] --> B["Telegram Bot API"]
    B --> C["FastAPI on Vercel"]
    C --> D["Neon PostgreSQL"]
    C --> E["Cloudflare Quick Tunnel"]
    E --> F["Local n8n Orchestrator"]
    F --> G["Qdrant Vector Store"]
    F --> H["Gemini Primary Model"]
    H -. "Failure" .-> I["OpenRouter Fallback"]
    F --> C
    C --> B
    C --> J["Telegram Admin Alert"]
```

## Message Processing Flow

1. A customer sends a message to the Telegram bot.
2. Telegram sends the update to the FastAPI webhook deployed on Vercel.
3. FastAPI authenticates the webhook request.
4. The incoming message and customer information are stored in Neon PostgreSQL.
5. Recent conversation history is loaded from PostgreSQL.
6. FastAPI securely sends the request to the local n8n webhook through Cloudflare Tunnel.
7. n8n retrieves relevant business knowledge from Qdrant.
8. Gemini generates the primary response.
9. If Gemini fails, n8n uses the fixed OpenRouter fallback model.
10. A JavaScript validation node normalizes the AI response.
11. FastAPI sends the final reply to the Telegram customer.
12. The outgoing message is stored in PostgreSQL.
13. If `requires_human` is `true`, FastAPI sends a separate alert to the configured administrator.

## Technology Stack

| Component | Technology |
|---|---|
| API backend | FastAPI |
| Automation orchestration | n8n |
| Primary LLM | Google Gemini |
| Fallback LLM | MiniMax through OpenRouter |
| Embedding model | `gemini-embedding-001` |
| Vector database | Qdrant |
| Relational database | Neon PostgreSQL |
| ORM | SQLAlchemy |
| HTTP client | HTTPX |
| Backend hosting | Vercel |
| Local tunnel | Cloudflare Quick Tunnel |
| Messaging platform | Telegram Bot API |
| Container runtime | Docker |
| Programming languages | Python and JavaScript |

## Repository Structure

```text
telegram-ai-business-agent/
│
├── app/
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── repositories.py
│
├── n8n/
│   └── workflows/
│       ├── 04-telegram-ai-orchestrator.json
│       └── 05-business-knowledge-ingestion.json
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## n8n Workflows

### 04 — Telegram AI Orchestrator

This is the main runtime workflow.

Main stages:

```text
Webhook
  → Qdrant Vector Search
  → Build Knowledge Context
  → Basic LLM Chain
  → Validate and Normalize Output
  → Respond to Webhook
```

Connected AI components:

- Google Gemini Chat Model as the primary model
- `minimax/minimax-m2.7:free` through OpenRouter as the fallback
- Google Gemini Embeddings for Qdrant retrieval

Expected n8n response:

```json
{
  "reply": "Professional response for the customer",
  "intent": "sales",
  "requires_human": false
}
```

The JavaScript validation node handles:

- Valid JSON responses
- Markdown-wrapped JSON
- Plain-text responses
- Missing or invalid intent values
- Boolean normalization
- Human-handoff override
- Safe fallback responses

### 05 — Business Knowledge Ingestion

This workflow loads approved business information into Qdrant.

Main stages:

```text
Manual Trigger
  → Business Knowledge
  → Data Loader
  → Text Splitting
  → Gemini Embeddings
  → Qdrant Vector Store
```

Configuration:

```text
Collection: telegram_business_knowledge
Embedding model: gemini-embedding-001
Vector dimension: 3072
```

This workflow does not need to run whenever the application starts. Run it only when business knowledge is added or updated.

## Environment Variables

Create a local `.env` file based on `.env.example`.

```env
APP_NAME=Telegram AI Business Agent
APP_ENV=development

DATABASE_URL=postgresql://username:password@host/database?sslmode=require

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_WEBHOOK_SECRET=your_secure_webhook_secret
TELEGRAM_SEND_ENABLED=false
ADMIN_TELEGRAM_CHAT_ID=your_numeric_admin_chat_id

N8N_ORCHESTRATION_URL=https://your-current-tunnel.trycloudflare.com/webhook/telegram-ai-orchestrator
N8N_INTERNAL_API_KEY=your_secure_internal_api_key
```

For Vercel production, configure:

```env
APP_NAME=Telegram AI Business Agent
APP_ENV=production
DATABASE_URL=your_neon_postgresql_connection_string
TELEGRAM_BOT_TOKEN=your_current_telegram_bot_token
TELEGRAM_WEBHOOK_SECRET=your_secure_webhook_secret
TELEGRAM_SEND_ENABLED=true
ADMIN_TELEGRAM_CHAT_ID=your_numeric_admin_chat_id
N8N_ORCHESTRATION_URL=https://your-current-tunnel.trycloudflare.com/webhook/telegram-ai-orchestrator
N8N_INTERNAL_API_KEY=your_secure_internal_api_key
```

Never commit the real `.env` file.

## Required n8n Credentials

The exported n8n workflows contain credential references but should not contain secret credential values.

Configure these credentials manually after importing the workflows:

- Google Gemini API credential
- OpenRouter API credential
- Qdrant API credential
- n8n Header Auth credential

The n8n Header Auth credential must send:

```text
Header name: X-Internal-API-Key
Header value: same value as N8N_INTERNAL_API_KEY
```

## Local Setup

### 1. Clone the repository

```powershell
git clone YOUR_GITHUB_REPOSITORY_URL
cd telegram-ai-business-agent
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
Set-ExecutionPolicy `
  -Scope Process `
  -ExecutionPolicy RemoteSigned

.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create `.env`

```powershell
Copy-Item .env.example .env
```

Replace the placeholder values inside `.env` with actual local credentials.

### 5. Verify the Python application

```powershell
python -m py_compile app/main.py
```

Expected result: no output.

Optional import verification:

```powershell
python -c "from app.main import app; print('Application import OK')"
```

Expected result:

```text
Application import OK
```

## Starting the Complete System

### 1. Start Docker Desktop

Wait until Docker Desktop reports that the Docker engine is running.

### 2. Start n8n and Qdrant

```powershell
docker start n8n qdrant
```

Verify:

```powershell
docker ps
```

Expected running services:

- n8n on port `5678`
- Qdrant on ports `6333` and `6334`

Open locally:

```text
n8n:    http://localhost:5678
Qdrant: http://localhost:6333/dashboard
```

### 3. Start Cloudflare Quick Tunnel

Open a separate PowerShell terminal:

```powershell
cloudflared tunnel --url http://localhost:5678
```

Cloudflare will generate a temporary URL similar to:

```text
https://random-words.trycloudflare.com
```

Keep this terminal running.

### 4. Update the Vercel n8n URL

Set the Vercel Production environment variable:

```text
N8N_ORCHESTRATION_URL
```

Value:

```text
https://random-words.trycloudflare.com/webhook/telegram-ai-orchestrator
```

Redeploy the latest Vercel deployment after changing the variable.

### 5. Verify services

FastAPI health endpoint:

```text
https://your-vercel-domain.vercel.app/health
```

Expected response:

```json
{
  "status": "healthy"
}
```

## Important Quick Tunnel Limitation

This project currently uses a free Cloudflare Quick Tunnel because no custom domain is configured.

Whenever the laptop or Cloudflare terminal is restarted:

1. Start Docker Desktop.
2. Start n8n and Qdrant.
3. Run Cloudflare Quick Tunnel.
4. Copy the new `trycloudflare.com` URL.
5. Update `N8N_ORCHESTRATION_URL` in Vercel.
6. Redeploy Vercel.

The other environment variables do not need to be updated.

A Cloudflare Named Tunnel can provide a stable hostname in the future when a custom domain is available.

## Telegram Webhook

Production webhook endpoint:

```text
https://your-vercel-domain.vercel.app/webhooks/telegram
```

The webhook is protected using:

```text
X-Telegram-Bot-Api-Secret-Token
```

The secret must match:

```text
TELEGRAM_WEBHOOK_SECRET
```

Webhook registration is only required when initially configuring the bot or when changing the production webhook URL. It is not required after every laptop restart.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Service information |
| GET | `/health` | Health check |
| POST | `/webhooks/telegram` | Telegram updates |
| GET | `/admin/database/stats` | Database statistics |
| POST | `/admin/database/init` | Initialize database tables |
| POST | `/admin/telegram/setup-webhook` | Configure Telegram webhook |

Admin endpoints require:

```text
X-Admin-Key: TELEGRAM_WEBHOOK_SECRET
```

## Conversation Memory

Recent incoming and outgoing messages are stored in Neon PostgreSQL.

For every new Telegram request:

- The current message is saved.
- Up to 10 previous messages are loaded.
- The current update is excluded from conversation history.
- History is sent to n8n.
- The LLM uses it only to understand follow-up questions.
- The current customer message always receives priority.

Example:

```text
Customer: What services do you offer?
Bot: We offer AI automation, business chatbots, workflow automation...

Customer: Can you arrange a demonstration for the service you mentioned?
Bot: Yes, our sales team can help arrange a demonstration.
```

## Human Handoff

If a customer explicitly requests a:

- Human
- Agent
- Representative
- Manager
- Team member
- Real person
- Sales representative

the validation node produces:

```json
{
  "intent": "human_handoff",
  "requires_human": true
}
```

FastAPI then:

1. Sends the customer a handoff confirmation.
2. Stores the outgoing message.
3. Sends a separate Telegram administrator alert.

Example alert:

```text
🚨 HUMAN HANDOFF REQUIRED

Customer: Customer Name
Username: @username
Customer Chat ID: 123456789
Message: Customer's original message

AI Reply: Handoff confirmation generated for the customer
```

If the Telegram user has no public username, the alert shows:

```text
Username: not_available
```

This is expected and is not an error.

## Database Persistence

Neon PostgreSQL stores:

- Telegram customer identity
- Chat ID
- Username, when available
- First name
- Incoming messages
- Outgoing messages
- Telegram update IDs
- Message timestamps
- Telegram message IDs

Telegram update IDs are used to prevent duplicate processing.

## Security

The project implements:

- Telegram webhook secret validation
- Internal API-key validation between FastAPI and n8n
- Environment-based secret management
- Duplicate update protection
- Separate administrative endpoints
- No hard-coded API keys
- No secrets inside exported workflow files
- `.env` excluded through `.gitignore`

Never commit:

- `.env`
- Telegram bot tokens
- Gemini API keys
- OpenRouter API keys
- Qdrant API keys
- PostgreSQL passwords
- Internal webhook keys

## Secret Verification Before Git Push

Confirm `.env` is ignored:

```powershell
git check-ignore -v .env
```

Confirm `.env` is not tracked:

```powershell
git ls-files .env
```

Expected: no output.

Search exported workflows:

```powershell
Select-String `
  -Path "n8n\workflows\*.json" `
  -Pattern "AIza|sk-|bot[0-9]+:|X-Internal-API-Key"
```

Expected: no actual secret values.

Review staged files:

```powershell
git status --short
```

`.env.example` may appear. `.env` must not appear.

Final staged-content scan:

```powershell
git diff --cached |
  Select-String -Pattern "AIza|sk-[A-Za-z0-9]|[0-9]{8,}:[A-Za-z0-9_-]{20,}|postgresql://[^ ]+:[^ ]+@"
```

Expected: no secret values.

## Troubleshooting

### n8n shows “Database is not ready”

Wait for n8n initialization and inspect:

```powershell
docker logs n8n
```

### Telegram bot returns a temporary failure message

Check:

1. Latest n8n execution
2. Cloudflare Tunnel terminal
3. Vercel deployment logs
4. Gemini primary-model status
5. OpenRouter fallback status

### Structured output errors

The project does not hard-fail on minor model formatting differences.

The JavaScript validation node supports:

- JSON objects
- JSON strings
- Markdown JSON
- Plain-text replies
- Missing intent fields
- Missing boolean fields

### n8n cannot connect directly to Telegram

Some local networks or ISPs may block `api.telegram.org`.

This project sends Telegram replies and admin alerts through Vercel FastAPI, avoiding dependency on direct local n8n-to-Telegram connectivity.

### `DATABASE_URL` cannot be parsed

Ensure:

- The URL contains the actual database password.
- Placeholder stars are not present.
- Quotes and extra spaces are removed.
- `load_dotenv()` runs before reading the variable.
- The appropriate PostgreSQL driver is installed.

### Qdrant collection error

Confirm:

```text
Collection name: telegram_business_knowledge
Vector dimension: 3072
Embedding model: gemini-embedding-001
```

The same embedding model must be used during ingestion and retrieval.

## Tested Scenarios

The completed system has been verified for:

- General business questions
- Business hours
- Available services
- Pricing requests
- Sales and demonstration requests
- Technical support requests
- Conversation follow-ups
- Human-agent requests
- Gemini-to-OpenRouter fallback
- Knowledge retrieval from Qdrant
- PostgreSQL conversation persistence
- Telegram administrator alerts

## Current Project Status

Core functionality is complete:

- Telegram integration
- Secure FastAPI backend
- n8n orchestration
- RAG knowledge retrieval
- Persistent conversation memory
- Primary and fallback LLMs
- Intent classification
- Human handoff
- Administrator notification
- Database persistence
- Vercel deployment
- Cloudflare connectivity

Future optional improvements:

- Custom domain and Cloudflare Named Tunnel
- Web-based admin dashboard
- CRM integration
- Email notifications
- Analytics and reporting
- Multiple business support
- Scheduled knowledge synchronization
- Production monitoring and alerting
