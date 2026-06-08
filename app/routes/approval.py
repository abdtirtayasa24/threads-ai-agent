import uuid
from fastapi import APIRouter, Request, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import httpx

from app.db import get_db
from app.models import ThreadPostDraft, ThreadPostLog, ThreadPostIdea
from app.services.telegram_approval import send_telegram_message
from app.services.scheduler import update_job_schedule, get_config
from app.config import settings

from app.jobs.generate_ideas import run_ideation, idea_key
from app.jobs.generate_daily_drafts import generate_carousel_for_draft, run_generation, regenerate_draft
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
        
        action, draft_id_str = callback_data.split("_", 1)
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
            draft.carousel_status = "generating"
            response_text = "✅ Draft approved. Generating carousel for review..."
            background_tasks.add_task(generate_carousel_for_draft, draft.id, str(chat_id))
        elif action == "reject":
            draft.status = "rejected"
            response_text = "❌ Draft Rejected."
        elif action == "regenerate":
            draft.status = "pending_regeneration"
            response_text = "🔄 Regeneration started. I’ll send the new draft shortly."
            background_tasks.add_task(regenerate_draft, draft.id, str(chat_id))
        elif action == "carouselapprove":
            draft.carousel_status = "approved"
            draft.carousel_rejection_reason = None
            response_text = "✅ Carousel approved. This post will publish with images."
        elif action == "carouselreject":
            draft.carousel_status = "rejected"
            draft.carousel_rejection_reason = "Rejected via Telegram"
            response_text = "❌ Carousel rejected. This approved post will publish text-only."
        elif action == "carouselregen":
            draft.carousel_status = "generating"
            draft.carousel_rejection_reason = None
            response_text = "🔄 Carousel regeneration started. I’ll send the new images shortly."
            background_tasks.add_task(generate_carousel_for_draft, draft.id, str(chat_id))
        else:
            return {"status": "error", "message": "Invalid callback action"}

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
            background_tasks.add_task(run_ideation, chat_id)
            await send_telegram_message("💡 *Ideation job started.* I am brainstorming new topics...", chat_id)

        elif text.startswith("/addidea"):
            idea_text = text[len("/addidea"):].strip()
            if "|" not in idea_text:
                await send_telegram_message(
                    "❌ *Invalid syntax.* Use:\n`/addidea <topic> | <angle>`\n\nExample:\n`/addidea AI agents for sales ops | Why agents fail when the CRM workflow is unclear`",
                    chat_id
                )
                return

            topic, angle = [part.strip() for part in idea_text.split("|", 1)]
            if not topic or not angle:
                await send_telegram_message(
                    "❌ *Invalid syntax.* Topic and angle are required. Use:\n`/addidea <topic> | <angle>`",
                    chat_id
                )
                return

            new_idea_key = idea_key(topic, angle)
            existing_ideas = db.query(ThreadPostIdea).all()
            if any(idea_key(idea.topic, idea.angle) == new_idea_key for idea in existing_ideas):
                await send_telegram_message("⚠️ *Idea not added.* The same topic and angle already exists in the database.", chat_id)
                return

            idea = ThreadPostIdea(
                topic=topic,
                angle=angle,
                source_note="Generate by Human User",
                status="pending"
            )
            db.add(idea)
            db.commit()

            await send_telegram_message(
                f"✅ *Idea added to database!*\n\n💡 *{topic}*\n_Angle:_ {angle}\n\n👉 Use `/generate` to write a draft for this idea.",
                chat_id
            )

        elif text.startswith("/generate"):
            background_tasks.add_task(run_generation, chat_id)
            await send_telegram_message("✍️ *Generation job started.* I am writing drafts for pending ideas...", chat_id)

        elif text.startswith("/publish"):
            background_tasks.add_task(run_publisher, chat_id)
            await send_telegram_message("🚀 *Publish job started.* I am pushing approved drafts to Threads...", chat_id)

        elif text.startswith("/schedule"):
            parts = text.split()

            if len(parts) == 1:
                ideate_h = get_config("schedule_ideate_hour", "7")
                generate_h = get_config("schedule_generate_hour", "8")
                publish_h = get_config("schedule_publish_hour", "10,16")

                status_msg = (
                    f"⏰ *Active Schedules (UTC+8):*\n\n"
                    f"• *Ideation (/ideate):* Daily at `{ideate_h}:00`\n"
                    f"• *Drafting (/generate):* Daily at `{generate_h}:00`\n"
                    f"• *Publishing (/publish):* Daily at `{publish_h}:00`\n\n"
                    f"👉 *To change a schedule, use:*\n"
                    f"`/schedule <job> <hours>`\n\n"
                    f"Example: `/schedule publish 9,15,21`\n"
                    f"Example: `/schedule generate 7`"
                )
                await send_telegram_message(status_msg, chat_id)

            elif len(parts) == 3:
                _, job_name, hour_str = parts

                job_map = {
                    "ideate": "generate_ideas",
                    "ideas": "generate_ideas",
                    "generate": "generate_daily_drafts",
                    "drafts": "generate_daily_drafts",
                    "publish": "publish_approved_posts",
                    "posts": "publish_approved_posts"
                }

                job_id = job_map.get(job_name.lower())
                if not job_id:
                    await send_telegram_message("❌ *Error:* Invalid job name. Use `ideate`, `generate`, or `publish`.", chat_id)
                    return
                
                try:
                    for h in hour_str.split(","):
                        val = int(h.strip())
                        if not (0 <= val <= 23):
                            raise ValueError()
                except ValueError:
                    await send_telegram_message("❌ *Error:* Invalid hour. Must be a single hour (e.g. `7`) or comma-separated hours (e.g. `10,16`) between 0 and 23.", chat_id)
                    return
                
                try:
                    update_job_schedule(job_id, hour_str)
                    await send_telegram_message(f"✅ *Schedule Updated!*\n`{job_name}` is now scheduled daily at `{hour_str}:00` UTC+8.", chat_id)
                except Exception as e:
                    await send_telegram_message(f"❌ *Failed to update schedule:* `{str(e)}`", chat_id)

            else:
                await send_telegram_message("❌ *Error:* Invalid syntax. Use `/schedule <job> <hours>` or just `/schedule` to view status.", chat_id)
            
    return {"status": "ok"}