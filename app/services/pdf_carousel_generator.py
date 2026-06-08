import os
import uuid
from urllib.parse import urlparse, unquote
from PIL import Image
from app.config import settings


def static_url_to_local_path(url: str) -> str:
    base_url = settings.BASE_URL.rstrip("/")
    static_prefix = f"{base_url}/static/"

    if not url.startswith(static_prefix):
        raise ValueError(f"Image URL is not a local static URL: {url}")

    parsed = urlparse(url)
    static_path = unquote(parsed.path).lstrip("/")
    return static_path


def generate_linkedin_carousel_pdf(draft_id: uuid.UUID, image_urls: list[str]) -> str:
    if not image_urls:
        raise ValueError("No carousel images found for PDF generation")

    images = []
    for image_url in image_urls:
        image_path = static_url_to_local_path(image_url)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Carousel image file not found: {image_path}")

        image = Image.open(image_path).convert("RGB")
        images.append(image)

    os.makedirs(os.path.join("static", "pdfs"), exist_ok=True)

    filename = f"{draft_id}-linkedin-carousel.pdf"
    filepath = os.path.join("static", "pdfs", filename)

    first_image, *other_images = images
    first_image.save(filepath, "PDF", save_all=True, append_images=other_images, resolution=100.0)

    return f"{settings.BASE_URL.rstrip('/')}/static/pdfs/{filename}"
