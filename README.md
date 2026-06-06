# Threads AI Agent

An AI-powered automation system that generates, validates, and publishes Threads/X-style posts in the persona of Abdul Fatah Tirtayasa.

## Features
- **Persona-Driven Generation**: Uses AI API to write posts based on a specific technical builder persona.
- **Dual-Layer Validation**: LLM-based Safety Checker and Style Checker.
- **Human-in-the-Loop**: Telegram integration with inline buttons for Approve/Reject/Regenerate.
- **Official Threads API**: Uses the official Meta Graph API for Threads (Container -> Publish pattern).
- **Auto-Publish Mode**: Configurable bypass for high-scoring drafts.

## Setup Steps

1. **Clone and Install Dependencies**

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Environment Variables**

Copy `.env.example` to `.env` and fill in your credentials.

- `AI_API_KEY`: Your AI provider API key.
- `TELEGRAM_BOT_TOKEN`: Get from BotFather.
- `THREADS_ACCESS_TOKEN`: Get from Meta App Dashboard.

3. **Database Setup**

By default, it uses SQLite for local development. Tables are auto-created on startup.

4. **Run the Server**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Telegram Webhook Setup

To receive inline button clicks, set your webhook URL:

```bash
curl -F "url=https://YOUR_DOMAIN/api/approval/webhook" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
```

_(Note: Use ngrok for local testing)._

## Running Jobs Manually

You can run the jobs via Telegram commands:

- `/ideate`: Generate new post ideas
- `/generate`: Write drafts for pending ideas
- `/publish`: Publish approved drafts to Threads
- `/schedule`: View or change job schedules

## Safety Policy

The system enforces strict safety rules via `app/prompts/safety_checker.md`. It will automatically reject drafts containing:

- Confidential company data
- Client names or phone numbers
- Exact revenue or leads count
- Passwords or API keys
- Direct attacks on competitors