from __future__ import annotations

import re
from typing import Annotated
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from server import asr, db
from server.audio_container import seekable_audio

router = APIRouter()
MAX_AUDIO = 25 * 1024 * 1024


def audio_kind(data: bytes) -> tuple[str, str]:
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav", "recording.wav"
    if data[:4] == bytes.fromhex("1a45dfa3"):
        return "audio/webm", "recording.webm"
    if data[4:8] == b"ftyp":
        return "audio/mp4", "recording.m4a"
    if data[:4] == b"OggS":
        return "audio/ogg", "recording.ogg"
    raise HTTPException(415, "Use a WAV, WebM, MP4 or Ogg audio recording.")


async def read_audio(file: UploadFile) -> tuple[bytes, str, str]:
    try:
        data = await file.read(MAX_AUDIO + 1)
    finally:
        await file.close()
    if not data:
        raise HTTPException(400, "The recording is empty.")
    if len(data) > MAX_AUDIO:
        raise HTTPException(413, "Recording exceeds 25 MB. Record a shorter memory.")
    media_type, filename = audio_kind(data)
    return data, media_type, filename


@router.post("/api/transcribe")
async def transcribe(file: Annotated[UploadFile, File()]) -> dict:
    import starlette.concurrency
    audio, media_type, filename = await read_audio(file)
    try:
        text = await starlette.concurrency.run_in_threadpool(asr.transcribe, audio, media_type, filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"text": text}


@router.post("/api/memories/recording", status_code=201)
async def save_recording(file: Annotated[UploadFile, File()],
                         transcript: Annotated[str, Form(max_length=60000)] = "",
                         title: Annotated[str, Form(max_length=200)] = "",
                         duration_seconds: Annotated[float | None, Form(ge=0, le=301)] = None) -> dict:
    from starlette.concurrency import run_in_threadpool
    audio, media_type, _ = await read_audio(file)
    try:
        audio = await run_in_threadpool(seekable_audio, audio, media_type)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return await run_in_threadpool(db.create_memory, transcript, title, audio=audio,
                                   audio_type=media_type, duration_seconds=duration_seconds)


@router.get("/api/memories/{memory_id}/audio")
def recording(memory_id: int, range_header: Annotated[str | None, Header(alias="Range")] = None) -> Response:
    recording = db.get_audio(memory_id)
    if recording is None:
        raise HTTPException(404, "No original recording for this memory.")
    audio, media_type = recording
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if not range_header:
        return Response(audio, media_type=media_type, headers=headers)
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
    if not match or not any(match.groups()):
        return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{len(audio)}"})
    left, right = match.groups()
    start = int(left) if left else max(0, len(audio) - int(right))
    end = min(int(right), len(audio) - 1) if left and right else len(audio) - 1
    if start > end or start >= len(audio):
        return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{len(audio)}"})
    headers["Content-Range"] = f"bytes {start}-{end}/{len(audio)}"
    return Response(audio[start:end + 1], status_code=206, media_type=media_type, headers=headers)
