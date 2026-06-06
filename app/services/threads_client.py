import httpx
from app.config import settings

THREADS_API_BASE = "https://graph.threads.net/v1.0"

async def publish_to_threads(text: str) -> str:
    """
    Publishes text to Threads using the official API pattern:
    1. Create media container
    2. Publish media container
    Returns the published post ID.
    """
    async with httpx.AsyncClient() as client:
        # 1. Create Media Container
        create_url = f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads"
        create_payload = {
            "media_type": "TEXT",
            "text": text,
            "access_token": settings.THREADS_ACCESS_TOKEN
        }
        create_res = await client.post(create_url, data=create_payload)
        create_res.raise_for_status()
        container_id = create_res.json().get("id")

        if not container_id:
            raise Exception("Failed to create Threads media container")

        # 2. Publish Media Container
        publish_url = f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": settings.THREADS_ACCESS_TOKEN
        }
        publish_res = await client.post(publish_url, data=publish_payload)
        publish_res.raise_for_status()
        
        return publish_res.json().get("id")