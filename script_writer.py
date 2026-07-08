"""
Turns a topic into a sentence-by-sentence script.

Each sentence gets:
  - "text": the narration line, in the TARGET language (e.g. Hindi)
  - "keywords": 2-3 ENGLISH visual search terms for stock footage
                (kept in English on purpose -- Pexels/stock search
                works far better in English regardless of narration language)

Output is a plain Python list of dicts, always in this shape, regardless
of which LLM provider you use.
"""

import os
import json
import re

PROMPT_TEMPLATE = """You are writing a short-form vertical video script (like a Reel/Short) about: "{topic}"

Write it in {language_name}. Rules:
- {num_sentences} short punchy sentences, each one a separate narration line
- Natural spoken {language_name}, no stage directions, no emojis
- Hook in the very first sentence
- For EACH sentence also give 2-3 ENGLISH keywords describing what b-roll footage would visually match it (even though the sentence itself is in {language_name})

Return ONLY valid JSON, no markdown fences, no preamble, in exactly this shape:
{{
  "title": "short video title in {language_name}",
  "sentences": [
    {{"text": "...", "keywords": ["...", "..."]}}
  ]
}}
"""

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "bn": "Bengali",
    "en": "English",
}


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()
    return raw


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    return resp.choices[0].message.content


def _call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt)
    return resp.text


PROVIDERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
}


def generate_script(topic: str, language: str = "hi", num_sentences: int = 8,
                     provider: str | None = None) -> dict:
    """
    Returns {"title": str, "sentences": [{"text": str, "keywords": [str, ...]}, ...]}
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "openai")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose from {list(PROVIDERS)}")

    language_name = LANGUAGE_NAMES.get(language, language)
    prompt = PROMPT_TEMPLATE.format(
        topic=topic, language_name=language_name, num_sentences=num_sentences
    )

    raw = PROVIDERS[provider](prompt)
    raw = _clean_json(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"LLM did not return valid JSON. Raw output was:\n{raw}"
        ) from e

    if "sentences" not in data or not isinstance(data["sentences"], list):
        raise RuntimeError(f"LLM JSON missing 'sentences' list: {data}")

    return data


def load_manual_script(path: str, language: str = "hi") -> dict:
    """
    If you'd rather write your own script instead of using an LLM:
    one sentence per line in a .txt file. Keywords are auto-guessed
    as generic fallback ('nature', 'city', 'people') since there's no
    LLM to derive them -- edit the returned dict's keywords if you want
    better footage matches.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    return {
        "title": os.path.splitext(os.path.basename(path))[0],
        "sentences": [{"text": line, "keywords": ["abstract", "background"]} for line in lines],
    }
