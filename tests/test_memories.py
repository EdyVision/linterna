import io
import sqlite3
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import config, db
from server.main import app


def recording():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 1600)
    return output.getvalue()


class MemoriesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        path = Path(self.folder.name)
        self.patches = [patch.object(config, 'DATA_DIR', path), patch.object(config, 'CONFIG_PATH', path / 'config.json'), patch.object(db, 'DB_PATH', path / 'memory.db')]
        for item in self.patches: item.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        for item in reversed(self.patches): item.stop()
        self.folder.cleanup()

    def save(self, transcript='A lantern by the window'):
        response = self.client.post('/api/memories/recording', files={'file': ('memory.wav', recording(), 'audio/wav')}, data={'transcript': transcript, 'duration_seconds': '.1'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_original_voice_transcript_search_and_audio_ranges(self):
        memory = self.save()
        self.assertTrue(memory['has_audio'])
        self.assertNotIn('audio', memory)
        endpoint = f'/api/memories/{memory["id"]}/audio'
        self.assertEqual(self.client.get(endpoint).content, recording())
        chunk = self.client.get(endpoint, headers={'Range': 'bytes=0-11'})
        self.assertEqual(chunk.status_code, 206)
        self.assertEqual(chunk.content, recording()[:12])
        self.assertEqual(self.client.get(endpoint, headers={'Range': 'bytes=-10'}).content, recording()[-10:])
        self.assertEqual(self.client.get(endpoint, headers={'Range': 'bytes=999999-'}).status_code, 416)
        self.assertEqual(len(self.client.get('/api/memories/search?q=lantern').json()['results']), 1)
        db.init_db()
        self.assertTrue(db.get_memory(memory['id'])['has_audio'])
        self.assertEqual(self.client.delete(f'/api/memories/{memory["id"]}').status_code, 204)
        self.assertEqual(self.client.get(endpoint).status_code, 404)

    def test_recording_can_survive_without_transcription(self):
        memory = self.save('')
        self.assertEqual(memory['title'], 'Recorded memory')
        self.assertTrue(memory['has_audio'])
        self.assertEqual(memory['transcript'], '')

    def test_existing_text_memories_still_work(self):
        response = self.client.post('/api/memories', json={'transcript': 'An old family story'})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['has_audio'])
        self.assertEqual(self.client.get(f'/api/memories/{response.json()["id"]}/audio').status_code, 404)

    def test_empty_and_disguised_uploads_are_rejected(self):
        for data, status in [(b'', 400), (b'not audio', 415)]:
            result = self.client.post('/api/memories/recording', files={'file': ('voice.wav', data, 'audio/wav')})
            self.assertEqual(result.status_code, status)
        self.assertEqual(self.client.get('/api/memories').json(), [])

    def test_migrates_old_database_without_losing_or_unindexing_stories(self):
        old_path = Path(self.folder.name) / 'legacy.db'
        conn = sqlite3.connect(old_path)
        with conn:
            conn.execute('CREATE TABLE memories (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, transcript TEXT NOT NULL, created_at TEXT NOT NULL)')
            conn.execute('INSERT INTO memories VALUES (1, ?, ?, ?)', ('Porch', 'Grandmother sang on the porch', '2026-10-27T12:00:00+00:00'))
        conn.close()
        with patch.object(db, 'DB_PATH', old_path):
            db.init_db()
            self.assertEqual(db.get_memory(1)['transcript'], 'Grandmother sang on the porch')
            self.assertFalse(db.get_memory(1)['has_audio'])
            self.assertEqual(db.search_memories('porch')[0]['id'], 1)

    def test_transcription_failure_does_not_create_or_delete_memories(self):
        with patch('server.audio_routes.asr.transcribe', side_effect=RuntimeError('Unavailable')):
            result = self.client.post('/api/transcribe', files={'file': ('memory.wav', recording(), 'audio/wav')})
        self.assertEqual(result.status_code, 502)
        self.assertEqual(self.client.get('/api/memories').json(), [])
        self.assertTrue(self.save('')['has_audio'])

    def test_transcription_route_uses_uploaded_audio(self):
        with patch('server.audio_routes.asr.transcribe', return_value='A synthetic family story') as transcribe:
            result = self.client.post('/api/transcribe', files={'file': ('memory.wav', recording(), 'audio/wav')})
        self.assertEqual(result.json(), {'text': 'A synthetic family story'})
        self.assertEqual(transcribe.call_args.args[0], recording())


if __name__ == '__main__': unittest.main()
