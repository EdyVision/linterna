from __future__ import annotations

import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LINTERNA_DATA", str(REPO_ROOT / "data"))).expanduser()
DB_PATH = DATA_DIR / "linterna.db"
CONFIG_PATH = DATA_DIR / "config.json"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))

DEFAULT_CONFIG = {
    "chat_base_url": "",
    "chat_model": "",
    "tts_base_url": "",
    "tts_model": "magpie-tts",
    "tts_voice": "Sofia",
    "asr_base_url": "",
    "asr_model": "whisper-1",
}


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def load_config() -> dict:
    ensure_data_dir()
    if not CONFIG_PATH.is_file():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
        return dict(DEFAULT_CONFIG)
    data = json.loads(CONFIG_PATH.read_text())
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    return merged


def save_config(updates: dict) -> dict:
    current = load_config()
    for key, value in updates.items():
        if key in DEFAULT_CONFIG:
            current[key] = value if value is not None else ""
    CONFIG_PATH.write_text(json.dumps(current, indent=2) + "\n")
    return current


def speech_headers(url: str) -> dict[str, str]:
    from urllib.parse import urlsplit
    private = {}
    private_file = REPO_ROOT / ".env.local"
    if private_file.is_file():
        for line in private_file.read_text().splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in ("LINTERNA_SPEECH_API_KEY", "LINTERNA_SPEECH_ORIGIN"):
                private[name.strip()] = value.strip()
    key = os.environ.get("LINTERNA_SPEECH_API_KEY", private.get("LINTERNA_SPEECH_API_KEY", ""))
    origin = os.environ.get("LINTERNA_SPEECH_ORIGIN", private.get("LINTERNA_SPEECH_ORIGIN", ""))
    expected, requested = urlsplit(origin), urlsplit(url)
    if key and origin and (expected.scheme, expected.netloc) == (requested.scheme, requested.netloc):
        return {"Authorization": f"Bearer {key}"}
    return {}
