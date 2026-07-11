import time
import uuid
from datetime import datetime, timezone
import asyncio
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import HTTPException
from openai import AsyncOpenAI
from google import genai
from google.genai import types as genai_types
from app.core.config import settings
from app.schemas.llm import ChatCompletionRequest, ChatResponse, MessageParam

# Initialize OpenAI Async client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Initialize Gemini (google-genai) client
gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

SUPPORTED_MODELS = {
    "openai": ["gpt-4o", "gpt-3.5-turbo"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash"]
}

class LLMService:
    @staticmethod
    def validate_request(request: ChatCompletionRequest):
        provider = request.provider.lower()
        model = request.model.lower()

        if provider not in SUPPORTED_MODELS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider '{provider}'. Supported providers: {list(SUPPORTED_MODELS.keys())}"
            )
        
        if model not in SUPPORTED_MODELS[provider]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model '{model}' for provider '{provider}'. Supported models: {SUPPORTED_MODELS[provider]}"
            )

    @staticmethod
    async def call_openai(request: ChatCompletionRequest) -> Dict:
        """Calls OpenAI Chat Completions API or returns mock if using mock key."""
        if settings.OPENAI_API_KEY.startswith("mock"):
            # Mock Response
            await asyncio.sleep(0.3) # simulate latency
            content = f"Mock response from OpenAI ({request.model}): Hello! This is a test completion."
            prompt_tokens = sum(len(m.content) // 4 for m in request.messages) + 10
            completion_tokens = len(content) // 4
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        
        # Actual API Call
        messages_list = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            response = await openai_client.chat.completions.create(
                model=request.model,
                messages=messages_list,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            return {
                "id": response.id,
                "content": response.choices[0].message.content,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")

    @staticmethod
    def _build_gemini_contents(request: ChatCompletionRequest):
        """Convert chat messages into google-genai Content objects, extracting any system instruction."""
        system_instruction = None
        contents = []
        for m in request.messages:
            if m.role == "system":
                system_instruction = m.content
            elif m.role == "assistant":
                contents.append(genai_types.Content(role="model", parts=[genai_types.Part(text=m.content)]))
            else:
                contents.append(genai_types.Content(role="user", parts=[genai_types.Part(text=m.content)]))
        return system_instruction, contents

    @staticmethod
    async def call_gemini(request: ChatCompletionRequest) -> Dict:
        """Calls Google Gemini API (via google-genai) or returns mock if using mock key."""
        if settings.GEMINI_API_KEY.startswith("mock"):
            # Mock Response
            await asyncio.sleep(0.3) # simulate latency
            content = f"Mock response from Gemini ({request.model}): Hello there! This is a test completion."
            prompt_tokens = sum(len(m.content) // 4 for m in request.messages) + 12
            completion_tokens = len(content) // 4
            return {
                "id": f"geminichat-{uuid.uuid4().hex[:12]}",
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }

        # Actual API Call
        system_instruction, contents = LLMService._build_gemini_contents(request)

        try:
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=request.temperature,
                max_output_tokens=request.max_tokens,
            )
            response = await gemini_client.aio.models.generate_content(
                model=request.model,
                contents=contents,
                config=config,
            )

            usage = response.usage_metadata
            prompt_tokens = (usage.prompt_token_count if usage else None) or 0
            completion_tokens = (usage.candidates_token_count if usage else None) or 0
            total_tokens = (usage.total_token_count if usage else None) or (prompt_tokens + completion_tokens)

            return {
                "id": f"gemini-{uuid.uuid4().hex[:12]}",
                "content": response.text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    @staticmethod
    async def call_openai_stream(request: ChatCompletionRequest) -> AsyncGenerator[Dict, None]:
        """Streams responses from OpenAI."""
        if settings.OPENAI_API_KEY.startswith("mock"):
            words = f"Mock streaming response from OpenAI ({request.model}): Hello! This is a token-by-token stream.".split(" ")
            for i, word in enumerate(words):
                await asyncio.sleep(0.08) # simulate token generation delay
                yield {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                    "delta": " " + word if i > 0 else word,
                    "finish_reason": None if i < len(words) - 1 else "stop"
                }
            return

        messages_list = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            stream = await openai_client.chat.completions.create(
                model=request.model,
                messages=messages_list,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content or ""
                    finish_reason = chunk.choices[0].finish_reason
                    yield {
                        "id": chunk.id,
                        "delta": delta,
                        "finish_reason": finish_reason
                    }
        except Exception as e:
            yield {"error": f"OpenAI Stream API error: {str(e)}"}

    @staticmethod
    async def call_gemini_stream(request: ChatCompletionRequest) -> AsyncGenerator[Dict, None]:
        """Streams responses from Gemini (via google-genai)."""
        if settings.GEMINI_API_KEY.startswith("mock"):
            words = f"Mock streaming response from Gemini ({request.model}): Hello! This is a token-by-token stream.".split(" ")
            for i, word in enumerate(words):
                await asyncio.sleep(0.08)
                yield {
                    "id": f"geminichat-{uuid.uuid4().hex[:12]}",
                    "delta": " " + word if i > 0 else word,
                    "finish_reason": None if i < len(words) - 1 else "stop"
                }
            return

        system_instruction, contents = LLMService._build_gemini_contents(request)

        try:
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=request.temperature,
                max_output_tokens=request.max_tokens,
            )
            stream = await gemini_client.aio.models.generate_content_stream(
                model=request.model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                finish_reason = None
                if chunk.candidates:
                    reason = chunk.candidates[0].finish_reason
                    finish_reason = reason.name if reason else None
                yield {
                    "id": f"gemini-{uuid.uuid4().hex[:12]}",
                    "delta": chunk.text or "",
                    "finish_reason": finish_reason
                }
        except Exception as e:
            yield {"error": f"Gemini Stream API error: {str(e)}"}

    @staticmethod
    async def log_usage_to_db(
        user_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        status_code: int,
        error_message: Optional[str] = None
    ) -> None:
        """Asynchronously writes usage metric logs to the usage_logs MongoDB collection."""
        from app.core.database import get_database
        db = get_database()
        if db is None:
            print("Logging error: database client not initialized")
            return
        try:
            log_entry = {
                "user_id": user_id,
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": latency_ms,
                "status_code": status_code,
                "error_message": error_message,
                "created_at": datetime.now(timezone.utc)
            }
            await db["usage_logs"].insert_one(log_entry)
        except Exception as e:
            # Prevent failures in logging from blocking the user response
            print(f"Logging error to MongoDB failed: {e}")
