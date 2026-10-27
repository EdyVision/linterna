import { MemoryRecorder } from './recorder.js';
import { transcribeRecording } from './transcription.js';
export function memoryCapture({ status, showDraft, saved, stopPlayback, media }) {
  const lantern = document.querySelector('#lantern'), label = document.querySelector('#lantern-label');
  const transcript = document.querySelector('#transcript'), draft = document.querySelector('#draft');
  const preview = document.querySelector('#draft-audio'), save = document.querySelector('#btn-save');
  let blob = null, duration = 0, url = null, generation = 0, pending = false, saving = false, config = {}, controller = null;
  function cancelTranscription() { controller?.abort(); controller = null; }
  function state(phase) {
    lantern.classList.toggle('recording', phase === 'recording');
    lantern.setAttribute('aria-pressed', String(phase === 'recording'));
    lantern.setAttribute('aria-busy', String(['requesting', 'stopping'].includes(phase)));
    save.disabled = phase !== 'idle';
    label.textContent = phase === 'recording' ? 'Recording · tap to finish, or release your hold' :
      phase === 'requesting' ? 'Allow microphone access to begin' : phase === 'stopping' ? 'Keeping your recording…' :
        'Tap to record · tap again to finish · or press and hold';
    if (phase === 'recording') status('Recording your voice. Up to five minutes per memory.');
  }
  function clearAudio() {
    preview.pause(); preview.removeAttribute('src'); preview.classList.add('hidden'); preview.load();
    if (url) URL.revokeObjectURL(url); url = null; blob = null;
  }
  async function transcribe() {
    if (!blob) { status('Record a memory first.'); return; }
    cancelTranscription(); const ticket = generation;
    controller = new AbortController(); const signal = controller.signal;
    status('Transcribing with your configured service… Your voice is already available to preview.');
    try {
      const text = await transcribeRecording(blob, signal);
      if (ticket !== generation || signal.aborted) return;
      transcript.value = text; status(text ? 'Your words are ready. Edit them or save your memory.' : 'No words detected. Your original recording can still be saved.');
    } catch (error) { if (!signal.aborted && ticket === generation) status(error.message + ' You can still save the original recording.'); }
    finally { if (controller?.signal === signal) controller = null; }
  }
  const recorder = new MemoryRecorder({ state, error: status, media,
    transcript: text => { transcript.value = [transcript.value.trim(), text].filter(Boolean).join(' '); },
    audio: (value, seconds) => {
      blob = value; duration = seconds; url = URL.createObjectURL(value); preview.src = url; preview.classList.remove('hidden');
      if (config.asr_base_url?.trim()) void transcribe();
      else status(transcript.value.trim() ? 'Voice and transcript captured. Edit or save your memory.' : 'Voice captured. Add a transcription endpoint in Config, type your words, or save the recording as it is.');
    },
  });
  async function start() {
    if (saving || pending || recorder.phase !== 'idle') return;
    if ((blob || transcript.value.trim()) && !confirm('Replace the unsaved memory?')) return;
    generation++; const ticket = generation; pending = true; cancelTranscription(); stopPlayback(false);
    clearAudio(); transcript.value = ''; showDraft(); state('requesting');
    try {
      const response = await fetch('/api/config'); if (!response.ok) throw new Error('Could not read recording settings.');
      config = await response.json(); if (ticket !== generation) return;
      pending = false;
      await recorder.start(!config.asr_base_url?.trim());
    } catch (error) { if (ticket === generation) { state('idle'); status(error.message); } }
    finally { if (ticket === generation) pending = false; }
  }
  function stop() {
    if (pending) { generation++; pending = false; state('idle'); status('Recording cancelled before it began.'); }
    else recorder.stop();
  }
  function discard() { if (saving) return; generation++; pending = false; cancelTranscription(); recorder.cancel(); clearAudio(); transcript.value = ''; draft.classList.add('hidden'); status(''); }
  async function saveMemory() {
    if (saving) return;
    if (pending || recorder.phase !== 'idle') { status('Finish recording first.'); return; }
    if (!blob && !transcript.value.trim()) { status('Record a memory or add some words first.'); return; }
    cancelTranscription(); saving = true; save.disabled = true; lantern.disabled = true; transcript.disabled = true;
    document.querySelector('#btn-discard').disabled = true; status('Keeping your memory…');
    try {
      let response;
      if (blob) {
        const form = new FormData(); form.append('file', blob, 'memory');
        form.append('transcript', transcript.value.trim()); form.append('duration_seconds', String(duration));
        response = await fetch('/api/memories/recording', { method: 'POST', body: form });
      } else response = await fetch('/api/memories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ transcript: transcript.value.trim() }) });
      const memory = await response.json(); if (!response.ok) throw new Error(typeof memory.detail === 'string' ? memory.detail : 'Memory could not be saved.');
      generation++; clearAudio(); transcript.value = ''; draft.classList.add('hidden');
      await saved(memory); status(memory.has_audio ? 'Memory kept. Your original voice is ready to play back.' : 'Your written memory is kept.');
    } catch (error) { status(error.message); }
    finally { saving = false; save.disabled = false; lantern.disabled = false; transcript.disabled = false; document.querySelector('#btn-discard').disabled = false; }
  }
  let pressed = 0, startedHere = false;
  lantern.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    event.preventDefault(); lantern.setPointerCapture(event.pointerId);
    pressed = performance.now(); startedHere = !pending && recorder.phase === 'idle';
    if (startedHere) void start(); else stop();
  });
  lantern.addEventListener('pointerup', () => { if (startedHere && performance.now() - pressed >= 350) stop(); });
  lantern.addEventListener('pointercancel', stop);
  lantern.addEventListener('click', event => { if (event.detail === 0) { pending || recorder.phase !== 'idle' ? stop() : void start(); } });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); cancelTranscription(); } });
  window.addEventListener('pagehide', () => { recorder.cancel(); cancelTranscription(); clearAudio(); });
  transcript.addEventListener('input', cancelTranscription);
  document.querySelector('#btn-transcribe').addEventListener('click', () => void transcribe());
  return { save: saveMemory, discard, cancelTranscription, busy: () => saving || pending || recorder.phase !== 'idle' };
}
