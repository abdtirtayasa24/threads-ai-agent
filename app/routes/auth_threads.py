from fastapi import APIRouter, BackgroundTasks
from app.jobs.refresh_threads_token import refresh_long_lived_token

router = APIRouter(prefix="/api/auth/threads", tags=["Threads Auth"])

@router.post("/refresh")
async def trigger_token_refresh(background_tasks: BackgroundTasks):
    """
    Manually triggers the Threads token refresh process in the background.
    """
    background_tasks.add_task(refresh_long_lived_token)
    return {"status": "ok", "message": "Token refresh job started in background."}