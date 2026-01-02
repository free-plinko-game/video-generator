"""Script generator for long-form video content."""

import json
import anthropic
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _call_claude(prompt: str, max_tokens: int = 2000) -> str:
    """Helper to call Claude API."""
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


def _parse_json(response_text: str) -> dict:
    """Parse JSON from response, handling markdown code blocks."""
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])
    return json.loads(response_text)


def generate_intro_script(intro_prompt: str, content_type: dict, theme: dict = None) -> str:
    """
    Generate an intro script for a compilation or long-form video.

    Args:
        intro_prompt: The intro generation prompt from content type
        content_type: Content type configuration
        theme: Optional theme data for context

    Returns:
        str: Intro voiceover script
    """
    context = f"Content Type: {content_type.get('name', 'Video')}"
    if theme:
        context += f"\nTheme: {json.dumps(theme, indent=2)}"

    prompt = f"""{intro_prompt}

{context}

Write a compelling 2-3 sentence intro that:
- Hooks the viewer immediately
- Sets the mood and tone
- Creates anticipation for what's coming

Return ONLY the script text, no JSON, no quotes, just the words to be spoken."""

    return _call_claude(prompt, max_tokens=300)


def generate_outro_script(content_type: dict) -> str:
    """
    Generate an outro script for a video.

    Args:
        content_type: Content type configuration

    Returns:
        str: Outro voiceover script
    """
    prompt = f"""Write a short outro for a {content_type.get('name', 'video')} video.

It should:
- Thank viewers in a subtle way
- Encourage likes/subscribes without being pushy
- Fit the {content_type.get('name', '')} aesthetic
- Be 2-3 sentences maximum

Return ONLY the script text, no JSON, no quotes."""

    return _call_claude(prompt, max_tokens=200)


def generate_outline(outline_prompt: str, content_type: dict) -> dict:
    """
    Generate an outline for a deep dive/essay video.

    Args:
        outline_prompt: The outline generation prompt
        content_type: Content type configuration

    Returns:
        dict: Outline with title and sections
    """
    prompt = f"""{outline_prompt}

Content Type: {content_type.get('name', 'Video')}

Generate a detailed outline for a 10-15 minute video essay.

Return JSON only:
{{
  "title": "Compelling video title",
  "hook": "Opening hook sentence",
  "sections": [
    {{
      "title": "Section title",
      "key_points": ["point 1", "point 2"],
      "duration_seconds": 90
    }}
  ],
  "conclusion": "Final takeaway message"
}}

Create 6-8 sections that flow logically and build to a satisfying conclusion."""

    response = _call_claude(prompt, max_tokens=1500)
    return _parse_json(response)


def generate_long_script(outline: dict, content_type: dict) -> str:
    """
    Generate a full script from an outline for a deep dive video.

    Args:
        outline: The video outline with sections
        content_type: Content type configuration

    Returns:
        str: Complete voiceover script
    """
    sections_text = ""
    for i, section in enumerate(outline.get('sections', [])):
        sections_text += f"\n{i+1}. {section.get('title', f'Section {i+1}')}"
        for point in section.get('key_points', []):
            sections_text += f"\n   - {point}"

    prompt = f"""Write a complete voiceover script for a video essay.

Title: {outline.get('title', 'Untitled')}
Hook: {outline.get('hook', '')}

Sections:{sections_text}

Conclusion: {outline.get('conclusion', '')}

Content style: {content_type.get('name', 'Video')}

Guidelines:
- Write in a conversational but authoritative tone
- Include natural pauses (indicated by "...")
- Create smooth transitions between sections
- The script should be ~1500-2000 words for a 10-15 minute video
- Start with the hook, expand each section, end with conclusion

Return ONLY the script text, formatted as a voiceover would be read."""

    return _call_claude(prompt, max_tokens=4000)


def generate_scene_script(theme: dict, content_type: dict, scene_number: int = None) -> str:
    """
    Generate a short script for a single scene in a compilation.

    Args:
        theme: Scene theme data
        content_type: Content type configuration
        scene_number: Optional scene number for context

    Returns:
        str: Scene voiceover script (1-3 sentences)
    """
    prompt = f"""Write a very short voiceover for scene {scene_number or 'X'} of a compilation video.

Theme: {json.dumps(theme, indent=2)}
Content Type: {content_type.get('name', '')}

Guidelines:
- 1-3 sentences maximum
- Evocative and atmospheric
- Matches the {content_type.get('name', '')} style
- Should work as a standalone moment

Return ONLY the script text."""

    return _call_claude(prompt, max_tokens=150)


if __name__ == "__main__":
    # Test the generators
    test_content_type = {
        'name': 'Liminal Spaces',
        'theme_prompt': 'Generate a liminal space concept...'
    }

    print("Testing intro script generation...")
    intro = generate_intro_script(
        "Write an intro for a liminal spaces compilation",
        test_content_type,
        {"location": "Empty mall at 3am", "mood": "Unsettling nostalgia"}
    )
    print(f"Intro: {intro}\n")

    print("Testing outro script generation...")
    outro = generate_outro_script(test_content_type)
    print(f"Outro: {outro}\n")
