# AutoDub Studio

AutoDub Studio is a Windows-first Python desktop app for fully local video dubbing.

It takes a source video, transcribes it with WhisperX, translates it with Argos Translate, generates dubbed speech with Piper, optionally assigns different voices to detected speakers, and exports a dubbed video plus transcript files.

## Highlights

- Windows-first desktop app with a bootstrap launcher
- Main UI built with CustomTkinter
- Offline-first after the initial dependency, tool, and model downloads
- Fixed local stack only: no cloud APIs, no account login, no backend switching
- Managed app data under `data/`
- Sequential queue support for processing multiple videos one after another

## Fixed Stack

- GUI: CustomTkinter
- Media I/O: FFmpeg / ffprobe
- Speech-to-text + alignment: WhisperX
- Translation: Argos Translate
- Text-to-speech: Piper
- Speaker grouping: SpeechBrain ECAPA embeddings + local clustering
- Optional speaker gender matching: audEERING wav2vec2 age/gender
- Storage: JSON + files in app-managed folders

## What It Exports

Each job can produce:

- Dubbed video
- Transcript JSON
- Word timestamp JSON
- Translated segments JSON
- Speaker map JSON
- Burned-in subtitles plus external `.srt`
- Per-job metadata JSON

## How To Run

### Recommended

Double-click:

- [`start.pyw`](/c:/Users/adria/Desktop/autotranslatev1/start.pyw)

This opens the bootstrap launcher first, checks dependencies, and then starts the main app.

### Install Python dependencies manually

On Windows you can also run:

- [`install_requirements.bat`](/c:/Users/adria/Desktop/autotranslatev1/install_requirements.bat)

Or from a terminal:

```powershell
python -m pip install -r requirements.txt
python start.pyw
```

## First-Run Setup

On first launch the app can guide you through missing pieces such as:

- Python packages
- FFmpeg / ffprobe
- WhisperX model
- Piper runtime
- Piper voices
- Argos language packages
- SpeechBrain ECAPA asset
- audEERING speaker gender model

After setup, the app is intended to run locally without online services.

## Project Layout

```text
start.pyw
requirements.txt
install_requirements.bat
data/
files/
```

- `files/` contains the app code
- `data/models/` stores managed runtimes and models
- `data/projects/` stores per-job working folders
- `data/exports/` stores exported deliverables
- `data/logs/` stores bootstrap, app, and job logs

## Current Status

This repository is the foundation of a real desktop product, but it is still early-stage.

Current MVP capabilities:

- single-video and queued batch dubbing
- source-language auto-detect
- translated dubbing into supported Piper target languages
- optional per-speaker voice mode
- optional gender-aware voice matching
- burned-in subtitles
- automatic setup/install flows for most managed assets

## Known Limitations

- Speaker grouping is best-effort and still experimental.
- Gender-aware voice matching is best-effort, not guaranteed.
- Background audio preservation is approximate, not full stem separation.
- Dubbing quality depends heavily on source audio quality and available local voices.
- The app is built for Windows first; other platforms are not the primary target.

## Notes

- This project uses only local/offline inference components after setup.
- Some third-party model assets may have their own licensing terms. Review them before redistribution or commercial use.

