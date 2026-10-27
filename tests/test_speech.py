import unittest
from unittest.mock import patch
import httpx
from server import asr, config


class SpeechTests(unittest.TestCase):
    def test_endpoint_accepts_root_v1_and_full_transcription_path(self):
        for value in ['https://speech.example', 'https://speech.example/v1', 'https://speech.example/v1/audio/transcriptions']:
            self.assertEqual(asr.transcription_url(value), 'https://speech.example/v1/audio/transcriptions')
        for value in ['file:///tmp/test', 'https://user:secret@speech.example', 'https://speech.example?key=secret']:
            with self.assertRaises(ValueError): asr.transcription_url(value)

    def test_private_key_is_never_forwarded_to_another_origin(self):
        with patch.dict('os.environ', {'LINTERNA_SPEECH_API_KEY': 'synthetic-key', 'LINTERNA_SPEECH_ORIGIN': 'https://speech.example'}):
            self.assertEqual(config.speech_headers('https://speech.example/v1/audio/transcriptions'), {'Authorization': 'Bearer synthetic-key'})
            self.assertEqual(config.speech_headers('https://unrelated.example/v1'), {})
            self.assertEqual(config.speech_headers('http://speech.example/v1'), {})

    def test_upstream_protocol_and_error_sanitization(self):
        original = httpx.Client
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'text': 'A remembered story'})
        def client(**kwargs): return original(transport=httpx.MockTransport(handler), **kwargs)
        with patch.object(asr, 'load_config', return_value={'asr_base_url': 'https://speech.example/v1', 'asr_model': 'local-asr'}), patch.object(asr, 'speech_headers', return_value={}), patch.object(asr.httpx, 'Client', side_effect=client):
            self.assertEqual(asr.transcribe(b'RIFF audio', 'audio/wav', 'memory.wav'), 'A remembered story')
        self.assertIn(b'local-asr', requests[0].content)
        self.assertIn(b'RIFF audio', requests[0].content)
        self.assertEqual(str(requests[0].url), 'https://speech.example/v1/audio/transcriptions')


if __name__ == '__main__': unittest.main()
