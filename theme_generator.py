"""Theme generator using Claude API to create liminal space concepts."""

import json
import anthropic

import config


THEME_PROMPT = """Generate a liminal space concept for a short atmospheric video.
Return JSON only, no other text:
{
  "location": "specific place with decade if relevant",
  "time": "specific late night time",
  "mood": "2-3 word emotional tone",
  "detail": "one small sensory detail",
  "memory_hook": "vague nostalgic connection"
}

Make it feel familiar but slightly wrong. Draw from: hotels, malls, schools, pools, hospitals, airports, arcades, parking garages, laundromats, bowling alleys - all at off-hours or abandoned."""


def generate_theme() -> dict:
    """
    Generate a random liminal space concept using Claude API.

    Returns:
        dict: Theme concept with location, time, mood, detail, and memory_hook

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
            {"role": "user", "content": THEME_PROMPT}
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

    # Validate required fields
    required_fields = ["location", "time", "mood", "detail", "memory_hook"]
    for field in required_fields:
        if field not in theme:
            raise Exception(f"Missing required field in theme: {field}")

    return theme


if __name__ == "__main__":
    # Test the generator
    theme = generate_theme()
    print(json.dumps(theme, indent=2))
