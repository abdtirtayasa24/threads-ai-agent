import uuid
from fastapi import APIRouter, Request, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import httpx

from app.db import get_db
from app.models import ThreadPostDraft, ThreadPostLog
from app.services.telegram_approval import send_telegram_message
from app.config import settings

from app.jobs.generate_ideas import run_ideation
from app.jobs.generate_daily_drafts import run_generation
from app.jobs.publish_approved_posts import run_publisher

router = APIRouter(prefix="/api/approval", tags=["Approval"])

@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Handles inline button clicks and commands from Telegram."""
    data = await request.json()
    
    # 1 . Handle Callback Queries (Inline Buttons)
    if "callback_query" in data:
        callback = data["callback_query"]
        callback_data = callback["data"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        
        action, draft_id_str = callback_data.split("_")
        try:
            draft_uuid = uuid.UUID(draft_id_str)
        except ValueError:
            return {"status": "error", "message": "Invalid UUID format"}
        
        draft = db.query(ThreadPostDraft).filter(ThreadPostDraft.id == draft_uuid).first()
        
        if not draft:
            return {"status": "error", "message": "Draft not found"}

        response_text = ""
        if action == "approve":
            draft.status = "approved"
            draft.approved_at = datetime.utcnow()
            response_text = "✅ Draft Approved! It will be published by the scheduler."
        elif action == "reject":
            draft.status = "rejected"
            response_text = "❌ Draft Rejected."
        elif action == "regenerate":
            draft.status = "pending_regeneration"
            response_text = "🔄 Draft marked for regeneration."

        db.add(ThreadPostLog(draft_id=draft.id, action=action, detail="Triggered via Telegram"))
        db.commit()

        # Edit message to remove buttons
        edit_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
        async with httpx.AsyncClient() as client:
            await client.post(edit_url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"{callback['message']['text']}\n\n*{response_text}*",
                "parse_mode": "Markdown"
            })

    # 2. Handle Standard Messages (Commands)
    elif "message" in data and "text" in data["message"]:
        message = data["message"]
        text = message["text"].strip()
        chat_id = str(message["chat"]["id"])

        if chat_id != str(settings.TELEGRAM_CHAT_ID):
            return {"status": "ignored", "reason": "Unauthorized chat"}
        
        if text.startswith("/ideate"):
            background_tasks.add_task(run_ideation)
            await send_telegram_message("💡 *Ideation job started.* I am brainstorming new topics...", chat_id)

        elif text.startswith("/generate"):
            background_tasks.add_task(run_generation)
            await send_telegram_message("✍️ *Generation job started.* I am writing drafts for pending ideas...", chat_id)

        elif text.startswith("/publish"):
            background_tasks.add_task(run_publisher)
            await send_telegram_message("🚀 *Publish job started.* I am pushing approved drafts to Threads...", chat_id)
            
    return {"status": "ok"}