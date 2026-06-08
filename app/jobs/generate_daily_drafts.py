import asyncio
import uuid
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ThreadPostIdea, ThreadPostDraft, ThreadPostLog, ThreadPostImage
from app.services.ai_generator import generate_draft
from app.services.illustration_generator import generate_carousel_images
from app.services.safety_checker import check_safety
from app.services.style_checker import check_style
from app.services.telegram_approval import send_draft_for_approval, send_telegram_message
from app.config import settings

async def generate_and_store_draft_images(db: Session, draft: ThreadPostDraft) -> list[str]:
    if not settings.GENERATE_ILLUSTRATIONS:
        return []

    generated_images = await generate_carousel_images(str(draft.id), draft.content)
    image_urls = []

    for item in generated_images:
        image = ThreadPostImage(
            draft_id=draft.id,
            image_url=item["image_url"],
            position=item["position"],
            headline=item.get("headline"),
            caption_text=item.get("caption_text"),
            prompt=item.get("prompt"),
        )
        db.add(image)
        image_urls.append(item["image_url"])

    db.commit()
    return image_urls


async def regenerate_draft(draft_id: uuid.UUID, chat_id: str = None):
    db: Session = SessionLocal()
    try:
        old_draft = db.query(ThreadPostDraft).filter(ThreadPostDraft.id == draft_id).first()
        if not old_draft:
            await send_telegram_message("❌ *Regeneration Failed:* Draft not found.", chat_id)
            return

        idea = db.query(ThreadPostIdea).filter(ThreadPostIdea.id == old_draft.idea_id).first()
        if not idea:
            old_draft.status = "failed"
            old_draft.rejection_reason = "Regeneration failed: idea not found"
            db.commit()
            await send_telegram_message("❌ *Regeneration Failed:* Original idea not found.", chat_id)
            return

        print(f"Regenerating draft for idea: {idea.topic}")
        content = generate_draft(idea.topic, idea.angle)

        safety = check_safety(content)
        style = check_style(content)

        new_draft = ThreadPostDraft(
            idea_id=idea.id,
            content=content,
            score_safety=safety["score"],
            score_style=style["score"],
            rejection_reason=safety.get("reason") if safety["score"] < 9 else None,
            status="draft"
        )
        db.add(new_draft)
        db.commit()
        db.refresh(new_draft)

        old_draft.status = "regenerated"
        image_urls = await generate_and_store_draft_images(db, new_draft)

        db.add(ThreadPostLog(draft_id=old_draft.id, action="regenerated", detail=f"New draft: {new_draft.id}"))
        db.add(ThreadPostLog(draft_id=new_draft.id, action="generated", detail=f"Regenerated from draft {old_draft.id}. Safety: {safety['score']}, Style: {style['score']}"))
        db.commit()

        await send_draft_for_approval(new_draft.id, content, safety["score"], style["score"], chat_id, image_urls)
        print(f"Regenerated draft {new_draft.id} sent for approval.")

    except Exception as e:
        try:
            draft = db.query(ThreadPostDraft).filter(ThreadPostDraft.id == draft_id).first()
            if draft:
                draft.status = "failed"
                draft.rejection_reason = f"Regeneration failed: {str(e)}"
                db.commit()
        finally:
            await send_telegram_message(f"❌ *Regeneration Failed!*\nError: `{str(e)}`", chat_id)
    finally:
        db.close()


async def run_generation(chat_id: str = None):
    db: Session = SessionLocal()
    try:
        # Get pending ideas
        ideas = db.query(ThreadPostIdea).filter(ThreadPostIdea.status == "pending").limit(3).all()
        
        if not ideas:
            print("No pending ideas found in the database.")
            await send_telegram_message("ℹ️ *Generation Job Done:*\nNo pending ideas found to draft. Run `/ideate` first!", chat_id)
            return

        for idea in ideas:
            print(f"Generating draft for idea: {idea.topic}")
            content = generate_draft(idea.topic, idea.angle)
            
            safety = check_safety(content)
            style = check_style(content)
            
            draft = ThreadPostDraft(
                idea_id=idea.id,
                content=content,
                score_safety=safety["score"],
                score_style=style["score"],
                rejection_reason=safety.get("reason") if safety["score"] < 9 else None,
                status="draft"
            )
            db.add(draft)
            db.commit()
            db.refresh(draft)
            
            image_urls = await generate_and_store_draft_images(db, draft)

            db.add(ThreadPostLog(draft_id=draft.id, action="generated", detail=f"Safety: {safety['score']}, Style: {style['score']}"))
            idea.status = "drafted"
            db.commit()
            
            # Send to Telegram
            await send_draft_for_approval(draft.id, content, safety["score"], style["score"], chat_id, image_urls)
            print(f"Draft {draft.id} sent for approval.")

    except Exception as e:
        await send_telegram_message(f"❌ *Generation Job Failed!*\nError: `{str(e)}`", chat_id)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_generation())