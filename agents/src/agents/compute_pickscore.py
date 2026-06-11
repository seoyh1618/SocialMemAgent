"""PickScore (CLIP-H / Pick-a-Pic v2) — image-prompt preference score.

PickScore-aware Performance Memory의 핵심 측정 모듈.
- 모델: HuggingFace `yuvalkirstain/PickScore_v1`
- 프로세서: `laion/CLIP-ViT-H-14-laion2B-s32B-b79K`
- 출력: 0-1 sigmoid (높을수록 prompt-image 적합성 ↑)

이미지 생성 직후 자동 호출 → CampaignRecord.performance.pickscore 에 저장.
나중에 memory_search_campaigns가 PickScore 상위 캠페인을 우선 노출.

설계 원칙:
- 모델 로드는 lazy + 1회 캐시 (warm 호출 비용 ≈ 100ms).
- 외부 망/torch 미설치 환경에선 silent fail → None 반환 (이미지 저장 자체는 막지 않음).
- bytes / file path / URL 셋 모두 입력 가능.
"""

from __future__ import annotations

import io
import logging
import math
from pathlib import Path
from typing import Optional, Union
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_CACHE: dict = {"model": None, "processor": None, "init_failed": False}

ImageInput = Union[bytes, str, Path]


def _load_model_once() -> bool:
    """Initialize PickScore + CLIP-H once; return True if usable."""
    if _CACHE["model"] is not None:
        return True
    if _CACHE["init_failed"]:
        return False
    try:
        from transformers import AutoModel, AutoProcessor
        _CACHE["processor"] = AutoProcessor.from_pretrained(
            "laion/CLIP-ViT-H-14-laion2B-s32B-b79K"
        )
        _CACHE["model"] = AutoModel.from_pretrained(
            "yuvalkirstain/PickScore_v1"
        ).eval()
        logger.info("[PICKSCORE] ✅ model loaded (yuvalkirstain/PickScore_v1)")
        return True
    except Exception as e:
        _CACHE["init_failed"] = True
        logger.warning("[PICKSCORE] ⚠ init failed: %s", e)
        return False


def _load_image(src: ImageInput):
    """bytes / path / url → PIL.Image (RGB)."""
    from PIL import Image
    if isinstance(src, bytes):
        return Image.open(io.BytesIO(src)).convert("RGB")
    if isinstance(src, Path):
        return Image.open(src).convert("RGB")
    if isinstance(src, str):
        if src.startswith(("http://", "https://")):
            req = Request(src, headers={"User-Agent": "pickscore/1.0"})
            with urlopen(req, timeout=10) as resp:
                data = resp.read()
            return Image.open(io.BytesIO(data)).convert("RGB")
        return Image.open(src).convert("RGB")
    raise TypeError(f"Unsupported image input: {type(src)}")


def _compute_logit_and_cosine(image: ImageInput, prompt_text: str) -> Optional[tuple]:
    """내부 헬퍼 — (logit_with_scale, raw_cosine) 둘 다 반환.

    logit_with_scale: model.logit_scale.exp() × cosine — PickScore 논문 원본 점수
    raw_cosine: scale 미적용 cosine ∈ [-1, 1] — CLIP 의미적 유사도 raw

    이 둘이 있으면 어떤 sigmoid 온도든 호출 측에서 자유롭게 적용 가능.
    """
    if not prompt_text:
        return None
    if not _load_model_once():
        return None
    try:
        import torch
        model = _CACHE["model"]
        proc = _CACHE["processor"]

        img = _load_image(image)
        img_inputs = proc(images=[img], padding=True, truncation=True,
                          max_length=77, return_tensors="pt")
        txt_inputs = proc(text=prompt_text[:300],
                          padding=True, truncation=True,
                          max_length=77, return_tensors="pt")

        with torch.no_grad():
            img_out = model.get_image_features(**img_inputs)
            txt_out = model.get_text_features(**txt_inputs)

            def _extract(out):
                if isinstance(out, torch.Tensor):
                    return out
                for attr in ("pooler_output", "image_embeds", "text_embeds"):
                    v = getattr(out, attr, None)
                    if isinstance(v, torch.Tensor):
                        return v
                if hasattr(out, "last_hidden_state"):
                    return out.last_hidden_state[:, 0, :]
                return out

            img_emb = _extract(img_out)
            txt_emb = _extract(txt_out)
            img_emb = img_emb / torch.norm(img_emb, dim=-1, keepdim=True)
            txt_emb = txt_emb / torch.norm(txt_emb, dim=-1, keepdim=True)
            raw_cos = (txt_emb @ img_emb.T)[0][0].item()
            scaled_logit = model.logit_scale.exp().item() * raw_cos

        return (scaled_logit, raw_cos)
    except Exception as e:
        logger.warning("[PICKSCORE] ⚠ compute failed: %s", e)
        return None


def compute_pickscore(image: ImageInput, prompt_text: str) -> Optional[float]:
    """[LEGACY — 비포 비교용] 이미지-prompt 적합성 PickScore (0-1 sigmoid, 온도 10).

    ⚠ 이 함수는 sigmoid 온도 10을 적용해 출력 분포가 [0.82, 0.84]에 압축됨 →
    변별력 낮음. 기존 메모리 percentile / winner 임계치(75) 호환성 위해 유지.
    신규 측정·평가는 `compute_pickscore_v2()` 권장.

    Returns:
        0.0~1.0 (None = 측정 실패)
    """
    pair = _compute_logit_and_cosine(image, prompt_text)
    if pair is None:
        return None
    scaled_logit, _ = pair
    return 1.0 / (1.0 + math.exp(-scaled_logit / 10.0))


def compute_pickscore_v2(image: ImageInput, prompt_text: str) -> Optional[dict]:
    """[NEW — 애프터, 권장] 변별력 보존 PickScore + raw cosine 동시 반환.

    실측 비교 (P03 18장, before_after_raw.json):
      - legacy sigmoid t=10: 분산 폭 0.0085 (변별력 1.00x, baseline)
      - raw cosine:           분산 폭 0.0061 (변별력 0.72x, 더 나쁨)
      - sigmoid t=1:          분산 폭 0.0000 (완전 포화, 무용)
      - **scaled_logit:       분산 폭 0.6045 (변별력 71x — 진짜 정답)**

    → Pick-a-Pic 논문의 원본 점수(scaled_logit = logit_scale × cosine)가
      sigmoid를 거치기 전 단계라 분포 압축이 없고, M1 SCA Norm을 통한
      min-max 정규화에서도 변별력을 유지함. **메모리·평가에는 scaled_logit**.

    반환되는 세 신호:
      - `raw_cosine`: ∈ [-1, 1], CLIP-H cosine. 평균 0.16, 폭 0.006 (변별력 낮음).
      - `scaled_logit`: logit_scale × cosine. 평균 15-16, 폭 0.4-0.8 (**권장**).
      - `sigmoid_t1`: 표준 sigmoid. CLIP-H logit이 너무 커서 거의 1.0으로 포화 (무용).

    호출 측 선택:
      - **메모리 percentile / Norm / reranking → `scaled_logit`** (변별력 최대)
      - 0-1 표시가 필요할 때 → min-max Norm 후 [0, 1] (sigmoid는 쓰지 말 것)
      - legacy 호환 → `compute_pickscore()` (sigmoid t=10) 유지

    Returns:
        {"raw_cosine": float, "scaled_logit": float, "sigmoid_t1": float} | None
    """
    pair = _compute_logit_and_cosine(image, prompt_text)
    if pair is None:
        return None
    scaled_logit, raw_cos = pair
    return {
        "raw_cosine": raw_cos,
        "scaled_logit": scaled_logit,
        "sigmoid_t1": 1.0 / (1.0 + math.exp(-scaled_logit)),
    }


def fetch_image_bytes(url: str, timeout: int = 10) -> Optional[bytes]:
    """GCS URL → bytes. 실패 시 None."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        req = Request(url, headers={"User-Agent": "pickscore/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        logger.warning("[PICKSCORE] ⚠ fetch failed for %s: %s", url[:80], e)
        return None


def compute_percentile(value: float, history: list[float]) -> float:
    """history 안에서 value의 백분위 (0-100).

    Args:
        value: 이번에 측정된 PickScore
        history: 같은 페르소나의 과거 PickScore 목록 (None 제외 후 전달)

    Returns:
        0.0 (최하위) ~ 100.0 (최상위). history가 비면 50.0.
    """
    cleaned = [h for h in history if h is not None]
    if not cleaned:
        return 50.0
    below = sum(1 for h in cleaned if h <= value)
    return round(below / len(cleaned) * 100.0, 1)
