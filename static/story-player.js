export function storyPlayer(status) {
  let audio = null, controller = null, objectUrl = null, generation = 0;
  function stop(announce = true) {
    generation++; controller?.abort(); controller = null;
    globalThis.speechSynthesis?.cancel();
    if (audio) { audio.pause(); audio.removeAttribute('src'); audio.load(); audio = null; }
    if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = null;
    if (announce) status('Stopped.');
  }
  function browserVoice(text, current) {
    if (!globalThis.speechSynthesis) { status('No speech playback is available in this browser.'); return; }
    const utterance = new SpeechSynthesisUtterance(text); utterance.rate = .96;
    utterance.onend = () => { if (current === generation) status('Finished reading.'); };
    utterance.onerror = () => { if (current === generation) status('Speech playback was interrupted.'); };
    globalThis.speechSynthesis.speak(utterance); status('Reading transcript with browser voice…');
  }
  async function play(memory, readTranscript = false) {
    stop(false); const current = generation; controller = new AbortController();
    try {
      if (memory.has_audio && !readTranscript) {
        audio = new Audio(`/api/memories/${memory.id}/audio`);
      } else {
        const config = await fetch('/api/config', { signal: controller.signal }).then(response => response.json());
        if (current !== generation) return;
        if (!config.tts_base_url?.trim()) { browserVoice(memory.transcript, current); return; }
        status('Preparing spoken transcript…');
        const response = await fetch('/api/tts', { method: 'POST', signal: controller.signal,
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: memory.transcript }) });
        if (!response.ok) throw new Error('Speech service unavailable.');
        const blob = await response.blob(); if (current !== generation) return;
        objectUrl = URL.createObjectURL(blob); audio = new Audio(objectUrl);
      }
      audio.onended = () => { if (current === generation) { stop(false); status('Finished.'); } };
      audio.onerror = () => { if (current === generation) { stop(false); status('Audio could not be played. Try reading the transcript.'); } };
      await audio.play(); if (current === generation) status(memory.has_audio && !readTranscript ? 'Playing your original recording…' : 'Reading transcript…');
    } catch (error) {
      if (current !== generation || error.name === 'AbortError') return;
      if ((!memory.has_audio || readTranscript) && memory.transcript) browserVoice(memory.transcript, current);
      else status('Could not play the original recording. Use the audio controls or read the transcript.');
    }
  }
  return { play, stop };
}
