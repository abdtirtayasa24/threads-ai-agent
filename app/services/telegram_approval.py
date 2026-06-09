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

async def send_telegram_html(text: str, chat_id: str = None):
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def send_carousel_slide_for_review(draft_id: uuid.UUID, image: dict, chat_id: str = None, media_mode: str = "carousel"):
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    position = image.get("position")
    headline = image.get("headline") or ""
    caption_text = image.get("caption_text") or ""
    is_single_image = media_mode == "single_image"
    title = "Image Post" if is_single_image else f"Carousel Slide {position}"
    button_text = "🔄 Regenerate Image" if is_single_image else f"🔄 Regenerate Slide {position}"

    caption = (
        f"🖼️ *{title}*\n"
        f"*Headline:* {headline}\n"
        f"*Caption:* {caption_text}"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": button_text, "callback_data": f"slideregen_{draft_id}_{position}"}
            ]
        ]
    }

    photo_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as client:
        await client.post(photo_url, json={
            "chat_id": target_chat_id,
            "photo": image["image_url"],
            "caption": caption,
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        })

async def send_carousel_for_approval(draft_id: uuid.UUID, images: list[dict], chat_id: str = None, media_mode: str = "carousel"):
    for image in images:
        await send_carousel_slide_for_review(draft_id, image, chat_id, media_mode)

    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    is_single_image = media_mode == "single_image"
    title = "Image Ready for Approval" if is_single_image else "Carousel Ready for Approval"
    description = (
        "Review the generated image for this approved draft."
        if is_single_image
        else "Review the generated carousel images for this approved draft.\nYou can regenerate individual slides above, regenerate the full carousel, approve, or reject."
    )
    approve_text = "✅ Approve Image" if is_single_image else "✅ Approve Carousel"
    reject_text = "❌ Reject Image" if is_single_image else "❌ Reject Carousel"
    regen_text = "🔄 Regenerate Image" if is_single_image else "🔄 Regenerate Full Carousel"

    text = f"🖼️ *{title}*\n\n{description}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": approve_text, "callback_data": f"carouselapprove_{draft_id}"},
                {"text": reject_text, "callback_data": f"carouselreject_{draft_id}"}
            ],
            [
                {"text": regen_text, "callback_data": f"carouselregen_{draft_id}"}
            ]
        ]
    }

    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
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