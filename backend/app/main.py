import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.api.routes import router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import DomainError

app = FastAPI(title='Workleave API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins, allow_credentials=False, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])
app.include_router(router)
logger = logging.getLogger('workleave')
logging.basicConfig(level=logging.INFO, format='%(message)s')
windows = defaultdict(deque)
window_lock = Lock()


@app.middleware('http')
async def security(request: Request, call_next):
    request_id = str(uuid4())
    started = time.monotonic()
    key = request.client.host if request.client else 'unknown'
    authorization = request.headers.get('authorization', '')
    if authorization:
        key += ':' + hashlib.sha256(authorization.encode()).hexdigest()[:32]
    limited = False
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        with window_lock:
            # Bounded single-process limiter. Deploy one API worker or limit at the ingress too.
            if len(windows) > 10000:
                for stale in [k for k, q in windows.items() if not q or q[-1] < started-60]:
                    windows.pop(stale, None)
            queue = windows[key]
            while queue and queue[0] < started-60:
                queue.popleft()
            limited = len(queue) >= settings().rate_limit_per_minute
            if not limited:
                queue.append(started)
    response = JSONResponse({'error': {'code': 'rate_limited', 'message': 'Too many requests. Try again shortly.'}}, status_code=429, headers={'Retry-After': '60'}) if limited else await call_next(request)
    response.headers.update({'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store', 'X-Request-ID': request_id, 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'})
    if settings().environment == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    logger.info(json.dumps({'event': 'http', 'request_id': request_id, 'method': request.method, 'status': response.status_code, 'duration_ms': round((time.monotonic()-started)*1000)}))
    return response


@app.exception_handler(DomainError)
async def domain_error(_, exc):
    return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_error(_, exc):
    # Never echo submitted comments, token contents, or other input values.
    details = [{'loc': e['loc'], 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]
    return JSONResponse(jsonable_encoder({'error': {'code': 'validation_error', 'message': 'Please check the submitted fields', 'details': details}}), status_code=422)


@app.exception_handler(IntegrityError)
async def integrity_error(_, exc):
    return JSONResponse({'error': {'code': 'conflict', 'message': 'The change conflicts with an existing record or reference'}}, status_code=409)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/ready')
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT version_num FROM alembic_version'))
        return {'status': 'ready'}
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)


@app.exception_handler(HTTPException)
async def http_error(_, exc):
    return JSONResponse({"error": {"code": "http_error", "message": str(exc.detail)}}, status_code=exc.status_code, headers=exc.headers)
