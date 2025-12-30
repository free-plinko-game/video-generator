"""Prompt generator using Claude API to create asset prompts from theme concepts."""

import json
import anthropic

import config


PROMPT_TEMPLATE = """Given this liminal space concept:
{concept_packet}

Generate these assets. Return JSON only, no other text:
{{
  "image_prompt": "Detailed prompt for AI image generation. Style: liminal photography, low lighting, empty, 1980s-1990s aesthetic, film grain, slightly unsettling, no people. Vertical 9:16 composition.",
  "voiceover_script": "Second-person narration, 15-25 words max. Whispered tone. Present tense. Evoke vague memory or deja vu. No resolution or explanation.",
  "screen_text": "Location label and time in cryptic format. Example: 'Pool Level 2 — 3:33 AM' or 'Corridor 7B // 2:47'"
}}"""


def generate_prompts(concept: dict) -> dict:
    """
    Generate asset prompts from a theme concept using Claude API.

    Args:
        concept: Theme concept dict with location, time, mood, detail, memory_hook

    Returns:
        dict: Asset prompts with image_prompt, voiceover_script, screen_text

    Raises:
        ValueError: If API key is not configured
        Exception: If API call fails or response is invalid
    """
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Format the concept for the prompt
    concept_text = json.dumps(concept, indent=2)
    prompt = PROMPT_TEMPLATE.format(concept_packet=concept_text)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Extract the text content
    response_text = message.content[0].text.strip()

    # Parse JSON response
    try:
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (code block markers)
            response_text = "\n".join(lines[1:-1])

        prompts = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse prompts JSON: {e}\nResponse: {response_text}")

    # Validate required fields
    required_fields = ["image_prompt", "voiceover_script", "screen_text"]
    for field in required_fields:
        if field not in prompts:
            raise Exception(f"Missing required field in prompts: {field}")

    return prompts


if __name__ == "__main__":
    # Test the generator
    from theme_generator import generate_theme

    theme = generate_theme()
    print("Theme:")
    print(json.dumps(theme, indent=2))
    print("\nPrompts:")
    prompts = generate_prompts(theme)
    print(json.dumps(prompts, indent=2))
