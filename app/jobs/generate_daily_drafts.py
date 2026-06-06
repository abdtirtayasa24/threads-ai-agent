import asyncio
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ThreadPostIdea, ThreadPostDraft, ThreadPostLog
from app.services.ai_generator import generate_draft
from app.services.safety_checker import check_safety
from app.services.style_checker import check_style
from app.services.telegram_approval import send_draft_for_approval

async def run_generation():
    db: Session = SessionLocal()
    try:
        # Get pending ideas
        ideas = db.query(ThreadPostIdea).filter(ThreadPostIdea.status == "pending").limit(3).all()
        
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
            
            db.add(ThreadPostLog(draft_id=draft.id, action="generated", detail=f"Safety: {safety['score']}, Style: {style['score']}"))
            idea.status = "drafted"
            db.commit()
            
            # Send to Telegram
            await send_draft_for_approval(draft.id, content, safety["score"], style["score"])
            print(f"Draft {draft.id} sent for approval.")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_generation())