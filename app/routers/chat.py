import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.database import get_database
from app.routers.auth import get_current_user
from app.schemas.llm import (
    ChatCompletionRequest,
    ChatResponse,
    ModelDetail,
    ModelListResponse,
)
from app.services.llm_service import LLMService
from app.core.config import settings
from app.core.rate_limiter import limiter, is_admin_request

router = APIRouter(prefix="/chat", tags=["chat"])


async def generate_sse_stream(request: ChatCompletionRequest, user_id: str):
    """Generates Server-Sent Events (SSE) compatible payload chunks."""
    start_time = time.time()
    full_content = []
    
    if request.provider == "openai":
        generator = LLMService.call_openai_stream(request)
    else:
        generator = LLMService.call_gemini_stream(request)

    status_code = 200
    error_message = None

    try:
        async for chunk in generator:
            if "error" in chunk:
                error_message = chunk["error"]
                status_code = 502
                yield f"data: {json.dumps({'error': error_message})}\n\n"
                break

            delta = chunk.get("delta", "")
            full_content.append(delta)
            yield f"data: {json.dumps({'delta': delta})}\n\n"

    except Exception as e:
        status_code = 500
        error_message = str(e)
        yield f"data: {json.dumps({'error': error_message})}\n\n"
        
    finally:
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        full_text = "".join(full_content)
        
        # Approximate tokens
        prompt_tokens = sum(len(m.content) // 4 for m in request.messages) + 10
        completion_tokens = len(full_text) // 4

        # Asynchronously log usage metrics to PostgreSQL
        asyncio.create_task(
            LLMService.log_usage_to_db(
                user_id=user_id,
                provider=request.provider,
                model=request.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status_code=status_code,
                error_message=error_message
            )
        )


@router.post("/completions", response_model=None, summary="Call chat completions endpoint")
@limiter.limit(settings.RATE_LIMIT_CHAT, exempt_when=is_admin_request)
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    stream: bool = Query(default=False),
    current_user = Depends(get_current_user),
):
    """
    Unified chat completions endpoint supporting standard response and SSE streaming.
    Routes calls to OpenAI or Google Gemini.
    """
    LLMService.validate_request(body)

    is_streaming = stream or body.stream

    if is_streaming:
        return StreamingResponse(
            generate_sse_stream(body, str(current_user["_id"])),
            media_type="text/event-stream"
        )

    # Standard non-streaming completion
    start_time = time.time()
    status_code = 200
    error_message = None
    prompt_tokens = 0
    completion_tokens = 0
    result = {}

    try:
        if body.provider == "openai":
            result = await LLMService.call_openai(body)
        else:
            result = await LLMService.call_gemini(body)

        prompt_tokens = result["prompt_tokens"]
        completion_tokens = result["completion_tokens"]
        
        return ChatResponse(
            id=result["id"],
            provider=body.provider,
            model=body.model,
            content=result["content"],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=result["total_tokens"],
            created_at=datetime.now(timezone.utc)
        )

    except HTTPException as he:
        status_code = he.status_code
        error_message = str(he.detail)
        raise he
    except Exception as e:
        status_code = 500
        error_message = str(e)
        raise HTTPException(status_code=500, detail=error_message)
        
    finally:
        # Log to DB in standard non-streaming flow
        latency_ms = int((time.time() - start_time) * 1000)
        asyncio.create_task(
            LLMService.log_usage_to_db(
                user_id=str(current_user["_id"]),
                provider=body.provider,
                model=body.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status_code=status_code,
                error_message=error_message
            )
        )


@router.get("/models", response_model=ModelListResponse, summary="List supported provider/model combinations")
async def get_models(current_user = Depends(get_current_user)):
    """Returns a list of supported models grouped by provider."""
    models = [
        ModelDetail(name="gpt-4o", provider="openai"),
        ModelDetail(name="gpt-3.5-turbo", provider="openai"),
        ModelDetail(name="gemini-2.5-pro", provider="gemini"),
        ModelDetail(name="gemini-2.5-flash", provider="gemini"),
    ]
    return ModelListResponse(models=models)
