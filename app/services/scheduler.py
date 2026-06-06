from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.jobs.generate_ideas import run_ideation
from app.jobs.generate_daily_drafts import run_generation
from app.jobs.publish_approved_posts import run_publisher
from app.jobs.refresh_threads_token import refresh_long_lived_token
from app.db import SessionLocal
from app.models import AppConfig

# Initialize the scheduler
scheduler = AsyncIOScheduler()

def get_config(key: str, default: str) -> str:
    """
    Load a configuration value from the database with a default fallback.
    """
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter(AppConfig.key == key).first()
        if config:
            return config.value
        return default
    finally:
        db.close()

def set_config(key: str, value: str):
    """
    Save or update a configuration value in the database.
    """
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter(AppConfig.key == key).first()
        if config:
            config.value = value
        else:
            config = AppConfig(key=key, value=value)
            db.add(config)
        db.commit()
    finally:
        db.close()

def setup_scheduler():
    """
    Configures and starts the background jobs.
    Loads scheduled hours dynamically from database configuration.
    """
    ideate_hour = get_config("schedule_ideate_hour", "12")
    generate_hour = get_config("schedule_generate_hour", "1")
    publish_hour = get_config("schedule_publish_hour", "3,9")

    # 1. Generate new ideas every day
    scheduler.add_job(
        run_ideation,
        trigger=CronTrigger(hour=ideate_hour, minute=0),
        id="generate_ideas",
        name="Generate Post Ideas",
        replace_existing=True
    )

    # 2. Generate new drafts every day
    scheduler.add_job(
        run_generation,
        trigger=CronTrigger(hour=generate_hour, minute=0),
        id="generate_daily_drafts",
        name="Generate AI Drafts",
        replace_existing=True
    )

    # 3. Publish approved posts every day
    scheduler.add_job(
        run_publisher,
        trigger=CronTrigger(hour=publish_hour, minute=0),
        id="publish_approved_posts",
        name="Publish Approved Posts to Threads",
        replace_existing=True
    )

    # 4. Refresh Threads Token on the 1st and 30th of every month at 02:00 AM
    # (Tokens expire in 60 days, so once a month is very safe)
    scheduler.add_job(
        refresh_long_lived_token,
        trigger=CronTrigger(day="1,30", hour=2, minute=0),
        id="refresh_threads_token",
        name="Refresh Threads Access Token",
        replace_existing=True
    )

    scheduler.start()
    print("Scheduler started successfully. Background jobs are active.")

def update_job_schedule(job_id: str, hour_str: str):
    """
    Updates the schedule of an active job and saves it to the database.
    """
    config_keys = {
        "generate_ideas": "schedule_ideate_hour",
        "generate_daily_drafts": "schedule_generate_hour",
        "publish_approved_posts": "schedule_publish_hour"
    }

    key = config_keys.get(job_id)
    if not key:
        raise ValueError("Invalid job ID")
    
    set_config(key, hour_str)

    try:
        scheduler.reschedule_job(
            job_id,
            trigger=CronTrigger(hour=hour_str, minute=0)
        )
    except Exception as e:
        print(f"Note: Saved to database, but could not dynamically reschedule: {e}")

def shutdown_scheduler():
    """Gracefully shuts down the scheduler."""
    scheduler.shutdown()
    print("Scheduler shut down.")