export async function transcriptionAudio(blob) {
  const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
  const Offline = globalThis.OfflineAudioContext || globalThis.webkitOfflineAudioContext;
  if (!Context || !Offline) return blob;
  const context = new Context();
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer());
    const offline = new Offline(1, Math.ceil(decoded.duration * 16000), 16000);
    const source = offline.createBufferSource(); source.buffer = decoded;
    source.connect(offline.destination); source.start();
    const rendered = await offline.startRendering();
    return wavBlob(rendered.getChannelData(0), 16000);
  } finally { await context.close(); }
}
export function wavBlob(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer);
  const text = (offset, value) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  text(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => { const value = Math.max(-1, Math.min(1, sample)); view.setInt16(44 + i * 2, value < 0 ? value * 32768 : value * 32767, true); });
  return new Blob([buffer], { type: 'audio/wav' });
}
export async function transcribeRecording(blob, signal) {
  const audio = await transcriptionAudio(blob);
  if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
  const form = new FormData(); form.append('file', audio, audio.type === 'audio/wav' ? 'memory.wav' : 'memory.webm');
  const response = await fetch('/api/transcribe', { method: 'POST', body: form, signal });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || 'Transcription failed. Your original recording is still available.');
  return result.text;
}
