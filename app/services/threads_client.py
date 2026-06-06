import re
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
    """
    Paragraph-aware splitter for Threads.

    - Preserves paragraph breaks.
    - Does not cut words.
    - Splits long paragraphs safely by words.
    """
    def split_long_text_preserve_words(value: str) -> list[str]:
        tokens = re.findall(r"\S+\s*", value)
        parts: list[str] = []
        current = ""

        for token in tokens:
            candidate = current + token

            if len(candidate.rstrip()) <= max_chars:
                current = candidate
            else:
                if current.strip():
                    parts.append(current.rstrip())
                current = token

        if current.strip():
            parts.append(current.rstrip())

        return parts

    blocks = re.split(r"(\n+)", text.strip())
    chunks: list[str] = []
    current = ""

    for block in blocks:
        if not block:
            continue

        if re.fullmatch(r"\n+", block):
            candidate = current + block

            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.rstrip())
                current = ""
            continue

        block_parts = (
            split_long_text_preserve_words(block)
            if len(block) > max_chars
            else [block]
        )

        for part in block_parts:
            candidate = part if not current else current + part

            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.rstrip())
                current = part

    if current.strip():
        chunks.append(current.rstrip())

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