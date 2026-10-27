"""Keep encoded voice intact while repairing browser containers for seekable playback."""
import shutil
import subprocess
import tempfile
from pathlib import Path


def seekable_audio(audio: bytes, media_type: str) -> bytes:
    executable = shutil.which('ffmpeg')
    if not executable or media_type == 'audio/wav':
        return audio
    formats = {'audio/webm': 'webm', 'audio/mp4': 'mp4', 'audio/ogg': 'ogg'}
    format_name = formats.get(media_type)
    if not format_name:
        raise ValueError('Unsupported recording container.')
    with tempfile.TemporaryDirectory(prefix='linterna-audio-') as directory:
        output = Path(directory) / f'recording.{format_name}'
        command = [executable, '-nostdin', '-hide_banner', '-loglevel', 'error',
                   '-protocol_whitelist', 'file,pipe', '-i', 'pipe:0', '-map', '0:a:0',
                   '-c:a', 'copy', '-f', format_name]
        if format_name == 'mp4':
            command.extend(['-movflags', '+faststart'])
        try:
            result = subprocess.run(command + [str(output)], input=audio, capture_output=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('The recording could not be finalized in time. Your draft remains available.') from exc
        if result.returncode or not output.is_file():
            raise ValueError('The browser recording is incomplete or damaged. Try recording again.')
        if output.stat().st_size > 25 * 1024 * 1024:
            raise ValueError('The finalized recording exceeds 25 MB. Record a shorter memory.')
        return output.read_bytes()
