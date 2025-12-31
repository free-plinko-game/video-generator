"""Theme generator using Claude API to create content concepts."""

import json
import anthropic
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def generate_theme(theme_prompt: str) -> dict:
    """
    Generate a content theme/concept using Claude API.

    Args:
        theme_prompt: The prompt for generating the theme (from content type)

    Returns:
        dict: Theme concept data (structure depends on content type)

    Raises:
        ValueError: If API key is not configured
        Exception: If API call fails or response is invalid
    """
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[
            {"role": "user", "content": theme_prompt}
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

        theme = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse theme JSON: {e}\nResponse: {response_text}")

    return theme


if __name__ == "__main__":
    # Test the generator with a liminal space prompt
    test_prompt = """Generate a liminal space concept for a short atmospheric video.
Return JSON only:
{
  "location": "specific place with decade if relevant",
  "time": "specific late night time",
  "mood": "2-3 word emotional tone",
  "detail": "one small sensory detail",
  "memory_hook": "vague nostalgic connection"
}

Make it feel familiar but slightly wrong."""

    theme = generate_theme(test_prompt)
    print(json.dumps(theme, indent=2))
