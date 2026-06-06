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
        await asyncio.sleep(5)
        
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

    words = text.split(' ')
    chunks = []
    current_chunk = []
    current_length = 0
    max_chars = 500

    for word in words:
        word_len = len(word)
        space_cost = 1 if current_chunk else 0

        if current_length + word_len + space_cost > max_chars:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_len
        else:
            current_chunk.append(word)
            current_length += word_len + space_cost

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    parent_id = None
    for i, chunk in enumerate(chunks):
        if i > 0:
            print(f"⌛ Sleeping 10 seconds to respect Meta's rate limits before starting chunk {i+1}/{len(chunks)}...")
            await asyncio.sleep(10)

        print(f"📝 Publishing chunk {i+1}/{len(chunks)}...")
        if i == 0:
            parent_id = await create_and_publish_container(chunk)
        else:
            await create_and_publish_container(chunk, reply_to_id=parent_id)
            
    return parent_id