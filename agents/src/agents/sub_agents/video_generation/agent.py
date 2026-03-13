import os
import datetime
import time
import logging

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext
from google.cloud import storage
from google.genai import Client
from google.genai.types import GenerateVideosConfig, Image
from agents.utils.gcs_url_converters import gcs_uri_to_public_url, public_url_to_gcs_uri
from agents.sub_agents.audio_generation.agent import generate_audio
from agents.video_editing_tools import assemble_video_with_audio

from . import prompt
load_dotenv()

logger = logging.getLogger(__name__)

client = Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
)

# Initialize Google Cloud Storage client
storage_client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
GCS_BUCKET_NAME = "social-media-agent-assets"  # Public to internet


def generate_video(video_prompt: str, image_gcs_uri: str):
    """
    Generates a soundless video based on an prompt text and optionally an image.

    If you don't have an image, simply set the image_gcs_uri to empty string.

    Args:
        video_prompt (str): The prompt for video generation.
        image_gcs_uri (str): The GCS public URL of the image to be used in the video. If empty, the video will be generated purely based on the prompt.

    Returns:
        dict: A dictionary containing the status, detail, and video URL if successful.
    """

    # Use below static return to save the cost while testing
    # return {
    #     "status": "success",
    #     "detail": "Video generated and uploaded to GCS",
    #     "video_url": "https://storage.cloud.google.com/smba-assets/videos/8905612651172803034/sample_0.mp4",
    # }

    output_gcs_uri = f"gs://{GCS_BUCKET_NAME}/videos"

    # Polling config: exponential backoff, 10-minute hard timeout
    _MAX_WAIT_SECONDS = 600  # 10 minutes
    _BACKOFF_INITIAL = 2
    _BACKOFF_MAX = 30

    try:
        operation = client.models.generate_videos(
            # model="veo-3.0-generate-preview",  # hope we can use this asap
            model="veo-2.0-generate-001",
            prompt=video_prompt,
            image=Image(
                gcs_uri=public_url_to_gcs_uri(image_gcs_uri),
                mime_type="image/png",
            ) if image_gcs_uri else None,
            config=GenerateVideosConfig(
                aspect_ratio="16:9",
                output_gcs_uri=output_gcs_uri,
            ),
        )

        # Poll with exponential backoff + timeout
        logger.info("Video generation started. Polling for completion...")
        total_waited = 0
        backoff = _BACKOFF_INITIAL
        while not operation.done:
            if total_waited >= _MAX_WAIT_SECONDS:
                logger.error("Video generation timed out after %d seconds", total_waited)
                return {
                    "status": "failed",
                    "detail": f"Video generation timed out after {total_waited} seconds",
                }
            sleep_time = min(backoff, _BACKOFF_MAX)
            time.sleep(sleep_time)
            total_waited += sleep_time
            backoff = min(backoff * 2, _BACKOFF_MAX)
            operation = client.operations.get(operation)
            logger.debug("Polling video operation: waited %ds so far", total_waited)

        if operation.response and operation.result:
            logger.debug("Video operation result: %s", operation.result)

            generated_videos = operation.result.generated_videos
            if not generated_videos or not generated_videos[0].video or not generated_videos[0].video.uri:
                return {
                    "status": "failed",
                    "detail": f"Generated video is empty: {operation}",
                }
            generated_video_uri: str = generated_videos[0].video.uri
            logger.info("Video generated successfully: %s", generated_video_uri)
            return {
                "status": "success",
                "detail": "Video generated and uploaded to GCS",
                "video_url": gcs_uri_to_public_url(generated_video_uri),
            }
        else:
            return {
                "status": "failed",
                "detail": f"Video generation failed: {operation}",
            }
    except Exception as e:
        logger.exception("Video generation failed")
        return {"status": "failed", "detail": f"Video generation failed: {e}"}


video_generation_agent = Agent(
    name="video_generation_agent",
    model="gemini-2.5-flash",
    description=prompt.DESCRIPTION,
    instruction=prompt.INSTRUCTIONS,
    output_key="video_generation_output",
    tools=[generate_video, generate_audio, assemble_video_with_audio],
)
