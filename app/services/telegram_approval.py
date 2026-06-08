import httpx
import uuid
from app.config import settings

async def send_telegram_message(text: str, chat_id: str = None):
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def send_draft_for_approval(draft_id: uuid.UUID, content: str, safety_score: int, style_score: int, chat_id: str = None):
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    
    text = (
        f"📝 *New Draft Ready for Approval*\n\n"
        f"{content}\n\n"
        f"🛡 Safety Score: {safety_score}/10\n"
        f"🎨 Style Score: {style_score}/10\n"
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve_{draft_id}"},
                {"text": "❌ Reject", "callback_data": f"reject_{draft_id}"}
            ],
            [
                {"text": "🔄 Regenerate", "callback_data": f"regenerate_{draft_id}"}
            ]
        ]
    }
    
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)