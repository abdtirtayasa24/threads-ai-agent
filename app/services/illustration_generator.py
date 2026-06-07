import os
import re
import httpx
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from openai import AsyncOpenAI
from app.config import settings

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

async def generate_image_prompt(content: str) -> str:
    system_prompt = load_prompt("illustration_style.md")

    prompt_res = await client.chat.completions.create(
        model=settings.AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Create an image-generation prompt that visually represents "
                    "the core idea of this post:\n\n"
                    f"{content}"
                )
            }
        ],
        temperature=0.5
    )

    image_prompt = prompt_res.choices[0].message.content
    if not image_prompt:
        raise RuntimeError("AI did not return an image prompt.")
    
    return image_prompt.strip()
    
async def generate_and_watermark_image(draft_id: str, content: str) -> str | None:
    """
    Generate an illustration based on post content, apply watermark,
    save it locally, and return the public image URL.
    """
    try:
        image_prompt = await generate_image_prompt(content)

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
            "modalities": ["image", "text"],
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

        filename = f"{safe_filename(draft_id)}.jpg"
        filepath = os.path.join("static", "images", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        watermarked_img.save(filepath, "JPEG", quality=90, optimize=True)

        print(f"✅ Illustration saved to {filepath}")
        return f"{settings.BASE_URL.rstrip('/')}/static/images/{filename}"
        
    except Exception as e:
        print(f"❌ Failed to generate illustration: {e}")
        return None