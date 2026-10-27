---
title: "Linterna: keep the voice behind the memory"
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26).*

## What I Built

A transcript can tell you what someone said. It cannot keep the little pause before a punchline, the way they pronounce your name, or the laugh halfway through a story.

I built **Linterna**, a small, local oral-history app for keeping those things together: the recording, the words, and a way to find the memory again.

For this week's theme, I leaned toward remembrance. A lantern is something you light to keep a person or a story present. In Linterna, you tap a watercolor lantern, tell a memory, and keep it. Smaller lanterns float independently through the night sky, with an occasional shooting star crossing above them.

The interaction is deliberately small. There is no account to create and no conversation feed to manage. Pick a story by date, search its words, and listen.

## Demo

![Linterna records a memory, transcribes it, saves it and plays the original recording](https://raw.githubusercontent.com/EdyVision/linterna/main/docs/linterna-demo.gif)

The GIF uses synthetic speech to demonstrate the actual browser recording, transcription, save and playback flow. No family recording or private memory is included. The transcription runs against my existing private speech service.

You can tap to start and tap again to finish, or press and hold. Once the recording ends, you can preview your voice and edit the transcript before saving. If transcription is unavailable, the recording can still be saved. Your story does not disappear because a model request failed.

**Play recording** plays the original voice. **Read transcript** is a separate narration option. That distinction matters: a generated voice should never quietly replace the person who told the story.

Linterna runs locally. There is no public instance collecting visitors' family recordings.

## Code

{% github EdyVision/linterna %}

[Source code and setup instructions](https://github.com/EdyVision/linterna)

The application code is MIT licensed. The browser interface is plain JavaScript, HTML and CSS, with a FastAPI server and SQLite storage.

## How I Built It

The speech models do practical work here:

- **NVIDIA Nemotron ASR** transcribes the recording through my privately hosted, compatible speech endpoint. The tested deployment uses the `nemotron-3.5-asr-streaming-0.6b.q8_0` model. NVIDIA documents the underlying [Nemotron ASR family here](https://build.nvidia.com/nvidia/nemotron-asr-streaming/modelcard).
- **Magpie TTS** provides optional narration for a written transcript. It is useful for text-only memories, but the saved original recording remains the primary playback option. [NVIDIA's speech documentation](https://docs.nvidia.com/nim/speech/26.05.0/tts/) describes the TTS service.

Although the ASR model supports streaming, this version transcribes a completed recording. I am not claiming live captions or a streaming speech interface.

The browser uses `getUserMedia` and `MediaRecorder` to capture real audio. A separate WAV conversion sends mono, 16 kHz audio to ASR, while the original recording is kept for playback. The service URL and model ID are configurable; my infrastructure is not required to run someone else's copy.

SQLite stores the audio and transcript in the same memory record. That keeps saving and deletion together, without loose recording files becoming separated from their stories. SQLite FTS and a small TF-IDF ranking pass support topic searches. The latter is local text ranking, not an embeddings model or an LLM pretending to remember your family.

A few less visible details made a real difference:

- Recording data can arrive after Stop is pressed. I wait for the final recorder event before offering the audio to save.
- A late microphone permission result cannot restart a cancelled recording.
- Failed transcription keeps the draft audio available.
- Existing text-only memories survive the schema migration.
- Browser recordings can lack useful duration metadata. When FFmpeg is installed, the server remuxes the container without re-encoding the voice, so playback is seekable.
- Configured speech credentials stay on the server and are bound to their configured origin. They are not returned to the browser or committed to the repository.

Validation includes ten backend tests and five recorder/WAV tests, plus a real browser run through capture, private transcription, saving, page refresh and original-audio playback. The GIF comes from that working flow.

## Why Does Open Innovation Matter?

An oral-history tool should help you keep something, not create another dependency you are afraid of losing.

Open-weight speech models let me run transcription and narration on infrastructure I control. I do not need a new transcription subscription to capture each story, and the app does not need a particular vendor's account system to work.

The recordings and transcripts live in an ordinary local SQLite database. The code is available, the speech endpoint can be changed, and the original voice is retained independently of the model output.

That does not make every configuration automatically private or offline. My tested setup uses private network speech services. Point Linterna at an external provider and that provider receives the audio or text you send. Browser speech captions can also depend on the browser vendor. Keeping that boundary clear is part of building something trustworthy.

I also kept the transcript editable. Speech recognition can get names and words wrong, including this demo's spelling of “Linterna.” The original recording remains there to check against. A model's best guess should not become the only surviving version of a memory.

I used Codex to help develop and validate Linterna and prepare this write-up. The recording, transcription, storage and playback described here were exercised, rather than represented by a mock transcript.

My aim for this final week was simple: make something small enough to finish and useful enough to keep. A voice, a story, and a lantern you can return to.
