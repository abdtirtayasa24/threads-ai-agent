import os
import json
import logging
import re
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=settings.AI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def extract_and_parse_json(raw_output: str) -> dict:
    """Extract a JSON object from an AI response and parse it safely."""
    text = (raw_output or "").strip()

    code_block_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if code_block_match:
        text = code_block_match.group(1).strip()

    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.exception("Failed to decode JSON from AI output. Raw output: %r", raw_output)
        raise

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

def generate_ideas(count: int = 2, previous_ideas: list[dict[str, str]] | None = None) -> dict:
    """Generates new post ideas based on the persona system prompt."""
    system_prompt = load_prompt("writer_system.md")
    previous_ideas = previous_ideas or []
    previous_ideas_text = "\n".join(
        f"- Topic: {idea.get('topic', '')}\n  Angle: {idea.get('angle', '')}"
        for idea in previous_ideas
    )
    if not previous_ideas_text:
        previous_ideas_text = "No previous ideas yet."

    user_prompt = f"""Based on your persona, generate {count} new Thread/X post ideas.
Focus on AI, automation, data analytics, CLI agents, or practical business workflows.
Do not repeat generic ideas. Make them specific, grounded, and based on real operational problems.

Previously generated ideas that must NOT be repeated or reworded:
{previous_ideas_text}

Generate only ideas that are meaningfully different from every previous topic and angle above.
If an idea is merely a variation of a previous one, discard it and create a more distinct idea.

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
    return extract_and_parse_json(response.choices[0].message.content)