import os
import datetime
import base64
import logging
import urllib.request

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext
from google.cloud import storage
from google.genai import Client, types

from . import prompt
load_dotenv()

logger = logging.getLogger(__name__)

# Lazy-init to avoid import-time credential errors
_client = None
_storage_client = None
GCS_BUCKET_NAME = "social-media-agent-assets"


def _get_client():
    global _client
    if _client is None:
        _client = Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
        )
    return _client


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    return _storage_client


def analyze_user_image(tool_context: ToolContext, poster_goal: str, image_url: str = "") -> dict:
    """
    Analyzes a user image using Gemini multimodal vision and generates
    a detailed image generation prompt inspired by the photo.

    Use this tool when the user wants to create content based on their photo.
    The image can come from:
    1. A direct URL (image_url parameter — e.g., from asset archive)
    2. An image attached in the chat (auto-detected from state)

    Args:
        poster_goal: What the user wants to create (e.g., "인스타 포스터", "제품 홍보 이미지").
        image_url: Optional GCS or public URL of the user's image. If empty, tries to find attached image.

    Returns:
        dict with 'status', 'analysis', and 'suggested_prompt' (for generate_image).
    """
    image_bytes = None
    image_mime = "image/jpeg"

    # Priority 1: Direct URL provided
    if image_url and image_url.startswith("http"):
        try:
            req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                image_bytes = resp.read()
                ct = resp.headers.get("Content-Type", "image/jpeg")
                image_mime = ct.split(";")[0].strip()
            logger.info("Image loaded from URL: %s (%d bytes)", image_url[:80], len(image_bytes))
        except Exception as e:
            logger.warning("Failed to fetch image from URL '%s': %s", image_url[:80], e)

    # Priority 2: base64 data URL
    if not image_bytes and image_url and image_url.startswith("data:"):
        try:
            header, b64data = image_url.split(",", 1)
            image_mime = header.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(b64data)
            logger.info("Image loaded from data URL (%d bytes)", len(image_bytes))
        except Exception as e:
            logger.warning("Failed to parse data URL: %s", e)

    # Priority 3: Asset reference URL from state (extracted by _inject_core_memory)
    if not image_bytes:
        try:
            ref_url = tool_context.state.get("_referenced_asset_url")
            if ref_url and isinstance(ref_url, str) and ref_url.startswith("http"):
                req = urllib.request.Request(ref_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    image_bytes = resp.read()
                    ct = resp.headers.get("Content-Type", "image/jpeg")
                    image_mime = ct.split(";")[0].strip()
                logger.info("Image loaded from state _referenced_asset_url: %s (%d bytes)", ref_url[:80], len(image_bytes))
        except Exception as e:
            logger.debug("Failed to load referenced asset URL from state: %s", e)

    # Priority 4: Attached image in state (stored by _inject_core_memory)
    if not image_bytes:
        try:
            stored = tool_context.state.get("_user_attached_image")
            if stored and isinstance(stored, dict) and stored.get("data"):
                image_bytes = base64.b64decode(stored["data"])
                image_mime = stored.get("mimeType", "image/jpeg")
                logger.info("Image loaded from state (_user_attached_image, %d bytes)", len(image_bytes))
        except Exception as e:
            logger.debug("No attached image in state: %s", e)

    if not image_bytes:
        return {
            "status": "failed",
            "detail": "이미지를 찾을 수 없습니다. 이미지를 채팅에 첨부하거나, 에셋 URL을 제공해주세요.",
        }

    # Gemini multimodal analysis — Imagen 3.0 optimized
    analysis_prompt = f"""You are a professional product photographer analyzing an image for social media marketing.

The user wants to create: {poster_goal}

Provide your analysis in the SAME LANGUAGE as the poster_goal above.

## Analysis Steps:
1. **Subject identification**: What is the main product/subject? Describe its exact shape, color, material, and distinguishing features
2. **Color analysis**: List the EXACT colors (hex-like precision): product color, background color, accent colors
3. **Composition**: Camera angle, distance, lighting setup
4. **Mood/Atmosphere**: Overall feeling and brand impression

## Imagen 3.0 Prompt Generation Rules:
Build the suggested_prompt with this formula: Subject + Context + Style + Technical

- Subject: Describe the EXACT product with specific colors and materials
- Context: Appropriate background for marketing (clean, lifestyle, or studio)
- Style: "professional product photography" or "lifestyle photography"
- Technical: Include lens type (50mm for products), lighting (soft natural or studio), focus (shallow depth of field), quality modifiers (high detail, 8K)

CRITICAL:
- The prompt MUST recreate the SAME product appearance (colors, shape, materials)
- Do NOT include text or logos in the prompt
- Use positive descriptions only (not "no X" or "without X")
- Make the product the clear hero/focal point

Return ONLY valid JSON (no markdown):
{{
  "description": "detailed image description focusing on product features",
  "key_elements": ["specific element with color/material detail"],
  "mood": "overall mood and brand feeling",
  "color_palette": ["#hex or descriptive color names"],
  "product_details": "exact product description for consistency across channels",
  "suggested_prompt": "Subject + Context + Style + Technical format Imagen 3.0 prompt"
}}"""

    try:
        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
                types.Part.from_text(text=analysis_prompt),
            ],
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        import json
        analysis = json.loads(raw.strip())

        return {
            "status": "success",
            "analysis": analysis.get("description", ""),
            "key_elements": analysis.get("key_elements", []),
            "mood": analysis.get("mood", ""),
            "color_palette": analysis.get("color_palette", []),
            "product_details": analysis.get("product_details", ""),
            "suggested_prompt": analysis.get("suggested_prompt", ""),
            "source_image_url": image_url or "(chat attachment)",
        }

    except Exception as e:
        logger.warning("Image analysis failed: %s", e)
        return {
            "status": "failed",
            "detail": f"이미지 분석 실패: {str(e)}",
        }


# ─── 채널별 이미지 최적화 설정 ──────────────────────────────────────────────
_CHANNEL_IMAGE_CONFIG = {
    "instagram": {"aspect_ratio": "3:4", "style": "professional product photography, bright colors, clean background"},
    "facebook":  {"aspect_ratio": "16:9", "style": "engaging social media post, warm tones, community feel"},
    "pinterest": {"aspect_ratio": "3:4", "style": "aesthetic flat lay, lifestyle photography, inspiration board"},
    "linkedin":  {"aspect_ratio": "1:1", "style": "corporate professional, clean design, business context"},
    "tiktok":    {"aspect_ratio": "9:16", "style": "dynamic, eye-catching, trendy, bold colors"},
    "youtube":   {"aspect_ratio": "16:9", "style": "YouTube thumbnail, bold contrast, expressive"},
    "x":         {"aspect_ratio": "16:9", "style": "clean visual, informative, shareable"},
    "twitter":   {"aspect_ratio": "16:9", "style": "clean visual, informative, shareable"},
    "threads":   {"aspect_ratio": "1:1", "style": "minimal, clean, conversational"},
    "kakao":     {"aspect_ratio": "16:9", "style": "Korean aesthetic, friendly, warm colors"},
}


def generate_image(img_prompt: str, channel: str = "instagram"):
    """
    Generates an image using Imagen 3.0 with channel-optimized settings.

    Args:
        img_prompt (str): The prompt for image generation.
        channel (str): Target channel for aspect ratio optimization (default: instagram).

    Returns:
        dict: A dictionary containing the status, detail, and image URL if successful.
    """
    config = _CHANNEL_IMAGE_CONFIG.get(channel.lower(), _CHANNEL_IMAGE_CONFIG["instagram"])
    # Imagen 3.0 프롬프트 최적화: 스타일 + 품질 수식어 자동 추가
    quality_modifiers = "high detail, professional quality, sharp focus"
    enhanced_prompt = f"{img_prompt}. {config['style']}. {quality_modifiers}"

    import time as _time
    _max_retries = 3
    response = None
    for _attempt in range(_max_retries):
        try:
            response = _get_client().models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=enhanced_prompt,
                config={
                    "number_of_images": 1,
                    "aspect_ratio": config["aspect_ratio"],
                },
            )
            break
        except Exception as _e:
            if "429" in str(_e) or "RESOURCE_EXHAUSTED" in str(_e):
                _wait = 10 * (_attempt + 1)  # 10s, 20s, 30s
                logger.warning(f"[IMAGE] Rate limited, waiting {_wait}s (attempt {_attempt+1}/{_max_retries})")
                _time.sleep(_wait)
            else:
                raise
    if response is None:
        return {"status": "failed", "detail": "Image generation quota exceeded after retries. Try again later."}
    if not response.generated_images:
        return {"status": "failed", "detail": "No images were generated"}

    generated_image = response.generated_images[0].image
    if not generated_image:
        return {"status": "failed", "detail": "Generated image data is empty"}
    image_bytes = generated_image.image_bytes

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    gcs_object_name = f"images/{timestamp}.png"

    try:
        bucket = _get_storage_client().bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_object_name)
        blob.upload_from_string(image_bytes, content_type="image/png")

        return {
            "status": "success",
            "detail": "Image generated and uploaded to GCS",
            "image_url": blob.public_url,
        }
    except IOError as e:
        return {"status": "failed", "detail": f"Failed to upload image to GCS: {e}"}


image_generation_agent = Agent(
    name="image_generation_agent",
    model="gemini-2.5-flash",
    description=prompt.DESCRIPTION,
    instruction=prompt.INSTRUCTIONS,
    output_key="image_generation_output",
    tools=[analyze_user_image, generate_image],
)
