from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.jobs.generate_ideas import run_ideation
from app.jobs.generate_daily_drafts import run_generation
from app.jobs.publish_approved_posts import run_publisher
from app.jobs.refresh_threads_token import refresh_long_lived_token

# Initialize the scheduler
scheduler = AsyncIOScheduler()

def setup_scheduler():
    """
    Configures and starts the background jobs.
    """
    # 1. Generate new ideas every day at 07:00 AM
    scheduler.add_job(
        run_ideation,
        trigger=CronTrigger(hour=7, minute=0),
        id="generate_ideas",
        name="Generate Post Ideas",
        replace_existing=True
    )

    # 2. Generate new drafts every day at 08:00 AM
    scheduler.add_job(
        run_generation,
        trigger=CronTrigger(hour=8, minute=0),
        id="generate_daily_drafts",
        name="Generate AI Drafts",
        replace_existing=True
    )

    # 3. Publish approved posts every day at 10:00 AM and 04:00 PM
    scheduler.add_job(
        run_publisher,
        trigger=CronTrigger(hour="10,16", minute=0),
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

def shutdown_scheduler():
    """Gracefully shuts down the scheduler."""
    scheduler.shutdown()
    print("Scheduler shut down.")