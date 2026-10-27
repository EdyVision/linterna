from __future__ import annotations

import httpx
from urllib.parse import urlsplit

from server.config import load_config, speech_headers


def transcription_url(base: str) -> str:
    base = base.strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTP(S) transcription URL without embedded credentials or a query.")
    if base.endswith("/audio/transcriptions"):
        return base
    return base + ("/audio/transcriptions" if base.endswith("/v1") else "/v1/audio/transcriptions")


def transcribe(audio: bytes, media_type: str, filename: str) -> str:
    config = load_config()
    if not config.get("asr_base_url", "").strip():
        raise ValueError("Set a transcription endpoint in Config. Your recording can still be saved without text.")
    url = transcription_url(config["asr_base_url"])
    try:
        with httpx.Client(timeout=httpx.Timeout(90.0, connect=5.0), follow_redirects=False) as client:
            with client.stream("POST", url, headers=speech_headers(url), files={"file": (filename, audio, media_type)},
                               data={"model": config.get("asr_model") or "whisper-1", "response_format": "json"}) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Transcription service returned {response.status_code}.")
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 262144:
                        raise RuntimeError("Transcription response exceeds the supported size.")
                import json
                result = json.loads(chunks)
    except httpx.HTTPError as exc:
        raise RuntimeError("Transcription service is unavailable. Check its URL and network connection.") from exc
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Transcription service returned an invalid response.") from exc
    text = result.get("text") if isinstance(result, dict) else None
    if not isinstance(text, str) or len(text) > 60000:
        raise RuntimeError("Transcription service returned no usable transcript.")
    return text.strip()
