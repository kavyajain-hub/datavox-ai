import os
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config.settings import get_settings
from config.llm import user_api_key_ctx, user_provider_ctx, user_model_ctx
from main import handle_query_detailed
from services.data_service import (
    parse_csv_or_json,
    ingest_dataset,
    ingest_multiple_datasets,
    get_all_tables,
    get_table_data,
    get_all_relationships,
    purge_sample_tables
)
from db.init_db import create_and_seed_database

# Structured JSON logging
logging.basicConfig(
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","message":"%(message)s"}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Datavox", version="1.1.0")

# --- Rate Limiting ---
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    limiter = None
    logger.warning("slowapi not installed — rate limiting disabled. Run: pip install slowapi")

# --- CORS (restricted in production) ---
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Middleware: reset context vars after each request ---
@app.middleware("http")
async def reset_llm_credentials(request: Request, call_next):
    """Ensure user API key context vars are reset between requests to prevent cross-user leakage."""
    token_key = user_api_key_ctx.set(None)
    token_prov = user_provider_ctx.set(None)
    token_mod = user_model_ctx.set(None)
    try:
        response = await call_next(request)
        return response
    finally:
        user_api_key_ctx.reset(token_key)
        user_provider_ctx.reset(token_prov)
        user_model_ctx.reset(token_mod)


# --- Upload size limit ---
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


# --- Health check ---
@app.get("/health")
def health_check():
    """Lightweight health check for Render / load balancer monitoring."""
    return {"status": "ok"}


@app.get("/api/status")
def get_system_status():
    """Return runtime configuration and active provider status."""
    settings = get_settings()
    has_key = bool(settings.active_api_key and "your-" not in settings.active_api_key)
    is_sqlite = settings.database_url.startswith("sqlite")

    return {
        "status": "online",
        "provider": settings.llm_provider,
        "model": settings.active_model,
        "database": "SQLite (Local)" if is_sqlite else "PostgreSQL",
        "database_url": settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url,
        "has_server_key": has_key,
        "checkpointer": "MemorySaver (Local)" if not settings.checkpoint_db_url.startswith("postgresql://") or "postgres:postgres@localhost" in settings.checkpoint_db_url else "PostgresSaver"
    }


@app.post("/api/chat")
def chat_endpoint(
    req: ChatRequest,
    request: Request,
    x_datavox_api_key: Optional[str] = Header(None),
    x_datavox_provider: Optional[str] = Header(None),
    x_datavox_model: Optional[str] = Header(None)
):
    """Process natural language query via LangGraph pipeline and return detailed response."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Rate limit check (if slowapi is installed)
    if limiter:
        limiter._check_request_limit(request, chat_endpoint, [("10/minute",)])

    try:
        result = handle_query_detailed(
            req.query.strip(),
            session_id=req.session_id,
            api_key=x_datavox_api_key,
            provider=x_datavox_provider,
            model=x_datavox_model
        )
        return result
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tables")
def list_tables():
    """List all user and system tables with schema and counts."""
    try:
        tables = get_all_tables()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to inspect tables: {e}")


@app.get("/api/tables/{table_name}")
def view_table_data(table_name: str, limit: int = 50, offset: int = 0):
    """Fetch paginated data for a given table."""
    try:
        data = get_table_data(table_name, limit=limit, offset=offset)
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not load table '{table_name}': {e}")


@app.get("/api/relationships")
def list_relationships():
    """Return all detected foreign key relationships across tables."""
    try:
        rels = get_all_relationships()
        return {"relationships": rels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-data")
async def upload_dataset(
    file: UploadFile = File(...),
    table_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    clear_sample_data: bool = Form(False)
):
    """Upload CSV or JSON file, create database table, and index into schema.json."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum {MAX_UPLOAD_SIZE // (1024*1024)}MB allowed.")

        default_table, rows = parse_csv_or_json(content, file.filename)
        target_table = table_name.strip() if table_name and table_name.strip() else default_table

        ingest_result = ingest_dataset(
            target_table,
            rows,
            description=description,
            clear_sample_data=clear_sample_data
        )
        return {
            "success": True,
            "message": f"Successfully ingested {ingest_result['rows_inserted']} rows into table '{ingest_result['table_name']}'.",
            "details": ingest_result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to ingest file: {e}")


@app.post("/api/upload-multiple-data")
async def upload_multiple_datasets_endpoint(
    files: list[UploadFile] = File(...),
    clear_sample_data: bool = Form(False)
):
    """Upload multiple CSV or JSON files in batch, detect relationships between them, and index schemas."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    dataset_items = []
    errors = []

    for f in files:
        if not f.filename:
            continue
        try:
            content = await f.read()
            if len(content) > MAX_UPLOAD_SIZE:
                errors.append(f"File '{f.filename}' exceeds {MAX_UPLOAD_SIZE // (1024*1024)}MB limit.")
                continue
            tname, rows = parse_csv_or_json(content, f.filename)
            dataset_items.append({
                "table_name": tname,
                "rows": rows,
                "description": f"Uploaded dataset '{tname}' from file {f.filename}."
            })
        except Exception as e:
            errors.append(f"Error parsing '{f.filename}': {e}")

    if not dataset_items:
        raise HTTPException(status_code=400, detail="None of the uploaded files could be parsed: " + "; ".join(errors))

    try:
        result = ingest_multiple_datasets(dataset_items, clear_sample_data=clear_sample_data)
        return {
            "success": True,
            "message": f"Successfully ingested {len(result['tables_ingested'])} tables with {len(result['detected_relationships'])} detected relationships.",
            "details": result,
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest batch datasets: {e}")


@app.post("/api/clear-sample-data")
def clear_sample_data_endpoint():
    """Purge all testing/sample tables from database and schema registry."""
    try:
        dropped = purge_sample_tables(keep_custom=True)
        return {
            "success": True,
            "message": f"Successfully purged {len(dropped)} sample/testing tables.",
            "dropped_tables": dropped
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reset-sample-data")
def reset_sample_data():
    """Reset and re-seed the sample tables."""
    try:
        create_and_seed_database()
        return {"success": True, "message": "Sample database verified and seeded."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

# Mount static assets
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Datavox API is running. UI files under /static."}

