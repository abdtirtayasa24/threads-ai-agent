from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import engine, Base
from app.routes import approval, drafts, auth_threads
from app.services.scheduler import setup_scheduler, shutdown_scheduler

# Create tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(title="Threads AI Agent API", version="0.1.0", lifespan=lifespan)

app.include_router(approval.router)
app.include_router(drafts.router)
app.include_router(auth_threads.router)

@app.get("/")
def read_root():
    return {"status": "online", "agent": "Abdul Fatah Tirtayasa Persona"}

@app.post("/api/jobs/ideate")
async def trigger_ideation():
    """Endpoint to manually trigger the ideation job."""
    from app.jobs.generate_ideas import run_ideation
    import asyncio
    asyncio.create_task(run_ideation())
    return {"message": "Ideation job started in background"}

@app.post("/api/jobs/generate")
async def trigger_generation():
    """Endpoint to manually trigger the generation job."""
    from app.jobs.generate_daily_drafts import run_generation
    import asyncio
    asyncio.create_task(run_generation())
    return {"message": "Generation job started in background"}

@app.post("/api/jobs/publish")
async def trigger_publish():
    """Endpoint to manually trigger the publish job."""
    from app.jobs.publish_approved_posts import run_publisher
    import asyncio
    asyncio.create_task(run_publisher())
    return {"message": "Publish job started in background"}