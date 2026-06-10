import os
import re
import uuid
import httpx
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from openai import AsyncOpenAI
from app.config import settings
from app.services.ai_generator import extract_and_parse_json

client = AsyncOpenAI(
    api_key=settings.AI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
    
def safe_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
    return value[:80]

def decode_image_data_url(data_url: str) -> bytes:
    match = re.match(r"^data:image\/[a-zA-Z0-9.+-]+;base64,(.+)$", data_url)

    if not match:
        raise RuntimeError(f"Unexpected OpenRouter image URL format: {data_url[:80]}")

    return base64.b64decode(match.group(1))

async def generate_single_image_plan(content: str) -> dict:
    system_prompt = load_prompt("illustration_single_style.md")

    prompt_res = await client.chat.completions.create(
        model=settings.AI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Create a single image-generation prompt for this post. "
                    "Return only the required JSON format.\n\n"
                    f"{content}"
                )
            }
        ],
        temperature=0.5
    )

    raw_output = prompt_res.choices[0].message.content
    if not raw_output:
        raise RuntimeError("AI did not return a single image plan.")

    plan = extract_and_parse_json(raw_output)
    if not plan.get("prompt"):
        raise RuntimeError(f"AI did not return a single image prompt: {plan}")

    return plan


def flatten_single_image_prompt(plan: dict) -> str:
    headline = plan.get("headline", "")
    caption_text = plan.get("caption_text", "")
    visual_prompt = plan.get("prompt", "")

    text_instruction = ""
    if headline or caption_text:
        text_instruction = f"""
Render this exact headline as readable text if provided:
{headline}

Render this exact supporting text as readable secondary text if provided:
{caption_text}
"""

    return f"""Create one professional Threads image for a single post.
Do not create a carousel.
Do not generate multiple panels or multiple slides.
{text_instruction}

---

## Consistent character requirement:

### Use the same recurring main character:

- young Southeast Asian male tech worker
- medium tan skin
- neat black mustache
- simple dark black hoodie
- calm focused builder/developer appearance
- minimalist anime-style facial features
- no glasses unless explicitly requested
- no beard other than the mustache

### Visual direction:

{visual_prompt}

### Layout requirements:
- Keep the image simple, relatable, and mobile-friendly.
- If there is text, it must be large and readable.
- Do not add extra words, labels, logos, hashtags, or watermarks.
- Generate only this single image."""


async def generate_carousel_plan(content: str) -> dict:
    system_prompt = load_prompt("illustration_style.md")

    prompt_res = await client.chat.completions.create(
        model=settings.AI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Create a self-contained visual carousel plan for this post. "
                    "Return only the required JSON format.\n\n"
                    f"{content}"
                )
            }
        ],
        temperature=0.5
    )

    raw_output = prompt_res.choices[0].message.content
    if not raw_output:
        raise RuntimeError("AI did not return a carousel plan.")

    plan = extract_and_parse_json(raw_output)
    slides = plan.get("slides") or []
    if not isinstance(slides, list) or not slides:
        raise RuntimeError(f"AI did not return carousel slides: {plan}")

    return {"slides": slides[:6]}

def flatten_carousel_slide_prompt(slide: dict) -> str:
    slide_number = slide.get("slide", "")
    role = slide.get("role", "")
    headline = slide.get("headline", "")
    caption_text = slide.get("caption_text", "")
    visual_prompt = slide.get("prompt", "")

    return f"""Create one professional LinkedIn/Threads carousel image for slide {slide_number}.

Slide role: {role}.

Render this exact headline as large, dominant, readable text:
{headline}

Render this exact supporting text as clearly readable secondary text, not tiny:
{caption_text}

---

## Consistent character requirement:

### Use the same recurring main character in this slide:

- young Southeast Asian male tech worker
- medium tan skin
- neat black mustache
- simple dark black hoodie
- calm focused builder/developer appearance
- minimalist anime-style facial features
- no glasses unless explicitly requested
- no beard other than the mustache

### Visual direction:

{visual_prompt}

### Text layout requirements:

- Headline must be the main readable text.
- Supporting text must be large enough to read on mobile.
- Do not add extra words, labels, logos, hashtags, or watermarks.
- Do not generate multiple slides.
- Generate only this single carousel image."""

async def generate_image_from_prompt(draft_id: str, image_prompt: str, position: int | None = None) -> str | None:
    try:
        print(f"🎨 Generating illustration for draft {draft_id}...")
        print(f"🧠 Image prompt: {image_prompt}")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "Threads AI Agent",
        }

        payload = {
            "model": settings.IMAGE_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": image_prompt
                }
            ],
            "modalities": ["image"],
            "temperature": 0.75,
            "stream": False,
            "image_config": {
                "aspect_ratio": "4:3",
                "image_size": "1K"
            }
        }

        async with httpx.AsyncClient(timeout=90.0) as http_client:
            response = await http_client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print("❌ OpenRouter Image API Error:")
            print(response.text)
            return None

        data = response.json()

        message = data["choices"][0]["message"]
        images = message.get("images") or []

        if not images:
            raise RuntimeError(f"No images returned from OpenRouter: {data}")
            
        image_data_url = images[0]["image_url"]["url"]
        image_bytes = decode_image_data_url(image_data_url)

        img = Image.open(BytesIO(image_bytes)).convert("RGBA")

        txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        except Exception:
            try:
                font = ImageFont.load_default(size=36)
            except TypeError:
                font = ImageFont.load_default()

        watermark_text = "@abdtirtayasa24"
        padding = 40

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = img.width - text_width - padding
        y = img.height - text_height - padding

        draw.text((x+2, y+2), watermark_text, font=font, fill=(0, 0, 0, 170))
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 230))

        watermarked_img = Image.alpha_composite(img, txt_layer).convert("RGB")

        suffix = f"-{position}-{uuid.uuid4().hex[:8]}" if position is not None else ""
        filename = f"{safe_filename(draft_id)}{suffix}.jpg"
        filepath = os.path.join("static", "images", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        watermarked_img.save(filepath, "JPEG", quality=90, optimize=True)

        print(f"✅ Illustration saved to {filepath}")
        return f"{settings.BASE_URL.rstrip('/')}/static/images/{filename}"
        
    except Exception as e:
        print(f"❌ Failed to generate illustration: {e}")
        return None

async def generate_single_image(draft_id: str, content: str) -> dict | None:
    try:
        plan = await generate_single_image_plan(content)
        flattened_prompt = flatten_single_image_prompt(plan)
        image_url = await generate_image_from_prompt(draft_id, flattened_prompt, 1)

        if not image_url:
            return None

        return {
            "image_url": image_url,
            "position": 1,
            "headline": plan.get("headline"),
            "caption_text": plan.get("caption_text"),
            "prompt": flattened_prompt,
        }
    except Exception as e:
        print(f"❌ Failed to generate single illustration: {e}")
        return None


async def generate_carousel_images(draft_id: str, content: str) -> list[dict]:
    try:
        plan = await generate_carousel_plan(content)
        generated_images = []

        for index, slide in enumerate(plan["slides"], start=1):
            position = int(slide.get("slide") or index)
            flattened_prompt = flatten_carousel_slide_prompt({**slide, "slide": position})
            image_url = await generate_image_from_prompt(draft_id, flattened_prompt, position)

            if not image_url:
                continue

            generated_images.append({
                "image_url": image_url,
                "position": position,
                "headline": slide.get("headline"),
                "caption_text": slide.get("caption_text"),
                "prompt": flattened_prompt,
            })

        return generated_images
    except Exception as e:
        print(f"❌ Failed to generate carousel illustrations: {e}")
        return []
