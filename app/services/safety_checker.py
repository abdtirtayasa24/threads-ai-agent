import json
from openai import OpenAI
from app.config import settings
from app.services.ai_generator import load_prompt

client = OpenAI(
    api_key=settings.AI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def check_safety(draft_content: str) -> dict:
    system_prompt = load_prompt("safety_checker.md")
    
    response = client.chat.completions.create(
        model=settings.AI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Draft to evaluate:\n\n{draft_content}"}
        ],
        temperature=0.0
    )
    return json.loads(response.choices[0].message.content)