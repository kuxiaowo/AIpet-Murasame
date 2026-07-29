# macOS adapter

This adapter targets Apple Silicon Macs running macOS 13 or later. It keeps
macOS APIs inside `aipet.platforms.macos` and implements the shared platform
contracts without changing the Windows adapter.

Implemented platform behavior:

- native always-on-top windows that can join fullscreen Spaces;
- Option+V hold-to-talk input;
- Keychain-backed AutoDL credential storage;
- macOS application, cache, model, log, and audio-device policies;
- local GPT-SoVITS process discovery;
- Apple Silicon `.app` and DMG packaging.

## Run from source

Use Python 3.10:

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-voice.txt
.venv/bin/python main.py
```

macOS may request Accessibility, Microphone, or Screen Recording permission
when the corresponding feature is first used.

## Local GPT-SoVITS

Managed Windows GPT-SoVITS archives are intentionally not reused on macOS.
In **Settings → TTS**, choose **Local computer**, select the engine directory,
then click **Install macOS GPT-SoVITS base environment**. The installer uses a
pinned GPT-SoVITS release, downloads an isolated Python 3.10 runtime, installs
the required Python packages and common base assets. Murasame's character
weights and reference voices remain separate on-demand downloads.

For a source checkout, install `uv` in the environment that launches AIpet
before using the button:

```bash
.venv/bin/python -m pip install uv
```

The adapter also recognizes existing installations in these layouts:

```text
GPT-SoVITS/.venv/bin/python
.gpt-sovits-venv/bin/python
GPT-SoVITS/runtime/bin/python
GPT-SoVITS/bin/python
GPT-SoVITS/python
```

The engine directory must contain `api_v2.py` and
`GPT_SoVITS/configs/tts_infer.yaml`.

## Build the DMG

```bash
packaging/macos/build_dmg.sh
```

The output is `dist/macos/AIpet-Murasame.dmg`. Local builds are ad-hoc signed;
public distribution still requires an Apple Developer ID and notarization.
