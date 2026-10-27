from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server.audio_routes import router as audio_router
from server import db
from server import tts as tts_service
from server.config import DATA_DIR, DB_PATH, load_config, save_config


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Linterna", version="0.1.0")
app.include_router(audio_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class MemoryCreate(BaseModel):
    transcript: str = Field(min_length=1, max_length=60000)
    title: str = Field(default="", max_length=200)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1)


class ConfigUpdate(BaseModel):
    chat_base_url: str | None = None
    chat_model: str | None = None
    tts_base_url: str | None = None
    tts_model: str | None = None
    tts_voice: str | None = None
    asr_base_url: str | None = None
    asr_model: str | None = None


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    load_config()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "linterna",
        "db": str(DB_PATH),
        "data_dir": str(DATA_DIR),
        "memory_count": len(db.list_memories()),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def get_config() -> dict:
    return load_config()


@app.put("/api/config")
def put_config(body: ConfigUpdate) -> dict:
    return save_config(body.model_dump(exclude_none=True))


@app.post("/api/tts")
def speak(body: SpeakRequest) -> Response:
    try:
        audio, media_type = tts_service.synthesize(body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio, media_type=media_type)


@app.get("/api/memories")
def get_memories(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    day: int | None = Query(default=None, ge=1, le=31),
) -> list[dict]:
    return db.list_memories(year=year, month=month, day=day)


@app.get("/api/memories/timeline")
def get_timeline(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    day: int | None = Query(default=None, ge=1, le=31),
) -> dict:
    return {
        "years": db.timeline(year=year, month=month, day=day),
    }


@app.get("/api/memories/search")
def search_memories(
    q: str = Query(min_length=1),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    day: int | None = Query(default=None, ge=1, le=31),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    results = db.search_memories(
        q,
        year=year,
        month=month,
        day=day,
        limit=limit,
    )
    return {"query": q, "results": results}


@app.get("/api/memories/{memory_id}")
def get_one_memory(memory_id: int) -> dict:
    memory = db.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return memory


@app.post("/api/memories", status_code=201)
def post_memory(body: MemoryCreate) -> dict:
    try:
        return db.create_memory(body.transcript, body.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/memories/{memory_id}", status_code=204)
def remove_memory(memory_id: int) -> None:
    if not db.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="memory not found")
