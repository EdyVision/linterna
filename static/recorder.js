export class MemoryRecorder {
  constructor({ state, audio, transcript, error, media = navigator.mediaDevices,
    Recorder = globalThis.MediaRecorder, Recognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition }) {
    Object.assign(this, { onState: state, onAudio: audio, onTranscript: transcript, onError: error, media, Recorder, Recognition });
    this.phase = 'idle'; this.generation = 0;
  }
  async start(browserTranscript = false) {
    if (this.phase !== 'idle') return;
    const generation = ++this.generation;
    this.phase = 'requesting'; this.onState(this.phase);
    try {
      if (!this.media?.getUserMedia || !this.Recorder) throw new Error('Recording needs a modern browser on localhost or HTTPS. You can still type a memory.');
      const stream = await this.media.getUserMedia({ audio: true });
      if (generation !== this.generation) { stream.getTracks().forEach(track => track.stop()); return; }
      this.stream = stream; this.chunks = []; this.bytes = 0;
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg;codecs=opus']
        .find(type => this.Recorder.isTypeSupported(type));
      this.recorder = new this.Recorder(stream, mimeType ? { mimeType } : undefined);
      this.recorder.ondataavailable = ({ data }) => {
        if (generation !== this.generation) return;
        if (data.size) { this.chunks.push(data); this.bytes += data.size; }
        if (this.bytes > 24 * 1024 * 1024) this.stop();
      };
      this.recorder.onerror = () => { if (generation !== this.generation) return; this.onError('Recording was interrupted. Keep any captured audio or try again.'); this.stop(); };
      this.recorder.onstop = () => {
        if (generation !== this.generation) return;
        clearTimeout(this.timer); this.release();
        const blob = new Blob(this.chunks, { type: this.recorder.mimeType || mimeType || 'audio/webm' });
        const duration = Math.min(300, (performance.now() - this.started) / 1000);
        this.phase = 'idle'; this.onState('idle');
        if (blob.size) this.onAudio(blob, duration);
        else this.onError('No audio was captured. Check your microphone and try again.');
      };
      if (browserTranscript && this.Recognition) {
        this.recognition = new this.Recognition();
        this.recognition.continuous = true; this.recognition.interimResults = false;
        this.recognition.lang = navigator.language || 'en-US';
        this.recognition.onresult = event => {
          if (generation !== this.generation) return;
          let text = '';
          for (let i = event.resultIndex; i < event.results.length; i++)
            if (event.results[i].isFinal) text += event.results[i][0].transcript + ' ';
          if (text.trim()) this.onTranscript(text.trim());
        };
        this.recognition.onerror = () => {};
        try { this.recognition.start(); } catch { /* Original audio remains available. */ }
      }
      this.started = performance.now(); this.recorder.start(1000);
      this.phase = 'recording'; this.onState(this.phase);
      this.timer = setTimeout(() => this.stop(), 300000);
    } catch (error) {
      if (generation !== this.generation) return;
      this.release(); this.phase = 'idle'; this.onState('idle');
      this.onError(error.name === 'NotAllowedError' ? 'Microphone access was denied. Allow it in browser settings or type your memory.' : error.message);
    }
  }
  stop() {
    if (this.phase === 'requesting') { this.cancel(); return; }
    if (this.phase !== 'recording') return;
    this.phase = 'stopping'; this.onState(this.phase);
    this.recognition?.stop();
    if (this.recorder?.state !== 'inactive') this.recorder.stop();
  }
  release() { this.stream?.getTracks().forEach(track => track.stop()); this.stream = null; }
  cancel() {
    this.generation++; clearTimeout(this.timer); this.recognition?.abort();
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
    this.release(); this.chunks = []; this.phase = 'idle'; this.onState('idle');
  }
}
