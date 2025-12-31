"""Prompt generator using Claude API to create asset prompts from theme concepts."""

import json
import anthropic
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def generate_prompts(theme: dict, content_type: dict) -> dict:
    """
    Generate asset prompts from a theme concept using Claude API.

    Args:
        theme: Theme concept dict (structure varies by content type)
        content_type: Content type configuration with prompts and styles

    Returns:
        dict: Asset prompts with image_prompt, voiceover_script, screen_text

    Raises:
        ValueError: If API key is not configured
        Exception: If API call fails or response is invalid
    """
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Build prompt with content type's style and script instructions
    image_style = content_type.get('image_style_prompt', '')
    script_instructions = content_type.get('script_prompt', '')
    voice_style = content_type.get('voice_style', '')

    prompt = f"""Given this concept:
{json.dumps(theme, indent=2)}

Generate these assets. Return JSON only, no other text:
{{
  "image_prompt": "Detailed prompt for AI image generation. Include: {image_style}",
  "voiceover_script": "{script_instructions} Voice style hint: {voice_style}",
  "screen_text": "Short location/context text for video overlay. Be cryptic and atmospheric."
}}"""

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
    test_theme = {
        "location": "1990s hotel corridor",
        "time": "3:47 AM",
        "mood": "familiar unease",
        "detail": "distant ice machine hum",
        "memory_hook": "a vacation you half-remember"
    }

    test_content_type = {
        "image_style_prompt": "liminal photography, low fluorescent lighting, empty, 1980s-1990s aesthetic",
        "script_prompt": "Write second-person narration, 15-25 words max. Whispered tone.",
        "voice_style": "whispered, slow"
    }

    prompts = generate_prompts(test_theme, test_content_type)
    print(json.dumps(prompts, indent=2))
