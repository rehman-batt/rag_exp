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
    cache = ResponseCache(ttl_seconds=settings.cache_ttl_seconds)
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
        security_notes.extend(notes)


        if not is_authorized:
            metrics.update_metrics(latency=timer.elapsed_time, error=True)
            logger.warning("Unauthorized access attempt", extra={"extra_data": {"security_notes": security_notes}, "tracing_enabled": get_settings().langchain_tracing_v2})
            raise HTTPException(status_code=400, detail="Unauthorized access")


        # Check if the response is cached
        cached_response = cache.get(chat_request)
        if cached_response:
            metrics.update_metrics(latency=timer.elapsed_time, cache_hit=True)
            logger.info("Cache hit for request", extra={"extra_data": {"request": chat_request.dict(), "response": cached_response.dict()}, "tracing_enabled": get_settings().langchain_tracing_v2})
            return ChatResponse(
                response=cached_response,
                thread_id=chat_request.thread_id,
                model_used="cache",
                cached=True,
                processing_time_ms=0,

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

        response_text = agent_response["response"]
        model_used = agent_response["model_used"]

        # Cache Store

        cache.set(cleaned_message, response_text)

        
        