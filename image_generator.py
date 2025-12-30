"""Image generator using Hugging Face Inference API with SDXL model."""

import io
import time
import requests
from PIL import Image

import config


def generate_image(prompt: str, output_path: str) -> str:
    """
    Generate an image using Hugging Face SDXL model.

    Args:
        prompt: The image generation prompt
        output_path: Path to save the generated image

    Returns:
        str: Path to the saved image

    Raises:
        ValueError: If API token is not configured
        Exception: If image generation fails after retries
    """
    if not config.HF_API_TOKEN:
        raise ValueError("HF_API_TOKEN is not configured")

    headers = {"Authorization": f"Bearer {config.HF_API_TOKEN}"}

    payload = {
        "inputs": prompt,
        "parameters": {
            "width": config.IMAGE_WIDTH,
            "height": config.IMAGE_HEIGHT,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        }
    }

    # Retry logic for cold starts
    for attempt in range(config.MAX_RETRIES):
        response = requests.post(
            config.HF_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code == 200:
            # Success - process the image
            break
        elif response.status_code == 503:
            # Model is loading (cold start)
            try:
                error_data = response.json()
                estimated_time = error_data.get("estimated_time", config.RETRY_DELAY)
                print(f"Model loading, waiting {estimated_time}s (attempt {attempt + 1}/{config.MAX_RETRIES})")
                time.sleep(estimated_time)
            except Exception:
                print(f"Model loading, waiting {config.RETRY_DELAY}s (attempt {attempt + 1}/{config.MAX_RETRIES})")
                time.sleep(config.RETRY_DELAY)
        elif response.status_code == 500:
            # Server error - retry with backoff
            wait_time = config.RETRY_DELAY * (attempt + 1)
            print(f"Server error, retrying in {wait_time}s (attempt {attempt + 1}/{config.MAX_RETRIES})")
            time.sleep(wait_time)
        else:
            raise Exception(f"Image generation failed: {response.status_code} - {response.text}")
    else:
        raise Exception(f"Image generation failed after {config.MAX_RETRIES} attempts")

    # Load the generated image
    image = Image.open(io.BytesIO(response.content))

    # Resize/crop to target dimensions (1080x1920)
    image = resize_and_crop(image, config.VIDEO_WIDTH, config.VIDEO_HEIGHT)

    # Save the image
    image.save(output_path, "PNG", quality=95)

    return output_path


def resize_and_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Resize and crop image to target dimensions while maintaining aspect ratio.

    Args:
        image: PIL Image to process
        target_width: Target width in pixels
        target_height: Target height in pixels

    Returns:
        PIL Image: Processed image
    """
    # Calculate aspect ratios
    target_ratio = target_width / target_height
    image_ratio = image.width / image.height

    if image_ratio > target_ratio:
        # Image is wider - resize based on height, crop width
        new_height = target_height
        new_width = int(image.width * (target_height / image.height))
    else:
        # Image is taller - resize based on width, crop height
        new_width = target_width
        new_height = int(image.height * (target_width / image.width))

    # Resize
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Calculate crop box (center crop)
    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    # Crop
    image = image.crop((left, top, right, bottom))

    return image


if __name__ == "__main__":
    # Test the generator
    test_prompt = "Liminal photography of an empty hotel corridor at 3am, low lighting, 1980s aesthetic, film grain, slightly unsettling, no people, vertical 9:16 composition"
    output = generate_image(test_prompt, "test_image.png")
    print(f"Image saved to: {output}")
