import html
import uuid
from fastapi import APIRouter, Request, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import httpx

from app.db import get_db
from app.models import ThreadPostDraft, ThreadPostLog, ThreadPostIdea, ThreadPostImage
from app.services.pdf_carousel_generator import generate_linkedin_carousel_pdf
from app.services.telegram_approval import send_telegram_html, send_telegram_message
from app.services.scheduler import update_job_schedule, get_config
from app.config import settings

from app.jobs.generate_ideas import count_approved_unpublished_drafts, run_ideation, idea_key
from app.jobs.generate_daily_drafts import generate_carousel_for_draft, regenerate_carousel_slide, run_generation, regenerate_draft
from app.jobs.publish_approved_posts import run_publisher

router = APIRouter(prefix="/api/approval", tags=["Approval"])


def short_text(value: str | None, max_length: int = 120) -> str:
    value = " ".join((value or "").split())
    if len(value) <= max_length:
        return value
    return value[:max_length - 1].rstrip() + "…"


def short_source_note(value: str | None) -> str:
    value = (value or "").lower()
    if "human" in value:
        return "Human"
    return "Agent"


def format_dt(value) -> str:
    return value.isoformat(sep=" ", timespec="minutes") if value else "-"


async def send_post_report(db: Session, chat_id: str, status: str):
    timestamp_column = ThreadPostDraft.published_at if status == "published" else ThreadPostDraft.approved_at
    query = db.query(ThreadPostDraft, ThreadPostIdea)\
        .join(ThreadPostIdea, ThreadPostDraft.idea_id == ThreadPostIdea.id)\
        .filter(ThreadPostDraft.status == status)\
        .order_by(timestamp_column.desc())

    if status == "published":
        query = query.limit(5)

    rows = query.all()
    title = "Published posts" if status == "published" else "Approved unpublished posts"
    if not rows:
        await send_telegram_html(f"<b>{title}</b>\n\nNo records found.", chat_id)
        return

    lines = [f"<b>{html.escape(title)}</b>", "<pre>"]
    for index, (draft, idea) in enumerate(rows, start=1):
        timestamp = draft.published_at if status == "published" else draft.approved_at
        lines.extend([
            f"{index}. topic: {html.escape(short_text(idea.topic, 80))}",
            f"   content: {html.escape(short_text(draft.content))}",
            f"   {status}_at: {html.escape(format_dt(timestamp))}",
            ""
        ])
    lines.append("</pre>")
    await send_telegram_html("\n".join(lines), chat_id)


async def send_ideas_report(db: Session, chat_id: str, status: str):
    rows = db.query(ThreadPostIdea)\
        .filter(ThreadPostIdea.status == status)\
        .order_by(ThreadPostIdea.created_at.desc())\
        .limit(5)\
        .all()

    title = f"{status.title()} ideas"
    if not rows:
        await send_telegram_html(f"<b>{html.escape(title)}</b>\n\nNo records found.", chat_id)
        return

    lines = [f"<b>{html.escape(title)}</b>", "<pre>"]
    for index, idea in enumerate(rows, start=1):
        lines.extend([
            f"{index}. topic: {html.escape(short_text(idea.topic, 80))}",
            f"   angle: {html.escape(short_text(idea.angle))}",
            f"   source: {html.escape(short_source_note(idea.source_note))}",
            f"   created_at: {html.escape(format_dt(idea.created_at))}",
            ""
        ])
    lines.append("</pre>")
    await send_telegram_html("\n".join(lines), chat_id)


async def send_image_prompt_report(db: Session, chat_id: str, topic: str):
    if not topic:
        await send_telegram_html("<b>Invalid syntax.</b> Use: <code>/image-prompt &lt;topic&gt;</code>", chat_id)
        return

    rows = db.query(ThreadPostImage, ThreadPostDraft, ThreadPostIdea)\
        .join(ThreadPostDraft, ThreadPostImage.draft_id == ThreadPostDraft.id)\
        .join(ThreadPostIdea, ThreadPostDraft.idea_id == ThreadPostIdea.id)\
        .filter(
            ThreadPostDraft.status == "published",
            ThreadPostIdea.topic.ilike(f"%{topic}%")
        )\
        .order_by(ThreadPostDraft.published_at.desc(), ThreadPostImage.position.asc())\
        .limit(10)\
        .all()

    if not rows:
        await send_telegram_html(f"<b>Image prompts</b>\n\nNo published records found for topic: <code>{html.escape(topic)}</code>", chat_id)
        return

    lines = [f"<b>Image prompts for: {html.escape(topic)}</b>", "<pre>"]
    for index, (image, draft, idea) in enumerate(rows, start=1):
        lines.extend([
            f"{index}. topic: {html.escape(short_text(idea.topic, 80))}",
            f"   position: {image.position}",
            f"   prompt: {html.escape(short_text(image.prompt, 220))}",
            f"   image_url: {html.escape(image.image_url)}",
            ""
        ])
    lines.append("</pre>")
    await send_telegram_html("\n".join(lines), chat_id)


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
        
        if callback_data == "ideateforce":
            background_tasks.add_task(run_ideation, str(chat_id), True)
            response_text = "💡 Ideation started. I am brainstorming new topics..."

            edit_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
            async with httpx.AsyncClient() as client:
                await client.post(edit_url, json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": f"{callback['message']['text']}\n\n*{response_text}*",
                    "parse_mode": "Markdown"
                })
            return {"status": "ok"}

        if callback_data == "ideatecancel":
            response_text = "❌ Ideation cancelled."

            edit_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
            async with httpx.AsyncClient() as client:
                await client.post(edit_url, json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": f"{callback['message']['text']}\n\n*{response_text}*",
                    "parse_mode": "Markdown"
                })
            return {"status": "ok"}

        if callback_data.startswith("slideregen_"):
            payload = callback_data[len("slideregen_"):]
            draft_id_str, position_str = payload.rsplit("_", 1)
            try:
                draft_uuid = uuid.UUID(draft_id_str)
                position = int(position_str)
            except ValueError:
                return {"status": "error", "message": "Invalid slide regeneration callback"}

            background_tasks.add_task(regenerate_carousel_slide, draft_uuid, position, str(chat_id))
            await send_telegram_message(f"🔄 Regenerating carousel slide {position}...", str(chat_id))
            return {"status": "ok"}

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

            try:
                images = db.query(ThreadPostImage)\
                    .filter(ThreadPostImage.draft_id == draft.id)\
                    .order_by(ThreadPostImage.position.asc())\
                    .all()
                image_urls = [image.image_url for image in images]
                pdf_url = generate_linkedin_carousel_pdf(draft.id, image_urls)
                response_text += f"\n\n📄 LinkedIn carousel PDF ready:\n{pdf_url}"
            except Exception as e:
                response_text += f"\n\n⚠️ LinkedIn PDF generation failed: `{str(e)}`"
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

        message_parts = text.split(maxsplit=1)
        normalized_command = message_parts[0].lstrip("/").replace("-", "").lower()
        command_arg = message_parts[1].strip() if len(message_parts) > 1 else ""
        
        if text.startswith("/ideate"):
            approved_drafts_count = count_approved_unpublished_drafts(db)
            if approved_drafts_count >= 2:
                warning_text = (
                    f"⚠️ *Backlog Warning*\n\n"
                    f"You still have {approved_drafts_count} approved post drafts waiting to be published.\n"
                    f"Generating more ideas may create too much backlog.\n\n"
                    f"Do you still want to generate new ideas?"
                )
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Keep Generate Ideas", "callback_data": "ideateforce"},
                            {"text": "❌ Cancel", "callback_data": "ideatecancel"}
                        ]
                    ]
                }
                url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={
                        "chat_id": chat_id,
                        "text": warning_text,
                        "parse_mode": "Markdown",
                        "reply_markup": keyboard
                    })
                return {"status": "ok"}

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

        elif normalized_command == "postapproved":
            await send_post_report(db, chat_id, "approved")

        elif normalized_command == "postpublished":
            await send_post_report(db, chat_id, "published")

        elif normalized_command == "ideaspending":
            await send_ideas_report(db, chat_id, "pending")

        elif normalized_command == "ideasdrafted":
            await send_ideas_report(db, chat_id, "drafted")

        elif normalized_command == "imageprompt":
            await send_image_prompt_report(db, chat_id, command_arg)

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