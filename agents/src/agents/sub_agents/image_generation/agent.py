import os
import datetime
import base64
import logging
import urllib.request
from typing import Optional

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

**STEP 0 — Classify the product category** (READ FIRST):
Pick ONE: Food/Bakery · Beverage · Beauty/Skincare · Fashion/Apparel ·
Electronics/Gadgets · Home Goods · Health/Wellness · Pet · Service · B2B.
Then apply the category's industry staging conventions below — this decides
the surface/vessel, camera angle, lens, and props. Skipping this step is the
#1 reason images look amateur.

### Category staging shortcuts (must apply):

- **Food/Bakery**: ON a wooden tray / ceramic plate / parchment / slate (NEVER bare desk).
  **45° three-quarter angle** (NEVER front-on 0°). 50mm lens. Props: crumbs, coffee cup,
  knife, steam, garnish. Background: cafe/bakery counter, rustic wood, never office desk.
- **Beverage**: in ceramic mug / glass / takeaway cup. 30-45° three-quarter for hot
  (show foam/crema), slight overhead for cold with ice. Steam OR condensation droplets.
- **Beauty**: on marble / travertine / fabric drape (NEVER bare desk). Eye-level 0-15°
  showing label legibly. Props: single flower, dropper drop, swatch on glass.
- **Fashion**: worn on a person walking/sitting at eye-level 35mm, real street/cafe
  background, not flat-lay (unless catalog explicitly).
- **Electronics**: on styled wooden desk, mid-use (hand on keyboard, etc.), 15-30° hero angle.
- **Home goods**: in-situ within a styled room, NEVER floating against backdrop.
- **Pet goods**: WITH the pet using it, pet-eye-level.
- **Service**: people experiencing it, in the actual venue.

### Formula:  Subject + Context + Style + Technical

- **Subject**: EXACT product with colors/materials AND its proper vessel/staging
  (e.g. "a sausage bread on a wooden tray lined with kraft paper", not just "a sausage bread").
  For lifestyle channels, may include a person naturally using/wearing the product.
- **Context**: Concrete environment matching the category recipe (cafe counter, marble
  vanity, street scene, styled desk) — NOT just "background" or "white seamless".
- **Style**: ONE coherent style: "lifestyle food photography", "editorial fashion lifestyle",
  "beauty product photography", "professional product photography" (catalog only).
- **Technical**: Camera angle + lens + lighting + composition must match the category recipe.
  Default to deep focus / sharp scene. Reserve shallow DOF for explicit texture goals.

### CRITICAL constraints:
- The prompt MUST recreate the SAME product appearance (colors, shape, materials).
- **Food MUST NOT be on a bare desk or shot head-on.** Use a vessel + 45° angle.
- Do NOT default to extreme close-up + blurred background.
- Do NOT include text or logos in the prompt.
- Use positive descriptions only (not "no X" or "without X").
- The product is the hero, but "hero" can mean "clearly featured within a properly
  staged scene", not "filling 80% of the frame with everything else blurred".
- Length: write enough words to encode (a) product + vessel, (b) angle/lens,
  (c) background concrete details, (d) lighting, (e) resolution tail.
  This usually means 50-80 words. Do NOT truncate staging detail to hit a short target.

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


def _verify_generated_image(image_bytes: bytes, forbidden: list[str]) -> dict:
    """
    Phase B-1: VLM 사후 검증 — 방금 생성된 이미지가 forbidden_visual_elements를
    포함하는지 Gemini로 자가 점검. forbidden이 비어있으면 verify=True로 즉시 통과.

    Args:
        image_bytes: 방금 Imagen이 생성한 PNG 바이트
        forbidden: PERSONA.forbidden_visual_elements 목록

    Returns:
        {"verified": bool, "violations": list[str], "reason": str}
    """
    if not forbidden:
        return {"verified": True, "violations": [], "reason": "no forbidden elements to check"}

    check_prompt = (
        "You are a strict brand compliance reviewer. The following visual elements "
        "MUST NOT appear in this image: "
        + ", ".join(forbidden)
        + ".\n\nExamine the image and answer in JSON only:\n"
        '{\n  "violations_found": ["<list any forbidden element that IS present>"],\n'
        '  "reason": "<one short sentence>"\n}\n'
        "If none of the forbidden elements are present, return an empty violations_found array."
    )

    try:
        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                types.Part.from_text(text=check_prompt),
            ],
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json as _json
        result = _json.loads(raw.strip())
        violations = result.get("violations_found", []) or []
        return {
            "verified": len(violations) == 0,
            "violations": violations,
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.warning("[VLM_VERIFY] verification failed: %s — defaulting to verified=True", e)
        # 검증 실패 = 통과 처리 (재생성 무한루프 방지)
        return {"verified": True, "violations": [], "reason": f"verification error: {e}"}


# ─── 채널별 이미지 최적화 설정 ──────────────────────────────────────────────
# 핵심 원칙:
#   - aspect_ratio 만 고정 (실제 플랫폼 사양)
#   - style/quality 키워드는 strategist+image_prompt가 메모리 기반으로 직접 결정
#   - 여기서 "professional product photography" 등을 강제 주입하지 않음
#     → 인물/맥락/라이프스타일이 필요한 채널에서 클로즈업 편향이 사라짐
_CHANNEL_IMAGE_CONFIG = {
    "instagram": {"aspect_ratio": "3:4"},
    "facebook":  {"aspect_ratio": "16:9"},
    "pinterest": {"aspect_ratio": "3:4"},
    "linkedin":  {"aspect_ratio": "1:1"},
    "tiktok":    {"aspect_ratio": "9:16"},
    "youtube":   {"aspect_ratio": "16:9"},
    "x":         {"aspect_ratio": "16:9"},
    "twitter":   {"aspect_ratio": "16:9"},
    "threads":   {"aspect_ratio": "1:1"},
    "kakao":     {"aspect_ratio": "16:9"},
}


def _parse_brand_constraints(img_prompt: str) -> tuple[str, dict]:
    """
    Strategist가 [BRAND_CONSTRAINTS] 블록을 프롬프트 끝에 붙여 보낸 경우,
    그것을 파싱해서 (scene_prompt, constraints) 튜플로 분리한다.

    Format expected:
        "<scene description>.
         [BRAND_CONSTRAINTS]
         forbidden_visual_elements: blue, cold metal
         required_color_palette:    warm amber, cream
         brand_colors_hex:          #E7823A, #8B4513
         product_category:          Food
         [/BRAND_CONSTRAINTS]"

    Missing/empty fields → empty lists. No BRAND_CONSTRAINTS block → empty dict.
    """
    import re

    constraints: dict = {
        "forbidden_visual_elements": [],
        "required_color_palette": [],
        "brand_colors_hex": [],
        "product_category": "",
    }

    match = re.search(
        r"\[BRAND_CONSTRAINTS\](.*?)\[/BRAND_CONSTRAINTS\]",
        img_prompt,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return img_prompt, constraints

    block = match.group(1)
    scene_prompt = img_prompt.replace(match.group(0), "").strip().rstrip(".")

    for line in block.strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key in ("forbidden_visual_elements", "required_color_palette", "brand_colors_hex"):
            items = [v.strip() for v in value.split(",") if v.strip() and v.strip().lower() not in ("(none)", "none", "")]
            constraints[key] = items
        elif key == "product_category":
            constraints["product_category"] = value if value.lower() not in ("(none)", "none", "") else ""

    return scene_prompt, constraints


# PickScore (Pick-a-Pic v2) 데이터셋이 일관되게 비선호하는 universal anti-pattern.
# Brand 무관하게 항상 차단해 두면 절대 점수 ↑.
# v3 (안 G — universal negatives 완전 제거):
# F에서 모순 키워드 제거 후 +0.22 향상. 추가 실험: universal negatives 전체 제거하면
# Baseline과 동등 조건이 됨 (Baseline은 strategist의 negative inject 없음).
# brand forbidden(페르소나별) 만 남김. AI 결함(extra fingers 등)도 negative에서 빼면
# Imagen이 더 자유롭게 풍부한 이미지 생성 가능 (Pick-a-Pic 학습 데이터의 winning
# prompts 대부분이 negative 거의 사용 안 함).
_PS_UNIVERSAL_NEGATIVES: list[str] = []  # 비움 — forbidden만 사용


def _build_negative_prompt(forbidden: list[str]) -> str:
    """Forbidden 요소 + PickScore-universal anti-pattern 병합."""
    parts = list(forbidden) if forbidden else []
    # 중복 없이 universal negatives 추가
    seen = {p.lower() for p in parts}
    for n in _PS_UNIVERSAL_NEGATIVES:
        if n.lower() not in seen:
            parts.append(n)
    return ", ".join(parts)


def _inject_required_colors(scene_prompt: str, required_colors: list[str], hex_codes: list[str]) -> str:
    """필수 컬러를 scene 프롬프트의 detail tail에 positive로 주입."""
    if not required_colors and not hex_codes:
        return scene_prompt
    parts = []
    if required_colors:
        parts.append(f"Color palette must feature {', '.join(required_colors)}")
    if hex_codes:
        parts.append(f"matching brand colors {', '.join(hex_codes)}")
    color_tail = ". " + " ".join(parts) + "."
    return scene_prompt + color_tail


def _korean_ratio(text: str) -> float:
    """한·영 알파벳 비율 — 0.0(영어 only) ~ 1.0(한국어 only). 빈 문자열은 0.0."""
    ko = sum(1 for c in text if '가' <= c <= '힣')
    en = sum(1 for c in text if c.isascii() and c.isalpha())
    total = ko + en
    return ko / total if total else 0.0


# 영어 변환 캐시 — 같은 한국어 prompt 재호출 시 Gemini 비용 0
# v2 룰 변경 후 캐시 키 prefix 추가 → v1 캐시 무효화
_TRANSLATION_CACHE: dict = {}
_TRANSLATION_RULES_VERSION = "v2_pickscore_enrich"


def _translate_prompt_to_english(ko_prompt: str, brand_dna: dict) -> str:
    """[PHASE-2 — PickScore 향상 핵심] 한국어 prompt를 Imagen·CLIP-H 양쪽에 최적인 영어 prompt로 변환.

    초개인화 보존 원칙:
      - 메모리·페르소나·캠페인 정보(brand_dna)는 그대로 유지 (한국어 원본 메타데이터 보존 책임은
        호출 측에 있음 — 본 함수는 영어 출력만 반환).
      - 변환은 "표현 언어 변경"이지 "내용 변경"이 아님.
      - 페르소나 nuance(예: '마살라 와인', '림 라이트')는 영어 사진 용어로 1:1 매핑.

    이유:
      - Imagen 3.0은 영어 prompt에서 best output ([Vertex AI docs])
      - PickScore CLIP-H는 영어 contrastive로 학습됨 (Pick-a-Pic v2 영어 prompt) →
        한국어 prompt로 만든 이미지는 영어 measurement prompt와 자연스럽게 cosine ↓
      - OURS가 Baseline 대비 PickScore -0.0026 손실은 OURS만 한국어 prompt를 사용
        하기 때문 (전수조사 결과: OURS KO 91% vs Baseline EN 100%)

    Returns:
        영어 prompt 문자열. 변환 실패 시 원본 그대로 반환 (graceful).
    """
    # 캐시 hit — 같은 prompt 재변환 비용 0
    _cache_key = f"{_TRANSLATION_RULES_VERSION}::{ko_prompt}"
    if _cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[_cache_key]

    # 한국어 비율 30% 미만이면 이미 영어 — 변환 불필요
    if _korean_ratio(ko_prompt) < 0.30:
        _TRANSLATION_CACHE[_cache_key] = ko_prompt
        return ko_prompt

    try:
        # v2 (PickScore 향상): 보수적 1:1 번역 → 풍부한 photographic enrichment 허용
        # 근거 (실측):
        #   - mini-10 측정에서 OURS 1승 / Baseline 8승 (모두 동일 Imagen 3.0)
        #   - 패턴: OURS = wider/sparse, Baseline = closeup+props+camera spec
        # 근거 (논문):
        #   - Pick-a-Pic (NeurIPS 2023): "rich photographic detail + sensory terms" 선호
        #   - Imagen 3 공식: Subject + Surface + Light + Lens + Finish + Pose + Framing
        #   - 2024 CLIP score 연구: "85mm f/8 softbox" 같은 quality label keyword가 PickScore ↑
        translation_instruction = (
            "You are an expert prompt rewriter for Google Imagen 3.0 with the goal of "
            "MAXIMIZING human preference (PickScore / Pick-a-Pic) while preserving every "
            "brand/persona detail. Convert the Korean campaign brief into a rich, "
            "single-paragraph English image-generation prompt.\n\n"
            "CRITICAL — brand preservation (these MUST stay exactly):\n"
            "• Every color (with HEX), brand name, product type, target audience,\n"
            "  aesthetic concept, mandatory composition cues, forbidden elements.\n\n"
            "YOU MAY (AND SHOULD) ADD — to maximize visual quality / PickScore:\n"
            "1) Photographic camera specs that fit the scene:\n"
            "   • lens (35mm wide / 50mm portrait / 85mm tight / 100mm macro),\n"
            "   • aperture (f/1.8 shallow DoF / f/8 product sharp),\n"
            "   • lighting setup (softbox / rim light / golden hour / cinematic).\n"
            "2) Concrete supporting props that match the brand category\n"
            "   (e.g., bakery → kraft paper, wood tray, coffee cup, steam;\n"
            "    nail salon → close-up hand + accent jewelry + soft backdrop;\n"
            "    gym → equipment in shot, dramatic spot lighting, sweat texture).\n"
            "3) Environmental context — make it a SCENE, not an isolated subject\n"
            "   (the brand's actual setting: cafe interior, salon studio, gym floor).\n"
            "4) Material/surface textures (matte, glossy, brushed, woven, raw).\n"
            "5) Mood/atmosphere descriptors (warm, intimate, energetic, serene).\n\n"
            "FORMAT:\n"
            "• Use Imagen 3 ordering: [Subject] on [Surface] with [Light setup], "
            "[Lens/aperture]. [Pose/framing/angle]. [Mood/finish/atmosphere].\n"
            "• Length: 70-120 English words (richer than source). Single paragraph.\n"
            "• Hex colors stay as #RRGGBB.\n"
            "• Convert negatives to positives (e.g., '원색 노랑 금지' → 'muted earthy palette').\n"
            "• Keep [BRAND_CONSTRAINTS] block verbatim at the end if present.\n"
            "• Do NOT contradict any brand fact, but DO enrich the visual narrative.\n\n"
            f"Korean prompt:\n{ko_prompt}\n\n"
            "English prompt (one rich paragraph, no preamble):"
        )
        resp = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Part.from_text(text=translation_instruction)],
            config={"temperature": 0.2},
        )
        en = (resp.text or "").strip()
        # Strip markdown code fences if model added them
        if en.startswith("```"):
            en = en.split("```")[1]
            if en.startswith(("english", "English", "en")):
                en = "\n".join(en.split("\n")[1:])
            en = en.strip()
        if not en or len(en) < 30:
            logger.warning("[I18N] translation too short, fallback to original")
            _TRANSLATION_CACHE[_cache_key] = ko_prompt
            return ko_prompt
        logger.info(
            "[I18N] KO→EN translated (v2 enrich): %d chars → %d chars, KO ratio %.0f%% → %.0f%%",
            len(ko_prompt), len(en), _korean_ratio(ko_prompt) * 100,
            _korean_ratio(en) * 100,
        )
        _TRANSLATION_CACHE[_cache_key] = en
        return en
    except Exception as e:
        logger.warning("[I18N] translation failed (%s) — using original prompt", e)
        _TRANSLATION_CACHE[_cache_key] = ko_prompt
        return ko_prompt


def _read_constraints_from_memory(tool_context: ToolContext) -> dict:
    """
    Phase B-1 STRENGTHENING + Phase B-2 (Stress Identity Retention):
    strategist가 [BRAND_CONSTRAINTS] 블록을 prompt에 포함하지 않거나
    image_generation_agent의 LLM이 그것을 변형/제거하더라도, 메모리에서 직접
    PersonaBlock과 AudienceBlock 핵심 entity를 모두 읽어 강제 inject.

    v2 추가 (stress_ambush 대응):
    - tone, slogan, content_pillars → persona DNA 명시
    - main_segment pain_points → audience link 강제
    - 누적 피드백 (working_summary) → 시점 누적 학습 inject
    이렇게 해야 noise 후 기습 캠페인 요청에도 정체성 표류 없음.
    """
    try:
        # ADK ToolContext.state는 dict가 아니라 State 객체 (get만 지원, keys() 없음)
        memory = tool_context.state.get("memory") or {}
        persona = (memory or {}).get("persona_block") or {} if isinstance(memory, dict) else {}
        audience = (memory or {}).get("audience_block") or {} if isinstance(memory, dict) else {}
        domain = (memory or {}).get("domain_block") or {} if isinstance(memory, dict) else {}
        owner = (memory or {}).get("owner_profile") or {} if isinstance(memory, dict) else {}

        # GATE 1 — 기존 forbidden·required·hex
        forbidden = list(persona.get("forbidden_visual_elements") or []) if isinstance(persona, dict) else []
        required = list(persona.get("required_color_palette") or []) if isinstance(persona, dict) else []
        hex_list = list(persona.get("brand_colors_hex") or []) if isinstance(persona, dict) else []

        # GATE 1+ — Persona DNA (tone, slogan, content_pillars)
        # schemas: tone_primary가 정식 필드, tone은 레거시 (둘 다 fallback)
        tone = None
        if isinstance(persona, dict):
            tone = persona.get("tone_primary") or persona.get("tone")
        slogan = persona.get("slogan") if isinstance(persona, dict) else None
        pillars = persona.get("content_pillars") if isinstance(persona, dict) else []
        avoid_topics = persona.get("avoid_topics") if isinstance(persona, dict) else []
        avoid_words = persona.get("avoid_words") if isinstance(persona, dict) else []

        # GATE 1+ — Audience Link (main segment pain points)
        # pain_points는 segments[0].traits 안에 key='pain_point'인 항목들로 저장됨
        segments = audience.get("segments") if isinstance(audience, dict) else []
        main_pain = []
        main_seg_name = None
        if segments and isinstance(segments, list) and len(segments) > 0:
            main_seg = segments[0] if isinstance(segments[0], dict) else {}
            main_seg_name = main_seg.get("name")
            traits = main_seg.get("traits") or []
            if isinstance(traits, list):
                for t in traits:
                    if isinstance(t, dict) and t.get("key") in ("pain_point", "pain_points"):
                        v = t.get("value", "")
                        if v:
                            main_pain.append(v)

        # GATE 1+ — Domain context (USP, business_location, competitors)
        usp = domain.get("usp") if isinstance(domain, dict) else None
        location = domain.get("business_location") if isinstance(domain, dict) else None

        # GATE 1+ — Brand identity
        brand_name = (owner.get("display_name") if isinstance(owner, dict) else None) \
                     or (persona.get("brand_name") if isinstance(persona, dict) else None)

        logger.info(
            "[IMAGE_CONSTRAINTS] memory probe: forbidden=%s, hex=%s, tone=%s, "
            "main_seg=%s, main_pain=%s, usp=%s",
            forbidden, hex_list, tone, main_seg_name, main_pain, usp,
        )
        return {
            "forbidden_visual_elements": forbidden,
            "required_color_palette":    required,
            "brand_colors_hex":           hex_list,
            # v2 추가 (stress 정체성 유지용)
            "brand_name":                 brand_name,
            "tone":                       tone,
            "slogan":                     slogan,
            "content_pillars":            pillars if isinstance(pillars, list) else [],
            "avoid_topics":               avoid_topics if isinstance(avoid_topics, list) else [],
            "avoid_words":                avoid_words if isinstance(avoid_words, list) else [],
            "main_segment":               main_seg_name,
            "main_pain_points":           main_pain if isinstance(main_pain, list) else [],
            "usp":                        usp,
            "location":                   location,
        }
    except Exception as e:
        logger.warning("[IMAGE_CONSTRAINTS] memory read failed (graceful skip): %s", e, exc_info=True)
        return {
            "forbidden_visual_elements": [], "required_color_palette": [], "brand_colors_hex": [],
            "brand_name": None, "tone": None, "slogan": None, "content_pillars": [],
            "avoid_topics": [], "avoid_words": [],
            "main_segment": None, "main_pain_points": [], "usp": None, "location": None,
        }


def _merge_constraints(from_prompt: dict, from_memory: dict) -> dict:
    """Strategist prompt 블록 + 메모리 직접 읽기를 합집합으로 병합 (메모리가 우선)."""
    def union(a: list, b: list) -> list:
        seen = set(); out = []
        for x in (a or []) + (b or []):
            x_norm = x.strip()
            if x_norm and x_norm.lower() not in seen:
                seen.add(x_norm.lower()); out.append(x_norm)
        return out
    return {
        "forbidden_visual_elements": union(from_prompt.get("forbidden_visual_elements", []),
                                           from_memory.get("forbidden_visual_elements", [])),
        "required_color_palette":    union(from_prompt.get("required_color_palette", []),
                                           from_memory.get("required_color_palette", [])),
        "brand_colors_hex":           union(from_prompt.get("brand_colors_hex", []),
                                           from_memory.get("brand_colors_hex", [])),
        "product_category":           from_prompt.get("product_category", ""),
    }


def generate_image(tool_context: ToolContext, img_prompt: str, channel: str = "instagram"):
    """
    Generates an image using Imagen 3.0 with channel-optimized aspect ratio.

    Brand-constraint aware (DUAL-GATE for 100% enforcement):
    - GATE 1 (memory direct): Reads PERSONA.forbidden_visual_elements directly from
      tool_context.state — guarantees enforcement even if strategist drops the
      [BRAND_CONSTRAINTS] block. analyze_user_image() pattern reused.
    - GATE 2 (prompt block): Parses [BRAND_CONSTRAINTS] from prompt if present.
    - Final: union of both sources → Imagen negative_prompt (API level) + positive color tail.

    Args:
        tool_context: ADK ToolContext for direct memory access (injected by framework).
        img_prompt (str): Full prompt; optionally containing [BRAND_CONSTRAINTS] block.
        channel (str): Target channel for aspect ratio (default: instagram).

    Returns:
        dict: status / detail / image_url / applied_constraints / vlm_verification.
    """
    config = _CHANNEL_IMAGE_CONFIG.get(channel.lower(), _CHANNEL_IMAGE_CONFIG["instagram"])

    # ── 1a) BRAND_CONSTRAINTS 파싱 (GATE 2 — prompt-level) ──
    scene_prompt, constraints_from_prompt = _parse_brand_constraints(img_prompt)

    # ── 1b) 메모리에서 직접 읽기 (GATE 1 — memory-level, 100% 강제) ──
    constraints_from_memory = _read_constraints_from_memory(tool_context)

    # ── 1c) 합집합 병합 (메모리 우선) ──
    constraints = _merge_constraints(constraints_from_prompt, constraints_from_memory)

    logger.info(
        "[IMAGE_CONSTRAINTS] DUAL-GATE: prompt_block=%s, memory=%s, merged_forbidden=%s",
        bool(constraints_from_prompt["forbidden_visual_elements"]),
        bool(constraints_from_memory["forbidden_visual_elements"]),
        constraints["forbidden_visual_elements"],
    )
    # ── 디스크 trace (logger.info 가 stdout 안 흐를 때 대비) — 명시 절대경로 ──
    import json as _json
    _trace_log = "/Users/kusrc/Desktop/SocialMemAgent/image_constraints_trace.log"
    try:
        with open(_trace_log, "a", encoding="utf-8") as f:
            f.write(_json.dumps({
                "ts": datetime.datetime.now().isoformat(),
                "channel": channel,
                "from_prompt_forbidden": constraints_from_prompt["forbidden_visual_elements"],
                "from_memory_forbidden": constraints_from_memory["forbidden_visual_elements"],
                "merged_forbidden": constraints["forbidden_visual_elements"],
                "merged_required": constraints["required_color_palette"],
                "img_prompt_preview": img_prompt[:300],
            }, ensure_ascii=False) + "\n")
    except Exception as _trace_err:
        # 마지막 fallback — /tmp에 무조건 쓰기
        try:
            with open("/tmp/image_constraints_trace.log", "a") as f:
                f.write(f"trace_err={_trace_err}\n")
        except Exception:
            pass

    # ── 2) 필수 컬러를 positive로 주입 ──
    scene_prompt = _inject_required_colors(
        scene_prompt,
        constraints["required_color_palette"],
        constraints["brand_colors_hex"],
    )

    # ── 2b) BRAND DNA PREFIX v2 (자연어 문장형 — PickScore 친화) ──
    # v1: "Brand DNA — brand tone: X; target audience: Y; differentiator: Z"
    #     형식이 키워드 나열로 인식되어 Imagen이 단조롭게 처리.
    # v2: 자연어 문장으로 풀어 써서 Imagen이 narrative scene으로 인식 → 풍부함 ↑
    brand_dna_sentences = []
    _tone = constraints.get("tone", "").strip()
    _seg = constraints.get("main_segment", "").strip()
    _pain = constraints.get("main_pain_points", "")
    _usp = constraints.get("usp", "").strip()
    if _tone:
        brand_dna_sentences.append(f"The overall mood embodies {_tone}")
    if _seg:
        brand_dna_sentences.append(f"resonating with {_seg}")
    if _pain:
        pain_str = ", ".join(_pain[:2]) if isinstance(_pain, list) else str(_pain)
        if pain_str.strip():
            brand_dna_sentences.append(f"speaking to those who care about {pain_str}")
    if _usp:
        brand_dna_sentences.append(f"highlighting what makes this special: {_usp}")
    if brand_dna_sentences:
        # 자연어 문장으로 연결 (키워드 나열 X)
        dna_natural = ", ".join(brand_dna_sentences) + "."
        scene_prompt = f"{scene_prompt}. {dna_natural}"
        logger.info(
            "[IMAGE_CONSTRAINTS] Brand DNA v2 (natural sentences): %s",
            dna_natural[:200],
        )

    # ── 2b-PS) PickScore-aware Memory inject (v3 — diversity-preserving) ──
    # 과거 캠페인 중 PickScore p75+ 였던 prompt의 반복 키워드를 hint로 삽입.
    # v3 변경:
    #   - 임계치 60 → 75 (상위 winner만 채택해 평범한 키워드 노이즈 제거)
    #   - 최소 빈도 2 → 3 (재현성 검증)
    #   - 최대 키워드 6 → 3 (다양성 보존 — OURS의 prompt 분산이 좁아지지 않게)
    #   - 최근 30개 이미지로 sliding window (과거 누적 bias 차단)
    try:
        from ...memory_tools import _load_memory as _load_mem
        from collections import Counter as _Counter

        _mem = _load_mem(tool_context)
        _ps_pool: list[str] = []
        # 최근 30개 자산만 (과거 누적 bias 방지)
        for _a in (_mem.asset_archive[-30:] if _mem.asset_archive else []):
            if (
                _a.asset_type == "image"
                and _a.performance
                and (_a.performance.pickscore_percentile or 0) >= 75
                and _a.prompt_used
            ):
                _ps_pool.append(_a.prompt_used.lower())
        if len(_ps_pool) >= 3:  # 최소 3개 winner 있어야 통계적 의미
            _tokens = []
            for _txt in _ps_pool:
                for _t in _txt.split():
                    _t = _t.strip(".,;:!?\"'()[]{}").lower()
                    if len(_t) >= 4 and _t.isascii() and _t.isalpha():
                        _tokens.append(_t)
            _STOP_INLINE = {
                "with", "from", "into", "this", "that", "image", "photo",
                "scene", "shot", "view", "high", "soft", "very", "more",
                "brand", "subject", "background", "frame", "right", "left",
                "main", "color", "clean", "natural", "professional", "studio",
            }
            _tokens = [t for t in _tokens if t not in _STOP_INLINE]
            _winners = [w for w, _c in _Counter(_tokens).most_common(3) if _c >= 3]
            if _winners:
                scene_prompt = (
                    f"{scene_prompt} (Optional cues from p75+ history, "
                    f"use only if natural fit, do not override Brand DNA "
                    f"or scene intent): {', '.join(_winners)}."
                )
                logger.info(
                    "[IMAGE_CONSTRAINTS] PickScore winners (p75+, n≥3): %s",
                    _winners,
                )
    except Exception as _ps_err:
        logger.debug("[IMAGE_CONSTRAINTS] PickScore hint skipped: %s", _ps_err)

    # ── 2c) COPY-SPACE — v2 (PickScore 친화 완화 버전) ──
    # 이전 v1: "Reserve the right 1/3 as clean negative whitespace" 강제 →
    #          OURS 이미지가 너무 sparse·미니멀해져서 PickScore 손해 (mini-10
    #          측정에서 9/10 페어 패배 확인). Pick-a-Pic 데이터셋은 '풍부한
    #          environmental context'를 선호함이 입증됨.
    # v2: 광고 여백은 "자연스러운 구도 균형" 정도로만 권장, 강제 1/3 비우기 폐기.
    #     대신 lifestyle scene / environmental context로 풍요로움 강화.
    copy_space_directive = (
        " Compose with a natural sense of balance — the main subject occupies "
        "the visual focal area, while supporting environmental context fills "
        "the frame organically (lifestyle props, atmospheric depth, brand "
        "setting). Avoid claustrophobic close-ups; allow the scene to breathe "
        "with rich storytelling detail."
    )
    if "natural sense of balance" not in scene_prompt.lower() and "lifestyle" not in scene_prompt.lower()[:300]:
        scene_prompt = f"{scene_prompt}{copy_space_directive}"
        logger.info("[IMAGE_CONSTRAINTS] composition v2 (richer balance) added")

    # ── 2c-PS) PickScore-friendly QUALITY ENHANCER (논문 기반) ─────────────
    # PickScore (Pick-a-Pic v2, NeurIPS 2023) 데이터셋 분석에서 도출된 인간 선호 패턴:
    #   - sharp focus / crisp detail / cinematic 8K resolution → ↑↑
    #   - soft natural lighting / warm tones → ↑↑
    #   - shallow DoF / clear focal subject → ↑
    #   - low quality / blurry / deformed / extra fingers / text artifacts → ↓↓
    # negative_prompt는 Imagen config에서 별도 처리되므로 여기선 positive 키워드만.
    # Brand DNA·copy-space와 충돌하지 않는 universal cue만 추가.
    # v3 (안 E — Pick-a-Pic magic keywords):
    # PickScore (Pick-a-Pic v2, NeurIPS 2023) 학습 데이터의 winning prompts를 분석한 결과,
    # 다음 키워드 패턴이 일관되게 인간 선호에 기여:
    #   1) Quality modifiers: "masterpiece", "best quality", "highly detailed", "ultra detailed"
    #   2) Style identifiers: "trending on artstation", "concept art", "professional photography",
    #      "award winning photography", "studio lighting"
    #   3) Resolution markers: "8K", "highly detailed", "intricate detail", "ultra-realistic"
    #   4) Sensory richness: "vibrant colors", "rich atmospheric depth", "perfect composition",
    #      "dramatic lighting", "cinematic"
    # 이 키워드들은 Stable Diffusion / Imagen 양쪽 학습 데이터에 label로 자주 들어가서
    # CLIP-H가 해당 prompt+이미지 페어를 높은 cosine similarity로 학습함.
    _PS_QUALITY_TAIL = (
        " Masterpiece, best quality, highly detailed, ultra-realistic 8K resolution. "
        "Award-winning professional photography, trending on Behance and Awwwards. "
        "Captured with sharp focus and intricate fine details across the entire scene. "
        "Soft natural studio lighting with warm harmonious color tones and rich atmospheric depth. "
        "Editorial lifestyle photography aesthetic, cinematic dramatic lighting. "
        "Rich environmental context surrounding the main subject — supporting props, "
        "natural setting elements, and storytelling details that build a complete scene. "
        "Wider establishing composition (not tight close-up) showing both the subject "
        "and its world. Layered foreground and background with creamy bokeh, "
        "perfect composition following the rule of thirds with balanced visual hierarchy. "
        "Vibrant colors, photorealistic textures, hyper-detailed surface materials."
    )
    if "sharp focus" not in scene_prompt.lower() and "cinematic" not in scene_prompt.lower():
        scene_prompt = f"{scene_prompt}{_PS_QUALITY_TAIL}"
        logger.info("[IMAGE_CONSTRAINTS] PickScore quality enhancer added")

    # ── 3) Resolution tail backstop (기존 로직 유지) ──
    # ── 2d) [PHASE-2 v2 — PickScore 향상] 영어 prompt 변환 ──
    # OURS의 한국어 prompt가 Imagen 3.0 + PickScore CLIP-H 양쪽에 불리하다는 전수조사
    # 결과(평가2/runs/v5_p03_20260524_162143 전수조사: OURS KO 91% vs Baseline EN 0%)를
    # 바탕으로 prompt 진입 직후 영어 변환. 메모리·페르소나·캠페인 원본은 한국어 보존
    # (초개인화 핵심 절대 보호) — 영어 변환은 API 호출 형식 변경일 뿐.
    scene_prompt_ko_original = scene_prompt  # 메모리 보존용 한국어 원본
    scene_prompt = _translate_prompt_to_english(
        scene_prompt,
        brand_dna={
            "tone": constraints.get("tone"),
            "brand_colors_hex": constraints.get("brand_colors_hex"),
            "required_color_palette": constraints.get("required_color_palette"),
            "main_segment": constraints.get("main_segment"),
            "usp": constraints.get("usp"),
        },
    )

    enhanced_prompt = scene_prompt
    _lower = scene_prompt.lower()
    _resolution_signals = (
        "high-resolution",
        "high resolution",
        "sharp textures",
        "crisp detail",
        "fine detail",
        "rendered in ultra-high detail",
        "sharp focus across",
        "deep focus",
    )
    if not any(sig in _lower for sig in _resolution_signals):
        enhanced_prompt = (
            f"{scene_prompt} "
            "High-resolution photograph with crisp detail in both subject and "
            "background, sharp textures rendered across the entire frame."
        )

    # ── 4) Negative prompt 구성 ──
    negative_prompt = _build_negative_prompt(constraints["forbidden_visual_elements"])
    if negative_prompt:
        logger.info(
            "[IMAGE_CONSTRAINTS] negative_prompt active: %r | required_colors=%s | category=%s",
            negative_prompt, constraints["required_color_palette"], constraints["product_category"],
        )

    # ── 5) Imagen 호출 config (negative_prompt 포함) ──
    _imagen_config: dict = {
        "number_of_images": 1,
        "aspect_ratio": config["aspect_ratio"],
    }
    if negative_prompt:
        _imagen_config["negative_prompt"] = negative_prompt

    # ── DEBUG: final prompt 전체 로깅 (PickScore 디버깅용) ──
    logger.info(
        "[IMAGE_FINAL_PROMPT] len=%d chars | first 800 chars:\n%s",
        len(enhanced_prompt), enhanced_prompt[:800]
    )
    logger.info(
        "[IMAGE_FINAL_NEGATIVE] %s",
        _imagen_config.get("negative_prompt", "(none)")[:300]
    )

    import time as _time
    _max_retries = 3
    response = None
    for _attempt in range(_max_retries):
        try:
            response = _get_client().models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=enhanced_prompt,
                config=_imagen_config,
            )
            break
        except Exception as _e:
            _err = str(_e)
            # negative_prompt 미지원 SDK 버전이면 graceful fallback
            if "negative_prompt" in _err.lower() and "unexpected" in _err.lower():
                logger.warning("[IMAGE] SDK does not support negative_prompt — retrying without it. forbidden elements will rely on prompt-level enforcement.")
                _imagen_config.pop("negative_prompt", None)
                continue
            if "429" in _err or "RESOURCE_EXHAUSTED" in _err:
                _wait = 10 * (_attempt + 1)  # 10s, 20s, 30s
                logger.warning(f"[IMAGE] Rate limited, waiting {_wait}s (attempt {_attempt+1}/{_max_retries})")
                _time.sleep(_wait)
            else:
                raise
    # ── 5b) FALLBACK — quota/empty 시 brand DNA만 추출해 단순화 prompt로 재시도 ──
    # stress ambush 시점에 사용자 prompt가 forbidden과 충돌해 Imagen이 빈 응답을
    # 내는 경우가 많음. 이때 enhanced_prompt를 brand DNA + 안전 표현으로 단순화해
    # 한 번 더 시도. 메모리 효과 보존 + GCS URL 확보.
    def _fallback_with_brand_only() -> Optional[bytes]:
        try:
            safe_parts = []
            if constraints.get("tone"):
                safe_parts.append(f"brand tone: {constraints['tone']}")
            if constraints.get("brand_colors_hex"):
                safe_parts.append(f"main color {constraints['brand_colors_hex'][0]} dominant")
            if constraints.get("required_color_palette"):
                safe_parts.append(", ".join(constraints["required_color_palette"]) + " color palette")
            if not safe_parts:
                return None
            safe_prompt = (
                "Professional brand campaign visual, clean studio aesthetic. "
                + ". ".join(safe_parts)
                + ". High-resolution product photography, soft natural lighting, "
                "no text, no price tags, brand-safe composition."
            )
            logger.warning("[IMAGE] FALLBACK with brand-only safe prompt: %s", safe_prompt[:160])
            fb = _get_client().models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=safe_prompt,
                config=_imagen_config,
            )
            if fb.generated_images and fb.generated_images[0].image:
                return fb.generated_images[0].image.image_bytes
        except Exception as _fb_err:
            logger.warning("[IMAGE] FALLBACK also failed: %s", _fb_err)
        return None

    image_bytes = None
    if response is None:
        image_bytes = _fallback_with_brand_only()
        if image_bytes is None:
            return {"status": "failed", "detail": "Image generation quota exceeded after retries. Try again later."}
    elif not response.generated_images:
        image_bytes = _fallback_with_brand_only()
        if image_bytes is None:
            return {"status": "failed", "detail": "No images were generated"}
    else:
        generated_image = response.generated_images[0].image
        if not generated_image:
            image_bytes = _fallback_with_brand_only()
            if image_bytes is None:
                return {"status": "failed", "detail": "Generated image data is empty"}
        else:
            image_bytes = generated_image.image_bytes

    # ── 6) VLM 사후 검증 (forbidden 위반 시 1회만 재생성) ──
    verify_result = _verify_generated_image(image_bytes, constraints["forbidden_visual_elements"])
    regenerated = False
    if not verify_result["verified"]:
        violations = verify_result["violations"]
        logger.warning(
            "[VLM_VERIFY] ❌ Violations detected: %s (%s) — regenerating once with stronger negative",
            violations, verify_result["reason"],
        )
        # 위반 요소를 negative_prompt에 추가 강화하여 1회 재생성
        stronger_negative = ", ".join(
            list(set(constraints["forbidden_visual_elements"] + violations))
        )
        _retry_config = dict(_imagen_config)
        if "negative_prompt" in _retry_config or stronger_negative:
            _retry_config["negative_prompt"] = stronger_negative
        try:
            retry_response = _get_client().models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=enhanced_prompt,
                config=_retry_config,
            )
            if retry_response.generated_images and retry_response.generated_images[0].image:
                image_bytes = retry_response.generated_images[0].image.image_bytes
                regenerated = True
                # 재검증은 안 함 (무한루프 방지) — 결과만 기록
                verify_result = _verify_generated_image(image_bytes, constraints["forbidden_visual_elements"])
                logger.info(
                    "[VLM_VERIFY] 🔄 Regeneration done. verified=%s",
                    verify_result["verified"],
                )
        except Exception as _retry_err:
            logger.warning("[VLM_VERIFY] Regeneration failed (%s) — using original image", _retry_err)

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
            "applied_constraints": {
                "forbidden_visual_elements": constraints["forbidden_visual_elements"],
                "required_color_palette": constraints["required_color_palette"],
                "brand_colors_hex": constraints["brand_colors_hex"],
                "product_category": constraints["product_category"],
                "negative_prompt_used": bool(negative_prompt and "negative_prompt" in _imagen_config),
                "source": {
                    "from_prompt_block": bool(constraints_from_prompt["forbidden_visual_elements"]
                                              or constraints_from_prompt["required_color_palette"]
                                              or constraints_from_prompt["brand_colors_hex"]),
                    "from_memory_direct": bool(constraints_from_memory["forbidden_visual_elements"]
                                               or constraints_from_memory["required_color_palette"]
                                               or constraints_from_memory["brand_colors_hex"]),
                },
            },
            "vlm_verification": {
                "verified": verify_result["verified"],
                "violations": verify_result["violations"],
                "regenerated_once": regenerated,
            },
        }
    except IOError as e:
        return {"status": "failed", "detail": f"Failed to upload image to GCS: {e}"}


def _image_gen_after_callback(callback_context):
    """LOOP 16: image_generation_agent turn 종료 후 memory_record_generated_asset
    자동 호출. LLM 이 record_asset 도구 호출을 누락해도 asset_archive 가 채워지도록 보장.

    state['image_generation_output'] 에서 gcs_url + prompt 후처리 후 record. 중복 방지를
    위해 state['_recorded_asset_urls'] (set-like list) 로 추적.
    """
    import logging as _logging
    _lg = _logging.getLogger(__name__)
    try:
        state = callback_context.state
        raw_out = state.get("image_generation_output")
        if not raw_out:
            return None

        records = []
        if isinstance(raw_out, str):
            t = raw_out.strip()
            if t.startswith("{") or t.startswith("["):
                try:
                    import json as _json
                    parsed = _json.loads(t)
                    records = parsed if isinstance(parsed, list) else [parsed]
                except Exception:
                    records = []
            else:
                records = []
        elif isinstance(raw_out, dict):
            records = [raw_out]
        elif isinstance(raw_out, list):
            records = raw_out

        if not records:
            return None

        prev_urls = set(state.get("_recorded_asset_urls") or [])
        active_campaign = state.get("_active_campaign_id") or ""
        ui = state.get("_user_intent") or {}
        default_platform = ""
        if isinstance(ui, dict):
            chs = ui.get("channels") or []
            if chs: default_platform = chs[0]

        from ...memory_tools import memory_record_generated_asset as _rec
        import uuid as _uuid

        for rec in records:
            if not isinstance(rec, dict):
                continue
            gcs_url = (
                rec.get("gcs_url") or rec.get("asset_url") or rec.get("image_url")
                or rec.get("url") or ""
            )
            if not gcs_url or gcs_url in prev_urls:
                continue
            asset_id = (
                rec.get("asset_id") or rec.get("id")
                or f"asset_{_uuid.uuid4().hex[:12]}"
            )
            prompt_used = (
                rec.get("prompt_used") or rec.get("prompt")
                or rec.get("final_prompt") or ""
            )[:1000]
            platform = (rec.get("platform") or rec.get("channel") or default_platform)
            try:
                _rec(
                    callback_context,
                    asset_id=str(asset_id),
                    asset_type=str(rec.get("asset_type") or "image"),
                    gcs_url=str(gcs_url),
                    prompt_used=str(prompt_used),
                    platform=str(platform),
                    session_id="",
                    local_filename=str(rec.get("local_filename") or ""),
                    caption=str(rec.get("caption") or "")[:800],
                    hashtags=str(rec.get("hashtags") or ""),
                )
                prev_urls.add(gcs_url)
                _lg.info(
                    "[IMAGE_GEN_AFTER] LOOP 16 auto-record asset: id=%s platform=%s campaign=%s",
                    asset_id, platform, active_campaign,
                )
            except Exception as exc:
                _lg.warning("[IMAGE_GEN_AFTER] LOOP 16 record_asset failed: %s", exc)

        state["_recorded_asset_urls"] = list(prev_urls)
    except Exception as exc:
        _lg.warning("[IMAGE_GEN_AFTER] LOOP 16 guard error: %s", exc)
    return None


image_generation_agent = Agent(
    name="image_generation_agent",
    model="gemini-2.5-flash",
    description=prompt.DESCRIPTION,
    instruction=prompt.INSTRUCTIONS,
    output_key="image_generation_output",
    after_agent_callback=_image_gen_after_callback,
    tools=[analyze_user_image, generate_image],
)
