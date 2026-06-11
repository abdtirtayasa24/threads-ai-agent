import re
import httpx
import asyncio
from app.config import settings

THREADS_API_BASE = "https://graph.threads.net/v1.0"
async def create_threads_container(
        client: httpx.AsyncClient,
        text: str | None = None,
        reply_to_id: str | None = None,
        image_url: str | None = None,
        image_urls: list[str] | None = None,
        is_carousel_item: bool = False,
    ) -> str:
    create_url = f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads"
    create_payload = {
        "access_token": settings.THREADS_ACCESS_TOKEN
    }

    if image_urls:
        create_payload["media_type"] = "CAROUSEL"
        create_payload["children"] = ",".join(image_urls)
        if text:
            create_payload["text"] = text
    elif image_url:
        create_payload["media_type"] = "IMAGE"
        create_payload["image_url"] = image_url
        if text:
            create_payload["text"] = text
        if is_carousel_item:
            create_payload["is_carousel_item"] = "true"
    else:
        create_payload["media_type"] = "TEXT"
        create_payload["text"] = text or ""

    if reply_to_id:
        create_payload["reply_to_id"] = reply_to_id

    create_res = await client.post(create_url, data=create_payload)
    if create_res.status_code != 200:
        print(f"Threads API Container Error: {create_res.text}")
        create_res.raise_for_status()
        
    container_id = create_res.json().get("id")
    if not container_id:
        raise RuntimeError(f"Threads API did not return container id: {create_res.text}")

    media_type = create_payload.get("media_type")
    print(f"Threads container created | media_type={media_type} | is_carousel_item={is_carousel_item} | id={container_id}")
    return container_id

async def create_carousel_parent_with_retry(
        client: httpx.AsyncClient,
        text: str,
        reply_to_id: str | None,
        child_container_ids: list[str],
        max_attempts: int = 6,
        delay_seconds: int = 10,
    ) -> str:
    """Create carousel parent after child containers have had time to process.

    Threads does not expose the Instagram-style `status_code` field for media
    containers, so readiness is handled by retrying parent creation.
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            await asyncio.sleep(delay_seconds)

        try:
            print(f"Creating Threads carousel parent attempt {attempt}/{max_attempts} | children={child_container_ids}")
            return await create_threads_container(
                client,
                text=text,
                reply_to_id=reply_to_id,
                image_urls=child_container_ids,
            )
        except httpx.HTTPStatusError as e:
            last_error = e
            status_code = e.response.status_code if e.response is not None else "unknown"
            body = e.response.text if e.response is not None else ""
            print(f"Threads carousel parent create failed attempt {attempt}/{max_attempts} | status={status_code}")
            print(body)

    raise last_error or RuntimeError("Threads carousel parent creation failed")

async def publish_threads_container(client: httpx.AsyncClient, container_id: str) -> str:
    publish_url = f"{THREADS_API_BASE}/{settings.THREADS_USER_ID}/threads_publish"
    publish_payload = {
        "creation_id": container_id,
        "access_token": settings.THREADS_ACCESS_TOKEN
    }

    publish_res = None
    for attempt in range(1, 4):
        await asyncio.sleep(5 * attempt)

        publish_res = await client.post(publish_url, data=publish_payload)
        if publish_res.status_code == 200:
            break

        print(f"Threads API Publish Error attempt {attempt}/3:")
        print(publish_res.text)

    if publish_res is None or publish_res.status_code != 200:
        if publish_res is not None:
            publish_res.raise_for_status()
        raise RuntimeError("Threads publish failed without response")

    post_id = publish_res.json().get("id")
    if not post_id:
        raise RuntimeError(f"Threads API did not return published post id: {publish_res.text}")
        
    return post_id

async def create_and_publish_container(
        text: str,
        reply_to_id: str | None = None,
        image_url: str | None = None,
        image_urls: list[str] | None = None,
    ) -> str:
    """
    Create a Threads container, publish it, and return the published post ID.

    - If image_urls has multiple items: create a carousel post with text as caption.
    - If image_url is provided: create IMAGE post with text as caption.
    - If no image is provided: create TEXT post.
    - reply_to_id must be the published post ID, not container ID.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        if image_urls and len(image_urls) > 1:
            child_container_ids = []
            for index, url in enumerate(image_urls, start=1):
                child_container_id = await create_threads_container(
                    client,
                    image_url=url,
                    is_carousel_item=True,
                )
                child_container_ids.append(child_container_id)
                print(f"Waiting briefly after carousel child {index}/{len(image_urls)} creation...")
                await asyncio.sleep(5)

            container_id = await create_carousel_parent_with_retry(
                client,
                text=text,
                reply_to_id=reply_to_id,
                child_container_ids=child_container_ids,
            )
        else:
            single_image_url = image_url or (image_urls[0] if image_urls else None)
            container_id = await create_threads_container(
                client,
                text=text,
                reply_to_id=reply_to_id,
                image_url=single_image_url,
            )

        return await publish_threads_container(client, container_id)
    
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

async def publish_to_threads(text: str, image_url: str | None = None, image_urls: list[str] | None = None) -> str:
    """
    Split long text into chunks and publish as a reply chain.
    Images are attached only to the first chunk.
    Returns the last published post ID.
    """
    chunks = split_text_for_threads(text, max_chars=480)
    image_urls = image_urls or ([] if image_url is None else [image_url])

    parent_id = None
    for i, chunk in enumerate(chunks, start=1):
        if i > 1:
            print(f"⌛ Sleeping 10 seconds before chunk {i}/{len(chunks)}...")
            await asyncio.sleep(10)

        chunk_image_urls = image_urls if i == 1 else []

        print(
            f"📝 Publishing chunk {i}/{len(chunks)} | "
            f"chars={len(chunk)} | "
            f"reply_to_id={parent_id} | "
            f"images={len(chunk_image_urls)}"
        )

        parent_id = await create_and_publish_container(
            text=chunk,
            reply_to_id=parent_id,
            image_urls=chunk_image_urls,
        )

        print(f"✅ Published chunk {i}/{len(chunks)} | post_id={parent_id}")

    return parent_id
