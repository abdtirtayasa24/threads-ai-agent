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

async def send_draft_for_approval(draft_id: uuid.UUID, content: str, safety_score: int, style_score: int, chat_id: str = None, image_urls: list[str] | None = None):
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    if image_urls:
        async with httpx.AsyncClient() as client:
            if len(image_urls) == 1:
                photo_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
                await client.post(photo_url, json={
                    "chat_id": target_chat_id,
                    "photo": image_urls[0]
                })
            else:
                media_group_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMediaGroup"
                media = [
                    {"type": "photo", "media": image_url}
                    for image_url in image_urls
                ]
                await client.post(media_group_url, json={
                    "chat_id": target_chat_id,
                    "media": media
                })
    
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