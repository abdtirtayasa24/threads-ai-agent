import httpx
import asyncio
from app.config import settings

THREADS_API_BASE = "https://graph.threads.net/v1.0"

async def create_and_publish_container(text: str, reply_to_id: str | None = None) -> str:
    """Create a Threads text container, publish it, and return the published post ID."""
    async with httpx.AsyncClient(timeout=30) as client:
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
        if not container_id:
            raise RuntimeError(f"Threads API did not return container id: {create_res.text}")

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

        post_id = publish_res.json().get("id")
        if not post_id:
            raise RuntimeError(f"Threads API did not return published post id: {publish_res.text}")
            
        return post_id
    
def split_text_for_threads(text: str, max_chars: int = 480) -> list[str]:
    """Split text into safe Threads chunks under max_chars."""
    words = text.split()
    chunks: list[str] = []
    current_words: list[str] = []
    current_length = 0

    for word in words:
        word_length = len(word)
        
        if word_length > max_chars:
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = []
                current_length = 0

            chunks.append(word)
            continue

        space_cost = 1 if current_words else 0
        candidate_length = current_length + space_cost + word_length

        if candidate_length <= max_chars:
            current_words.append(word)
            current_length = candidate_length
        else:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_length = word_length

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks

async def publish_to_threads(text: str) -> str:
    """
    Split long text into chunks and publish as a reply chain.
    Returns the last published post ID.
    """
    chunks = split_text_for_threads(text, max_chars=480)

    parent_id = None
    for i, chunk in enumerate(chunks, start=1):
        if i > 1:
            print(f"⌛ Sleeping 10 seconds before chunk {i}/{len(chunks)}...")
            await asyncio.sleep(10)

        print(f"📝 Publishing chunk {i}/{len(chunks)} | chars={len(chunk)} | reply_to_id={parent_id}")

        parent_id = await create_and_publish_container(
            text=chunk,
            reply_to_id=parent_id,
        )

        print(f"✅ Published chunk {i}/{len(chunks)} | post_id={parent_id}")

    return parent_id