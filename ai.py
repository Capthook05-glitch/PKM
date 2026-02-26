"""
ai.py — AI processing layer.

All API calls go through this module. The UI code only calls the two public
functions: process_item() and process_highlight(). Both return a plain dict
so that swapping providers (OpenAI → Anthropic → Gemini) only requires
changing this file, not any UI code.

The model is gpt-4o-mini by default (fast, cheap, good for this use case).
Override with OPENAI_MODEL in your .env file if you want more power.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ─── System prompt ────────────────────────────────────────────────────────────
# This is the persistent context that shapes every AI response.
# It tells the model who this knowledge base belongs to and what "useful" means
# for this specific person.

SYSTEM_PROMPT = """You are a knowledge assistant for a specific professional's personal knowledge management system.

About this person:
- CBT-oriented therapist in private practice, focused on anxiety, overthinking, motivation, performance pressure, young adult transitions, and relationships.
- Organizational and behavioral consultant helping companies with alignment, culture, execution, and customer understanding.
- Learns by reading, watching, and listening — and needs to USE what they learn, not just collect it.

Your job on every request:
1. Summarize the idea in plain, direct language (1-2 sentences max).
2. Extract one concrete actionable insight — something specific this person could DO, SAY, or THINK DIFFERENTLY in their therapy sessions or consulting work. Not a platitude. A real move.
3. Suggest 3-5 lowercase tags that reflect the themes in this person's work (e.g., anxiety, cbt, motivation, reframe, org-culture, client-relationships, mental-models, performance).
4. Identify connections to other items in their library that genuinely relate — conceptually, thematically, or as contrasts.

Always respond in valid JSON. Be specific and practical."""


# ─── Client factory ───────────────────────────────────────────────────────────

def _get_client():
    """
    Return an OpenAI client.
    Raises RuntimeError with a clear user-facing message if setup is wrong.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "The openai package is not installed. Run: pip install openai"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No OPENAI_API_KEY found. Create a .env file in ~/pkm_app/ with:\n\n"
            "    OPENAI_API_KEY=sk-...\n\n"
            "See .env.example for the template."
        )

    from openai import OpenAI
    return OpenAI(api_key=api_key)


# ─── Library context builder ──────────────────────────────────────────────────

def _build_library_context(library_items: list) -> str:
    """
    Convert the list of library item dicts into a compact text block
    that fits comfortably in a prompt without burning tokens.
    Format: [ID:42] Title (Type) — tags: tag1, tag2
    Capped at 60 items to keep context manageable.
    """
    if not library_items:
        return "(library is empty — no connections possible yet)"

    lines = []
    for item in library_items[:60]:
        tags = item.get("tags", [])
        tag_str = ", ".join(tags) if tags else "untagged"
        lines.append(
            f"[ID:{item['id']}] {item['title']} ({item['content_type']}) — tags: {tag_str}"
        )
    return "\n".join(lines)


# ─── Response parser ──────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """
    Parse the model's JSON response into a normalized dict.
    Returns safe defaults for any missing or malformed fields so the UI
    never crashes from a bad model response.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # If JSON is malformed, extract what we can from the raw text
        return {
            "summary": raw[:300] if raw else "Could not parse AI response.",
            "actionable_insight": "",
            "suggested_tags": [],
            "connections": [],
        }

    # Normalize connections: ensure each has id, title, reason
    raw_connections = data.get("connections", [])
    connections = []
    for c in raw_connections:
        if isinstance(c, dict):
            connections.append({
                "id": c.get("id"),
                "title": str(c.get("title", "")),
                "reason": str(c.get("reason", "")),
            })

    # Normalize tags: must be strings, lowercased
    raw_tags = data.get("suggested_tags", [])
    tags = [str(t).strip().lower() for t in raw_tags if t]

    return {
        "summary": str(data.get("summary", "")).strip(),
        "actionable_insight": str(data.get("actionable_insight", "")).strip(),
        "suggested_tags": tags,
        "connections": connections,
    }


# ─── Public: process an item ──────────────────────────────────────────────────

def process_item(
    title: str,
    content_type: str,
    body: str,
    url: str,
    existing_tags: list,
    library_items: list,
) -> dict:
    """
    Run AI processing on an item.

    Returns a dict with keys:
      summary           — 1-2 sentence summary
      actionable_insight — one concrete thing to DO with this
      suggested_tags    — list of suggested lowercase tag strings
      connections       — list of {id, title, reason} dicts

    Raises RuntimeError (user-facing message) if the API key is missing.
    Raises Exception for network or API errors (caller should catch and display).
    """
    client = _get_client()
    library_str = _build_library_context(library_items)

    content_section = ""
    if body:
        content_section += f"\nContent/Notes:\n{body}\n"
    if url:
        content_section += f"\nURL: {url}\n"
    if not content_section:
        content_section = "\n(No body text provided — work from the title alone.)\n"

    prompt = f"""Analyze this item from my knowledge base and return a JSON object.

Title: {title}
Type: {content_type}
{content_section}
Other items in my library (use these IDs for connections):
{library_str}

Return ONLY valid JSON with exactly these keys:
{{
  "summary": "1-2 sentence summary of the core idea",
  "actionable_insight": "one specific thing I could do, say, or think differently in my therapy or consulting work",
  "suggested_tags": ["tag1", "tag2", "tag3"],
  "connections": [
    {{"id": <integer ID from library or null>, "title": "<exact title from library>", "reason": "<why it connects>"}}
  ]
}}

For connections: pick 2-3 genuinely related items from the library. If the library is empty, return [].
For suggested_tags: 3-5 lowercase tags. May include new tags not in the library."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    return _parse_response(response.choices[0].message.content)


# ─── Public: process a highlight ─────────────────────────────────────────────

def process_highlight(
    text: str,
    source_info: str,
    parent_item_title: str,
    existing_tags: list,
    library_items: list,
) -> dict:
    """
    Run AI processing on a highlight/quote.
    Same return shape as process_item().
    """
    client = _get_client()
    library_str = _build_library_context(library_items)

    context_lines = []
    if source_info:
        context_lines.append(f"Source: {source_info}")
    if parent_item_title:
        context_lines.append(f"From item: {parent_item_title}")
    context_str = "\n".join(context_lines) if context_lines else "(no source info)"

    prompt = f"""Analyze this highlight/quote from my knowledge base and return a JSON object.

Quote: "{text}"
{context_str}

Other items in my library (use these IDs for connections):
{library_str}

Return ONLY valid JSON with exactly these keys:
{{
  "summary": "1-2 sentence explanation of what this quote means and why it matters",
  "actionable_insight": "one specific thing I could do, say, or apply in my therapy or consulting work based on this quote",
  "suggested_tags": ["tag1", "tag2", "tag3"],
  "connections": [
    {{"id": <integer ID from library or null>, "title": "<exact title from library>", "reason": "<why it connects>"}}
  ]
}}

For connections: pick 2-3 genuinely related items from the library. If the library is empty, return [].
For suggested_tags: 3-5 lowercase tags."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    return _parse_response(response.choices[0].message.content)


# ─── Public: weekly digest ────────────────────────────────────────────────────

def generate_weekly_digest(
    items: list,
    highlights: list,
    item_tags_map: dict = None,
) -> str:
    """
    Generate a markdown-formatted weekly digest from recently captured content.
    Returns a plain string (markdown text, not JSON).
    """
    client = _get_client()

    item_lines = []
    for item in items:
        tags = (item_tags_map or {}).get(item["id"], [])
        summary = item["ai_summary"] or (item["body"] or "")[:200]
        tag_str = ", ".join(tags) if tags else ""
        line = f"- **{item['title']}** ({item['content_type_name'] or 'Unknown'})"
        if summary:
            line += f": {summary[:180]}"
        if tag_str:
            line += f"  [tags: {tag_str}]"
        item_lines.append(line)

    hl_lines = []
    for h in highlights:
        preview = h["text"][:150] + ("..." if len(h["text"]) > 150 else "")
        source = f" — {h['source_info']}" if h["source_info"] else ""
        hl_lines.append(f'- "{preview}"{source}')

    items_block = "\n".join(item_lines) if item_lines else "(nothing captured)"
    hl_block = "\n".join(hl_lines) if hl_lines else "(no highlights)"

    prompt = f"""Here is what I captured in my knowledge base recently:

ITEMS ({len(items)} total):
{items_block}

HIGHLIGHTS ({len(highlights)} total):
{hl_block}

Write a weekly digest in markdown that helps me reflect on and USE what I captured. Use these exact section headers:

## What I Captured
(2-3 sentences: what was the overall focus this period?)

## Key Themes
(3-5 bullet points: themes that emerged across items and highlights)

## Top Insights
(the 3 most actionable insights — specific to my therapy or consulting work, with item name in parentheses)

## Connections Worth Exploring
(2-3 cross-item patterns or tensions — where do ideas talk to each other or push back?)

## Questions to Sit With
(2-3 open questions this period's learning raised for me)

Be specific. Reference items by name. No generic platitudes."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    return response.choices[0].message.content


# ─── Public: build a framework ────────────────────────────────────────────────

def build_framework(
    selected_items: list,
    item_tags_map: dict = None,
) -> dict:
    """
    Synthesize selected items into a named, reusable mental model or framework.

    Returns a dict with keys:
      name, tagline, description,
      components: [{name, description, application}],
      how_to_use, source_items
    """
    client = _get_client()

    item_blocks = []
    for item in selected_items:
        tags = (item_tags_map or {}).get(item["id"], [])
        summary = item["ai_summary"] or (item["body"] or "")[:300]
        insight = item["ai_insight"] or ""
        tag_str = ", ".join(tags) if tags else "untagged"

        block = f"**{item['title']}** ({item['content_type_name'] or 'Unknown'})\n"
        if summary:
            block += f"Summary: {summary}\n"
        if insight:
            block += f"Key insight: {insight}\n"
        block += f"Tags: {tag_str}"
        item_blocks.append(block)

    items_text = "\n\n".join(item_blocks)

    prompt = f"""I want to synthesize these {len(selected_items)} items from my knowledge base into a reusable framework I can use with therapy clients or in consulting work.

ITEMS TO SYNTHESIZE:
{items_text}

Build a practical, memorable framework that distills the core ideas into something genuinely usable — something I could explain to a client in a session or introduce to a team in a workshop.

Return ONLY valid JSON with exactly these keys:
{{
  "name": "Short memorable name (3-6 words, e.g. 'The Activation-Meaning Loop')",
  "tagline": "One sentence: what problem this framework solves or what it helps with",
  "description": "2-3 sentences explaining the framework and why it works",
  "components": [
    {{
      "name": "Component name",
      "description": "What this component means or represents",
      "application": "Specific way to introduce or use this in a session or engagement"
    }}
  ],
  "how_to_use": "3-5 concrete steps for applying this with a client or team",
  "source_items": ["exact title 1", "exact title 2"]
}}

Aim for 3-5 components. Make it feel like a real, named tool — not just a summary."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    try:
        data = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        data = {}

    return {
        "name": data.get("name", "Untitled Framework"),
        "tagline": data.get("tagline", ""),
        "description": data.get("description", ""),
        "components": data.get("components", []),
        "how_to_use": data.get("how_to_use", ""),
        "source_items": data.get("source_items", []),
    }
