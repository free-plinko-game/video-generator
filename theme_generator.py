"""Theme generator using Claude API to create liminal space concepts."""

import json
import anthropic

import config


# Location types for the dropdown
LOCATION_TYPES = [
    ("random", "Random"),
    ("mall", "Shopping Mall"),
    ("school", "School / Classroom"),
    ("hospital", "Hospital / Medical"),
    ("pool", "Swimming Pool"),
    ("hotel", "Hotel / Motel"),
    ("airport", "Airport / Terminal"),
    ("arcade", "Arcade / Game Center"),
    ("parking", "Parking Garage"),
    ("laundromat", "Laundromat"),
    ("bowling", "Bowling Alley"),
    ("office", "Office Building"),
    ("subway", "Subway / Metro"),
    ("stairwell", "Stairwell / Hallway"),
    ("bathroom", "Public Bathroom"),
    ("elevator", "Elevator / Lobby"),
]

# Time options
TIME_OPTIONS = [
    ("random", "Random"),
    ("3am", "3:00 AM"),
    ("midnight", "Midnight"),
    ("dusk", "Dusk / Twilight"),
    ("dawn", "Early Dawn"),
    ("2am", "2:00 AM"),
    ("4am", "4:00 AM"),
    ("late_night", "Late Night"),
]

# Mood options
MOOD_OPTIONS = [
    ("random", "Random"),
    ("nostalgic", "Nostalgic / Bittersweet"),
    ("unsettling", "Unsettling / Eerie"),
    ("dreamlike", "Dreamlike / Surreal"),
    ("melancholic", "Melancholic / Sad"),
    ("peaceful", "Peaceful / Calm"),
    ("lonely", "Lonely / Isolated"),
    ("liminal", "Transitional / In-Between"),
    ("forgotten", "Forgotten / Abandoned"),
]


def build_theme_prompt(constraints: dict = None) -> str:
    """Build the theme prompt with optional constraints."""
    base_prompt = """Generate a liminal space concept for a short atmospheric video.
Return JSON only, no other text:
{
  "location": "specific place with decade if relevant",
  "time": "specific late night time",
  "mood": "2-3 word emotional tone",
  "detail": "one small sensory detail",
  "memory_hook": "vague nostalgic connection"
}

Make it feel familiar but slightly wrong."""

    if not constraints:
        base_prompt += " Draw from: hotels, malls, schools, pools, hospitals, airports, arcades, parking garages, laundromats, bowling alleys - all at off-hours or abandoned."
        return base_prompt

    additions = []

    if constraints.get('location') and constraints['location'] != 'random':
        location_map = {
            'mall': 'a shopping mall or department store',
            'school': 'a school, classroom, or educational building',
            'hospital': 'a hospital, medical facility, or waiting room',
            'pool': 'a swimming pool or pool area',
            'hotel': 'a hotel, motel, or hotel hallway',
            'airport': 'an airport terminal or gate area',
            'arcade': 'an arcade or game center',
            'parking': 'a parking garage or parking structure',
            'laundromat': 'a laundromat or laundry room',
            'bowling': 'a bowling alley',
            'office': 'an office building or corporate space',
            'subway': 'a subway station or metro platform',
            'stairwell': 'a stairwell, hallway, or corridor',
            'bathroom': 'a public bathroom or restroom',
            'elevator': 'an elevator or building lobby',
        }
        additions.append(f"The location MUST be {location_map.get(constraints['location'], constraints['location'])}.")

    if constraints.get('time') and constraints['time'] != 'random':
        time_map = {
            '3am': '3:00 AM',
            'midnight': 'midnight',
            'dusk': 'dusk or twilight',
            'dawn': 'early dawn, just before sunrise',
            '2am': '2:00 AM',
            '4am': '4:00 AM',
            'late_night': 'late night hours',
        }
        additions.append(f"The time MUST be {time_map.get(constraints['time'], constraints['time'])}.")

    if constraints.get('mood') and constraints['mood'] != 'random':
        mood_map = {
            'nostalgic': 'nostalgic and bittersweet',
            'unsettling': 'unsettling and eerie',
            'dreamlike': 'dreamlike and surreal',
            'melancholic': 'melancholic and sad',
            'peaceful': 'peaceful and calm',
            'lonely': 'lonely and isolated',
            'liminal': 'transitional and in-between',
            'forgotten': 'forgotten and abandoned',
        }
        additions.append(f"The mood MUST be {mood_map.get(constraints['mood'], constraints['mood'])}.")

    if additions:
        base_prompt += "\n\n" + " ".join(additions)
    else:
        base_prompt += " Draw from: hotels, malls, schools, pools, hospitals, airports, arcades, parking garages, laundromats, bowling alleys - all at off-hours or abandoned."

    return base_prompt


def generate_theme(constraints: dict = None) -> dict:
    """
    Generate a random liminal space concept using Claude API.

    Args:
        constraints: Optional dict with 'location', 'time', 'mood' constraints

    Returns:
        dict: Theme concept with location, time, mood, detail, and memory_hook

    Raises:
        ValueError: If API key is not configured
        Exception: If API call fails or response is invalid
    """
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    # Build prompt with constraints
    prompt = build_theme_prompt(constraints)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
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
