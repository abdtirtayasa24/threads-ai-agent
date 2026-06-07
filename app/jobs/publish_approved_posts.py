import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ThreadPostDraft, ThreadPostLog
from app.services.threads_client import publish_to_threads
from app.services.telegram_approval import send_telegram_message
from app.services.illustration_generator import generate_and_watermark_image
from app.config import settings

async def run_publisher(chat_id: str = None):
    """
    Publishes exactly one draft to Threads (FIFO queue behavior).
    Prioritizes user-approved drafts, then falls back to auto-publish-eligible drafts.
    """
    db: Session = SessionLocal()
    try:
        # Find approved drafts
        draft = draft = db.query(ThreadPostDraft)\
            .filter(ThreadPostDraft.status == "approved")\
            .order_by(ThreadPostDraft.created_at.asc())\
            .first()
        
        # If none, and AUTO_PUBLISH is true, look for high-scoring drafts
        if not draft and settings.AUTO_PUBLISH:
            draft = db.query(ThreadPostDraft)\
                .filter(
                    ThreadPostDraft.status == "draft",
                    ThreadPostDraft.score_safety >= 9,
                    ThreadPostDraft.score_style >= 7
                )\
                .order_by(ThreadPostDraft.created_at.asc())\
                .first()

        if not draft:
            await send_telegram_message("ℹ️ *Publish Job Done:*\nNo approved or eligible drafts found ready to be published.", chat_id)
            return
        
        image_public_url = None
        if settings.GENERATE_ILLUSTRATIONS:
            await send_telegram_message("🎨 Generating custom illustration for the post...", chat_id)
            image_public_url = await generate_and_watermark_image(str(draft.id), draft.content)
        
        print(f"Publishing draft {draft.id} to Threads...")
        try:
            post_id = await publish_to_threads(draft.content, image_url=image_public_url)
            draft.status = "published"
            draft.published_at = datetime.utcnow()
            draft.threads_post_id = post_id
                
            db.add(ThreadPostLog(draft_id=draft.id, action="published", detail=f"Threads ID: {post_id}"))
            db.commit()
            print(f"Successfully published draft {draft.id}")

            report_msg = (
                f"🚀 *Published 1 Post to Threads!*\n\n"
                f"📝 *Content:*\n"
                f"_{draft.content}_\n\n"
                f"🖼️ *Illustration:* {'Included ✅' if image_public_url else 'None ❌'}\n"
                f"🔗 *Threads Post ID:* `{post_id}`"
            )
            await send_telegram_message(report_msg, chat_id)

        except Exception as e:
            draft.status = "failed"
            db.add(ThreadPostLog(draft_id=draft.id, action="publish_failed", detail=str(e)))
            db.commit()
            print(f"Failed to publish draft {draft.id}: {e}")

            await send_telegram_message(f"❌ *Failed to publish draft {draft.id} to Threads:*\n`{str(e)}`", chat_id)
    
    except Exception as e:
        await send_telegram_message(f"❌ *Publishing Job Failed!*\nError: `{str(e)}`", chat_id)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_publisher())