import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ThreadPostDraft, ThreadPostLog
from app.services.threads_client import publish_to_threads
from app.config import settings

async def run_publisher():
    db: Session = SessionLocal()
    try:
        # Find approved drafts
        query = db.query(ThreadPostDraft).filter(ThreadPostDraft.status == "approved")
        
        # If AUTO_PUBLISH is true, also pick up drafts that meet the threshold but aren't explicitly approved yet
        if settings.AUTO_PUBLISH:
            auto_query = db.query(ThreadPostDraft).filter(
                ThreadPostDraft.status == "draft",
                ThreadPostDraft.score_safety >= 9,
                ThreadPostDraft.score_style >= 7
            )
            drafts = query.all() + auto_query.all()
        else:
            drafts = query.all()

        for draft in drafts:
            print(f"Publishing draft {draft.id}...")
            try:
                post_id = await publish_to_threads(draft.content)
                draft.status = "published"
                draft.published_at = datetime.utcnow()
                draft.threads_post_id = post_id
                
                db.add(ThreadPostLog(draft_id=draft.id, action="published", detail=f"Threads ID: {post_id}"))
                db.commit()
                print(f"Successfully published draft {draft.id}")
            except Exception as e:
                draft.status = "failed"
                db.add(ThreadPostLog(draft_id=draft.id, action="publish_failed", detail=str(e)))
                db.commit()
                print(f"Failed to publish draft {draft.id}: {e}")
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_publisher())