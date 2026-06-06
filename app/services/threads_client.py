import httpx
import asyncio
from app.config import settings

THREADS_API_BASE = "https://graph.threads.net/v1.0"

async def create_and_publish_container(text: str, reply_to_id: str = None) -> str:
    """Handle the 2-step Container -> Publish flow for a single post."""
    async with httpx.AsyncClient() as client:
        create_url = f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads"
        create_payload = {
            "media_type": "TEXT",
            "text": text,
            "access_token": settings.THREADS_ACCESS_TOKEN
        }
        if reply_to_id:
            create_payload["reply_to_id"] = reply_to_id

        create_res = await client.post(create_url, data=create_payload)
        if create_res.status_code != 200:
            print(f"Threads API Container Error: {create_res.text}")
            create_res.raise_for_status()
            
        container_id = create_res.json().get("id")

        publish_url = f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": settings.THREADS_ACCESS_TOKEN
        }
        await asyncio.sleep(2) 
        
        publish_res = await client.post(publish_url, data=publish_payload)
        if publish_res.status_code != 200:
            print(f"Threads API Publish Error: {publish_res.text}")
            publish_res.raise_for_status()
            
        return publish_res.json().get("id")

async def publish_to_threads(text: str) -> str:
    """
    Main entrypoint. Automatically splits text exceeding 500 characters
    into paragraphs and posts them as a nested Thread (reply chain).
    """
    if len(text.encode('utf-8')) <= 500:
        return await create_and_publish_container(text)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    parent_id = None
    for i, paragraph in enumerate(paragraphs):
        thread_prefix = f"({i+1}/{len(paragraphs)}) "
        chunk = thread_prefix + paragraph
        
        if len(chunk.encode('utf-8')) > 500:
            chunk = chunk.encode('utf-8')[:490].decode('utf-8', errors='ignore') + "..."
            
        if i == 0:
            parent_id = await create_and_publish_container(chunk)
        else:
            await create_and_publish_container(chunk, reply_to_id=parent_id)
            
    return parent_id