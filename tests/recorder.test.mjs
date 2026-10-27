import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryRecorder } from '../static/recorder.js';
import { wavBlob } from '../static/transcription.js';
class FakeRecorder {
  static isTypeSupported(type) { return type === 'audio/webm;codecs=opus'; }
  constructor(stream, options) { this.state = 'inactive'; this.mimeType = options.mimeType; }
  start() { this.state = 'recording'; }
  stop() {
    this.state = 'inactive';
    queueMicrotask(() => { this.ondataavailable({ data: new Blob(['original voice']) }); this.onstop(); });
  }
}
function setup(media) {
  const states = [], audio = [], errors = [];
  const recorder = new MemoryRecorder({ media, Recorder: FakeRecorder, Recognition: null,
    state: phase => states.push(phase), audio: (...args) => audio.push(args), error: value => errors.push(value), transcript: () => {} });
  return { recorder, states, audio, errors };
}
const stream = stop => ({ getTracks: () => [{ stop }] });
test('keeps final data emitted after stop and releases microphone tracks', async () => {
  let stopped = false;
  const value = setup({ getUserMedia: async () => stream(() => { stopped = true; }) });
  await value.recorder.start(); value.recorder.stop(); await Promise.resolve();
  assert.equal(await value.audio[0][0].text(), 'original voice');
  assert.deepEqual(value.states, ['requesting', 'recording', 'stopping', 'idle']);
  assert.equal(stopped, true);
});
test('cancelling while permission is pending closes a later stream without recording', async () => {
  let allow, stopped = false;
  const value = setup({ getUserMedia: () => new Promise(resolve => { allow = resolve; }) });
  const pending = value.recorder.start(); value.recorder.cancel();
  allow(stream(() => { stopped = true; })); await pending;
  assert.equal(stopped, true); assert.equal(value.audio.length, 0); assert.equal(value.recorder.phase, 'idle');
});
test('late callbacks from discarded audio never contaminate a newer recording', async () => {
  const value = setup({ getUserMedia: async () => stream(() => {}) });
  await value.recorder.start(); value.recorder.cancel();
  await value.recorder.start(); await Promise.resolve();
  assert.equal(value.recorder.phase, 'recording');
  value.recorder.stop(); await Promise.resolve();
  assert.equal(value.audio.length, 1);
  assert.equal(await value.audio[0][0].text(), 'original voice');
});
test('permission denial is recoverable and does not invent audio', async () => {
  const value = setup({ getUserMedia: async () => { throw Object.assign(new Error('Denied'), { name: 'NotAllowedError' }); } });
  await value.recorder.start();
  assert.equal(value.recorder.phase, 'idle'); assert.equal(value.audio.length, 0);
  assert.match(value.errors[0], /denied/);
});
test('ASR conversion writes mono PCM WAV with clipped samples and a correct header', async () => {
  const bytes = await wavBlob(new Float32Array([-2, 0, 2]), 16000).arrayBuffer();
  const view = new DataView(bytes);
  assert.equal(new TextDecoder().decode(bytes.slice(0, 4)), 'RIFF');
  assert.equal(view.getUint16(22, true), 1); assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getInt16(44, true), -32768); assert.equal(view.getInt16(48, true), 32767);
});
