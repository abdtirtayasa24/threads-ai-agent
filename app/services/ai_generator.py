import os
import json
import logging
import re
from openai import OpenAI
from app.config import settings
from app.services.content_strategy import WRITER_STYLE_V2, get_writer_prompt_filename, get_writer_style

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
    system_prompt = load_prompt(get_writer_prompt_filename())
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
    """Generates new post ideas based on the active persona/style prompt."""
    writer_style = get_writer_style()
    system_prompt = load_prompt(get_writer_prompt_filename())
    previous_ideas = previous_ideas or []
    previous_ideas_text = "\n".join(
        f"- Topic: {idea.get('topic', '')}\n  Angle: {idea.get('angle', '')}"
        for idea in previous_ideas
    )
    if not previous_ideas_text:
        previous_ideas_text = "No previous ideas yet."

    if writer_style == WRITER_STYLE_V2:
        focus_instruction = """Generate broader, conversation-first Threads Indonesia post ideas in Abdul's voice.
Use Abdul's AI/data/automation/workflow lens, but broaden the topics into work life, early career, learning technical skills, productivity pressure, repetitive work, spreadsheet/dashboard culture, AI anxiety, office communication, and relatable operational friction.
Make each idea specific, human, reply-friendly, and easy to turn into a conversation seed.
Do not generate only pure AI/automation tutorial topics."""
    else:
        focus_instruction = """Focus on AI, automation, data analytics, CLI agents, or practical business workflows.
Do not repeat generic ideas. Make them specific, grounded, and based on real operational problems."""

    user_prompt = f"""Based on your persona, generate {count} new Thread/X post ideas.
{focus_instruction}

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