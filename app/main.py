import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langsmith import traceable
from dotenv import load_dotenv

from app.config import get_settings
from app.models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
)

from app.security import SecurityManager
from app.cache import ResponseCache
from app.monitoring import MetricsCollector, RequestTimer, get_logger
from app.agent import ProductionAgent

logger = get_logger()

load_dotenv()  


def _response_text(content: str | list[dict]) -> str:
    """Extract text from the string or text-block content returned by the model."""
    if isinstance(content, str):
        return content
    return "".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Initializes the agent, security manager, and response cache.
    """

    global security, cache, metrics, agent

    settings = get_settings()

    logger.info(f"Starting application in {settings.api_env}", extra={"extra_data": {"env": settings.api_env, "log_level": settings.log_level, "primary_model": settings.primary_model, "fallback_model": settings.fallback_model}, "tracing_enabled": settings.langchain_tracing_v2})

    security = SecurityManager()
    cache = ResponseCache(ttl=settings.cache_ttl_seconds)
    metrics = MetricsCollector()
    agent = ProductionAgent()

    logger.info("All components initialized successfully.")

    yield

    logger.info("Shutting down application. Cleaning up resources.", extra={"extra_data": metrics.log_metrics()})




limiter = Limiter(key_func=get_remote_address, default_limits=[f"{get_settings().rate_limit}/minute"])

app = FastAPI(title="Production RAG API", version="1.0.0", lifespan=lifespan)


app.state.limiter = limiter

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(f"{get_settings().rate_limit}/minute")
@traceable(name="chat_endpoint", project=get_settings().langchain_project)
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    """
    Endpoint to handle chat requests.
    Processes the request, checks cache, invokes the agent, and returns the response.

    Flow:
    1. Security Check
    2. Cache Check
    3. Agent Invocation
    4. Cache Storage
    5. Return Response
    """

    with RequestTimer() as timer:
        security_notes = []

        is_authorized, cleaned_message, notes = security.process_input(chat_request.message)
        if notes:
            security_notes.append(notes)


        if not is_authorized:
            metrics.update_metrics(latency=timer.elapsed_time, error=True)
            logger.warning("Unauthorized access attempt", extra={"extra_data": {"security_notes": security_notes}, "tracing_enabled": get_settings().langchain_tracing_v2})
            raise HTTPException(status_code=400, detail="Unauthorized access")


        # Check if the response is cached
        cached_response = cache.get(cleaned_message)
        if cached_response:
            elapsed_time = timer.elapsed_time
            cached_response = _response_text(cached_response)
            metrics.update_metrics(latency=elapsed_time, cache_hit=True)
            logger.info("Cache hit for request", extra={"extra_data": {"request": chat_request.model_dump(), "response": cached_response}, "tracing_enabled": get_settings().langchain_tracing_v2})
            return ChatResponse(
                response=cached_response,
                thread_id=chat_request.thread_id,
                model_used="cache",
                cached=True,
                processing_time_ms=elapsed_time * 1000,

            )

        # Invoke the agent
        try:
            agent_response = agent.invoke(cleaned_message)
        except Exception as e:
            logger.error("Error invoking agent", extra={"extra_data": {"error": str(e), "thread_id": chat_request.thread_id}})
            metrics.update_metrics(latency=0, error=True)

            raise HTTPException (
                status_code=500,
                detail="An error occured while processing your request."
            )

        response_text = _response_text(agent_response["response"])
        model_used = agent_response["model_used"]

        # Cache Store

        cache.set(cleaned_message, response_text)

    input_tokens = int(len(cleaned_message.split()) * 1.3)
    output_tokens = int(len(response_text.split()) * 1.3)

    metrics.update_metrics(timer.elapsed_time, False, input_tokens, output_tokens)

    if security_notes:
        logger.info("Security Notes", extra={"extra_data": {
            "notes": security_notes,
            "thread_id": chat_request.thread_id
        }})

    return ChatResponse(
        response=response_text,
        thread_id=chat_request.thread_id,
        model_used=model_used,
        cached=False,
        processing_time_ms=timer.elapsed_time * 1000,
    )

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health Check Endpoint"""

    settings = get_settings()

    checks = {
        "agent": agent is not None,
        "security": security is not None,
        "cache": cache is not None
    }

    healthy = all(checks.values())

    return HealthResponse(
        status="healthy" if healthy else "degraded",
        environment=settings.api_env,
        checks=checks
    )

@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Metrics for monitoring dashboards."""
    summary = metrics.log_metrics()
   

    return MetricsResponse(**summary)

@app.get("/cache_stats")
async def cache_stats():
    """Cache performance"""
    return cache.stats()
