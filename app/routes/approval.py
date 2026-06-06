from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.db import get_db
from app.models import ThreadPostDraft, ThreadPostLog
import httpx
from app.config import settings

router = APIRouter(prefix="/api/approval", tags=["Approval"])

@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Handles inline button clicks from Telegram."""
    data = await request.json()
    
    if "callback_query" in data:
        callback = data["callback_query"]
        callback_data = callback["data"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        
        action, draft_id = callback_data.split("_")
        draft = db.query(ThreadPostDraft).filter(ThreadPostDraft.id == int(draft_id)).first()
        
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
            
    return {"status": "ok"}