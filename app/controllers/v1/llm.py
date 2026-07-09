from fastapi import Request

from app.controllers.v1.base import new_router
from app.models.schema import (
    VideoPolishScriptRequest,
    VideoScriptRequest,
    VideoScriptResponse,
    VideoSocialMetadataRequest,
    VideoSocialMetadataResponse,
    VideoTermsRequest,
    VideoTermsResponse,
)
from app.services import llm
from app.utils import utils
from app.utils.target_duration import (
    duration_seconds_from_target_duration,
    paragraph_number_from_target_duration,
)

# authentication dependency
# router = new_router(dependencies=[Depends(base.verify_token)])
router = new_router()


@router.post(
    "/scripts",
    response_model=VideoScriptResponse,
    summary="Create a script for the video",
)
def generate_video_script(request: Request, body: VideoScriptRequest):
    paragraph_number = body.paragraph_number
    if body.target_duration:
        paragraph_number = paragraph_number_from_target_duration(body.target_duration)

    video_script = llm.generate_script(
        video_subject=body.video_subject,
        language=body.video_language,
        paragraph_number=paragraph_number,
        video_script_prompt=body.video_script_prompt,
        custom_system_prompt=body.custom_system_prompt,
        target_duration=body.target_duration or "",
    )
    response = {"video_script": video_script}
    return utils.get_response(200, response)


@router.post(
    "/scripts/polish",
    response_model=VideoScriptResponse,
    summary="Polish a rough script brief into a full voiceover",
)
def polish_video_script(request: Request, body: VideoPolishScriptRequest):
    if body.target_duration:
        duration_seconds = duration_seconds_from_target_duration(body.target_duration)
    else:
        duration_seconds = max(30, int(body.paragraph_number or 1) * 25)
    try:
        video_script = llm.polish_script(
            brief=body.brief,
            video_subject=body.video_subject,
            duration_seconds=duration_seconds,
            language=body.video_language,
        )
    except ValueError as exc:
        return utils.get_response(400, {"video_script": f"Error: {exc}"})
    response = {"video_script": video_script}
    return utils.get_response(200, response)


@router.post(
    "/terms",
    response_model=VideoTermsResponse,
    summary="Generate video terms based on the video script",
)
def generate_video_terms(request: Request, body: VideoTermsRequest):
    paragraph_number = body.paragraph_number
    if body.target_duration:
        paragraph_number = paragraph_number_from_target_duration(body.target_duration)

    amount = body.amount
    if amount is None:
        amount = llm.default_terms_amount(
            body.match_materials_to_script,
            paragraph_number,
        )

    video_terms = llm.generate_terms(
        video_subject=body.video_subject,
        video_script=body.video_script,
        amount=amount,
        match_script_order=body.match_materials_to_script,
        paragraph_number=paragraph_number,
    )
    if isinstance(video_terms, str):
        response = {"video_terms": video_terms}
    else:
        response = {
            "video_terms": [keyword.model_dump() for keyword in video_terms.keywords],
            "has_explicit_weights": video_terms.has_explicit_weights,
        }
    return utils.get_response(200, response)


@router.post(
    "/social-metadata",
    response_model=VideoSocialMetadataResponse,
    summary="Generate social publishing metadata",
)
def generate_video_social_metadata(
    request: Request, body: VideoSocialMetadataRequest
):
    metadata = llm.generate_social_metadata(
        video_subject=body.video_subject,
        video_script=body.video_script,
        language=body.language,
        platform=body.platform,
    )
    return utils.get_response(200, metadata)
