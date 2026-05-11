# AutoDub Studio

AutoDub Studio is a Windows-first desktop app for local video dubbing. It takes a source video, transcribes the speech, translates the lines, generates a dubbed voice track, mixes it back into the video, and writes the useful sidecar files so you can inspect or reuse the result.

The project is built for people who want an offline-first workflow: setup downloads Python packages, tools, and models, then normal processing runs on your own machine.

## What It Does

- Extracts audio from a video with FFmpeg.
- Transcribes speech with WhisperX and keeps word/segment timing.
- Optionally groups detected speakers with SpeechBrain.
- Optionally estimates speaker gender with the local audEERING age/gender model.
- Translates segments with Argos Translate.
- Generates speech with Piper voices.
- Fits generated speech back onto the timeline.
- Preserves some background audio while suppressing centered original speech.
- Exports a dubbed video, transcript JSON, word timing JSON, translated segment JSON, speaker map JSON, metadata, and SRT subtitles.

## Current Scope

This is not a polished commercial dubbing suite yet. It is a practical local pipeline with a GUI around it.

Works best for:

- short to medium videos
- clean dialogue
- one or a few speakers
- offline experiments
- batch processing where perfect studio quality is not required

Current limits:

- Speaker grouping is best effort.
- Gender detection is best effort and can be wrong.
- Background preservation is approximate, not full stem separation.
- Voice quality depends on the installed Piper voice.
- Translation quality depends on available Argos language packages.
- GPU support depends on the installed PyTorch/CTranslate2 stack.

## Requirements

- Windows 10/11
- Python 3.10+
- Enough disk space for models and generated project files
- Optional but recommended: NVIDIA GPU with a working driver

The installer creates a local `.venv` folder in the repo. It does not need to install packages globally.

## Quick Start

From this folder:

```powershell
.\install_requirements.bat
```

Then launch:

```powershell
.\start.pyw
```

You can also double-click `start.pyw`.

If you have an NVIDIA GPU, the installer tries to install CUDA-enabled PyTorch wheels first:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade --force-reinstall torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
```

If GPU still shows unavailable in the app, check:

```powershell
nvidia-smi
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

For CUDA use, `torch.__version__` should include a CUDA suffix such as `+cu128`, `torch.version.cuda` should not be `None`, and `torch.cuda.is_available()` should be `True`.

## First Run Setup

Open the `Setup` page after launch. It checks:

- app folders
- Python packages
- FFmpeg and ffprobe
- WhisperX model cache
- Argos Translate packages
- Piper runtime and voices
- SpeechBrain speaker grouping asset
- audEERING speaker gender model

The setup page can install most missing pieces. Models and language packages can be large.

## Recommended Workflow

1. Install dependencies with `install_requirements.bat`.
2. Launch `start.pyw`.
3. Go to `Setup` and install missing runtime pieces.
4. Go to `Home`.
5. Pick a video.
6. Choose source and target language.
7. Choose single voice or per-speaker voice mode.
8. Enable gender-aware voice matching only if you want the audEERING model to guide voice assignment.
9. Start the job.
10. Inspect logs in `Processing`, segments in `Transcript`, and output paths in `Export`.

## Output Files

Each job stores working files under:

```text
data/projects/<job-id>/
```

Final export bundles are copied under:

```text
data/exports/<job-id>/
```

Important files:

- `dubbed_video.mp4` - final dubbed video
- `transcript.json` - source transcript with timings and speaker labels
- `words.json` - word-level timing data
- `translated_segments.json` - translated segment text and adjusted timing
- `speaker_map.json` - segment-to-speaker mapping, voice map, and gender guesses when available
- `subtitles.srt` - external subtitle file
- `metadata.json` - job settings, warnings, timing data, and output metadata
- `job.log` - per-job processing log

Generated data is intentionally ignored by Git.

## Project Layout

```text
start.pyw                  Launcher
install_requirements.bat   Windows dependency installer
requirements.txt           Python dependency pins
files/                     Application source
data/                      Local runtime data, models, projects, exports, logs
```

Notable source folders:

- `files/gui/` - CustomTkinter UI
- `files/core/` - job pipeline and result types
- `files/stt/` - WhisperX wrapper and transcript schemas
- `files/translate/` - Argos Translate integration
- `files/tts/` - Piper runtime and voice handling
- `files/speakers/` - speaker grouping and gender estimation
- `files/media/` - FFmpeg extraction, muxing, and timeline mixing
- `files/setup/` - runtime/model installers and environment checks
- `files/storage/` - settings, project, and export persistence

## Dependency Notes

AutoDub Studio is a glue app around several third-party tools and models:

- CustomTkinter
- FFmpeg
- WhisperX
- faster-whisper / CTranslate2
- PyTorch / torchaudio / torchvision
- Argos Translate
- Piper / piper-tts
- SpeechBrain
- audEERING age/gender model
- ONNX Runtime

The app code can be modified, sold, reused, or redistributed under this repository's license. That does not change the licenses for third-party software, model files, voice files, language packs, datasets, or downloaded assets.

If a model, voice, package, or tool has its own license or usage terms, those terms still apply. This project does not grant permission to bypass, relicense, remove, weaken, or ignore third-party licenses. Before redistributing a bundled build, selling model outputs, shipping model weights, or using the app commercially, review the license terms for every model and dependency you include.

## License

The original AutoDub Studio project code in this repository is released under The Unlicense. See `LICENSE`.

That means you can use, copy, modify, publish, distribute, sublicense, sell, or repackage this project's own code with minimal restriction.

This license applies only to project code and documentation that this repository owns. It does not apply to third-party dependencies, downloaded model weights, voice files, language packages, FFmpeg builds, PyTorch wheels, or any other external component. Those keep their own licenses.

## Development Notes

Keep generated files out of commits:

- `.venv/`
- `data/`
- `__pycache__/`
- `*.pyc`
- `*.part`
- logs

Run a quick syntax check from the repo root:

```powershell
.\.venv\Scripts\python.exe -m compileall files start.pyw
```

For dependency resolution without installing:

```powershell
.\.venv\Scripts\python.exe -m pip install --dry-run --upgrade -r requirements.txt
```
