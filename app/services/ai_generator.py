import os
import json
from openai import OpenAI
from app.config import settings

client = OpenAI(
    api_key=settings.AI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def generate_draft(topic: str, angle: str) -> str:
    system_prompt = load_prompt("writer_system.md")
    user_prompt = f"Write a Threads post about:\nTopic: {topic}\nAngle: {angle}\n\nMake it authentic to your persona."
    
    response = client.chat.completions.create(
        model=settings.AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=400
    )
    return response.choices[0].message.content.strip()

def generate_ideas(count: int = 3) -> dict:
    """Generates new post ideas based on the persona system prompt."""
    system_prompt = load_prompt("writer_system.md")
    user_prompt = f"""Based on your persona, generate {count} new Thread/X post ideas.
Focus on AI, automation, data analytics, CLI agents, or practical business workflows.
Do not repeat generic ideas. Make them specific, grounded, and based on real operational problems.

Output strictly in this JSON format:
{{
  "ideas": [
    {{
      "topic": "Short topic title",
      "angle": "The specific angle, contrarian take, or practical lesson to discuss"
    }}
  ]
}}"""
    
    response = client.chat.completions.create(
        model=settings.AI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.8
    )
    return json.loads(response.choices[0].message.content)