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
