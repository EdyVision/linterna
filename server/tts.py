from __future__ import annotations

import httpx
from server.config import load_config, speech_headers
from server.asr import transcription_url


def synthesize(text: str) -> tuple[bytes, str]:
    cfg = load_config()
    base = (cfg.get('tts_base_url') or '').strip()
    if not base:
        raise RuntimeError('Set a narration endpoint in Config, or use browser voice.')
    cleaned = ' '.join((text or '').split()).strip()
    if not cleaned:
        raise ValueError('Text is required.')
    if len(cleaned) > 60000:
        raise ValueError('The transcript is too long for a single narration request.')
    url = transcription_url(base).removesuffix('/audio/transcriptions') + '/audio/speech'
    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=5.0), follow_redirects=False) as client:
            with client.stream('POST', url, headers=speech_headers(url), json={
                'model': (cfg.get('tts_model') or 'magpie-tts').strip(),
                'voice': (cfg.get('tts_voice') or 'Sofia').strip(),
                'input': cleaned, 'response_format': 'wav',
            }) as response:
                if response.status_code != 200:
                    raise RuntimeError(f'Speech service returned {response.status_code}.')
                media_type = response.headers.get('content-type', '').split(';')[0]
                if media_type not in ('audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/mp4', 'audio/ogg'):
                    raise RuntimeError('Speech service did not return playable audio.')
                audio = bytearray()
                for chunk in response.iter_bytes():
                    audio.extend(chunk)
                    if len(audio) > 25 * 1024 * 1024:
                        raise RuntimeError('Narration exceeds the supported size.')
                if not audio:
                    raise RuntimeError('Speech service returned empty audio.')
                return bytes(audio), media_type
    except httpx.HTTPError as exc:
        raise RuntimeError('Speech service is unavailable. Your original recording is unaffected.') from exc
