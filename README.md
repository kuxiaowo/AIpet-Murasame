<p align="center">
  <img src="icon.png" width="112" alt="AIpet icon">
</p>

<h1 align="center">AIpet · Murasame</h1>

<p align="center">
  <strong>A prompt-driven AI desktop companion with interchangeable local and cloud models.</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows11&logoColor=white">
  <img alt="PyQt5" src="https://img.shields.io/badge/UI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white">
  <img alt="Ollama" src="https://img.shields.io/badge/Local-Ollama-111111?style=flat-square&logo=ollama&logoColor=white">
  <img alt="Cloud APIs" src="https://img.shields.io/badge/API-DeepSeek%20%7C%20Alibaba%20%7C%20OpenAI-6246EA?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>

<p align="center">
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/kuxiaowo/AIpet-Murasame?style=flat-square&logo=github"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/kuxiaowo/AIpet-Murasame?style=flat-square"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/network/members"><img alt="GitHub forks" src="https://img.shields.io/github/forks/kuxiaowo/AIpet-Murasame?style=flat-square"></a>
</p>

<p align="center">
  <strong>English</strong> | <a href="docs/zh-CN/README.md">简体中文</a>
</p>

<p align="center">
  <a href="#quick-start"><img alt="Quick start" src="https://img.shields.io/badge/Docs-Quick_Start-0969DA?style=for-the-badge&logo=readthedocs&logoColor=white"></a>
  <a href="#settings"><img alt="Settings" src="https://img.shields.io/badge/Setup-Settings-00897B?style=for-the-badge&logo=qt&logoColor=white"></a>
  <a href="#architecture"><img alt="Architecture" src="https://img.shields.io/badge/Guide-Architecture-E67E22?style=for-the-badge&logo=diagramsdotnet&logoColor=white"></a>
</p>

---

## Overview

AIpet is an always-on-top Murasame desktop companion for Windows. The character is simulated entirely through a personality prompt—there is no bundled chat Transformer, LoRA adapter, PyTorch runtime, or model download script.

You can run conversations through a local [Ollama](https://ollama.com/) service or an OpenAI-compatible cloud API. DeepSeek, Alibaba Cloud Model Studio, and OpenAI are built in. Chat and vision backends are configured independently, so a cloud chat model can use a local Ollama vision model.

## Highlights

- **Two backend modes** — local Ollama or a cloud API.
- **Selectable models** — configure chat and vision models independently.
- **Built-in providers** — DeepSeek, Alibaba Cloud, OpenAI, and local Ollama.
- **Bilingual settings** — switch between English and Simplified Chinese instantly, choose backends, load model lists, edit the personality prompt, and configure behavior without hand-editing JSON.
- **Stable character output** — each response uses validated structured JSON with Chinese text, Japanese TTS text, one of six emotions, and a safe `a`/`b` portrait pose.
- **Deterministic portraits** — the model may switch between the two validated poses, while pose and emotion map to known portrait layers in code; model changes cannot invent broken layer IDs.
- **Adaptive multi-monitor sizing** — after middle-button dragging to another display, the portrait resizes to that screen's available height.
- **Live diagnostic console** — optionally open a real-time command window with correlated request/response JSON, worker events, warnings, and exception details. UTF-8 logs are retained by day under `logs/YYYY-MM-DD.log`; API secrets are redacted and large base64 media is represented by length and SHA-256 metadata.
- **Optional screen awareness** — screenshots are captured safely in the Qt GUI thread, the pet window is masked before analysis, and the vision model can identify likely on-screen characters including Murasame.
- **Optional speech** — GPT-SoVITS-compatible output and faster-whisper Caps Lock input.
- **Private user state** — configuration, keys, and conversation history live outside the Git repository.

## Supported backends

| Purpose | Provider | Default model |
|---|---|---|
| Chat | Ollama | `qwen3:14b` |
| Chat | DeepSeek | `deepseek-v4-flash` |
| Chat | Alibaba Cloud Model Studio | `qwen-plus` |
| Chat | OpenAI | `gpt-5.6-luna` |
| Vision | Ollama (local) | `qwen2.5vl:7b` |
| Vision | Alibaba Cloud Model Studio | `qwen3-vl-plus` |
| Vision | OpenAI | `gpt-5.6-luna` |

Model fields are editable. The defaults are starting points, not hard-coded requirements.

## Architecture

```mermaid
flowchart LR
    UI["PyQt5 desktop pet<br>Settings"] --> C["Conversation worker"]
    UI --> V["Vision worker"]
    C --> CB{"Chat backend"}
    V --> VB{"Independent vision backend"}
    CB --> O["Ollama /api/chat"]
    CB --> D["DeepSeek API"]
    CB --> A["Alibaba Cloud API"]
    CB --> OA["OpenAI API"]
    VB --> VO["Local Ollama"]
    VB --> A
    VB --> OA
    C --> R["Validated reply<br>zh + ja + emotion"]
    R --> P["Deterministic portrait layers"]
    R --> T["Optional GPT-SoVITS"]
    P --> UI
    T --> UI
```

The language model never controls files, Qt widgets, portrait layer IDs, or shell commands. Screen text is wrapped as untrusted event context before it reaches the character prompt.

## Requirements

- Windows 10 or 11
- Conda
- Python 3.10 or newer
- One of:
  - [Ollama](https://ollama.com/) with a chat model
  - a DeepSeek API key
  - an Alibaba Cloud Model Studio API key
- Optional: GPT-SoVITS for speech output; AIpet can manage the local service
- Optional: microphone dependencies from `requirements-voice.txt`

A local NVIDIA GPU is not required by AIpet itself. Hardware needs depend on the Ollama and TTS models you choose.

## Quick start

### 1. Clone the project

```bash
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
```

### 2. Create the Conda environment

```bash
conda env create -f environment.yml
conda activate aipet
```

Or create it manually:

```bash
conda create -n aipet python=3.10 -y
conda activate aipet
python -m pip install -r requirements.txt
```

For optional Caps Lock speech input:

```bash
python -m pip install -r requirements-voice.txt
```

### 3. Prepare a backend

For Ollama, install it and pull models of your choice. For example:

```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

For a cloud API, have a DeepSeek, Alibaba Cloud, or OpenAI key ready. Keys may also be provided through environment variables:

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
$env:DASHSCOPE_API_KEY = "your-key"
$env:OPENAI_API_KEY = "your-key"
```

### 4. Launch

```bash
python main.py
```

Settings opens on first launch. Save a valid configuration and AIpet starts immediately. The launcher does not install packages or modify CUDA. Model downloads start only after an explicit Whisper download action or approval of the TTS model prompt. A downloaded local GPT-SoVITS service starts on demand before the first TTS request, or from the manual control in Settings.

## Settings

Open **Settings…** from the tray menu at any time.

### Models

- Switch between Ollama and API mode.
- Select DeepSeek, Alibaba Cloud, or OpenAI for chat.
- Edit server URLs and timeout values.
- Select an independent Ollama, Alibaba Cloud, or OpenAI vision backend.
- Enable or disable DeepSeek V4 thinking mode.
- Select a faster-whisper model or repository ID and an explicit download directory. AIpet downloads and loads the model from that exact directory and prompts when it is missing.
- Switch the settings and tray UI between English and Simplified Chinese.
- Limit Ollama's context window to avoid unexpectedly large model allocations.
- Model lists load automatically when Settings opens. Use the connection
  buttons to refresh after changing an address, provider, or API key.

The model loader calls Ollama's `GET /api/tags` or the cloud provider's
`GET /models`. Chat and vision lists use their own configured endpoints.
Every model selector remains editable, so custom IDs still work when an
endpoint omits a model or model listing is unavailable.

DeepSeek V4 uses the current `deepseek-v4-flash` and `deepseek-v4-pro` IDs. Retired `deepseek-chat` and `deepseek-reasoner` settings are migrated automatically. Existing combined chat/vision configurations are migrated to the new independent vision settings.

### Character

- Set the user name and portrait set.
- Create or edit the personality prompt visually.
- Import a UTF-8 text or Markdown prompt.

AIpet adds the structured response contract automatically. The personality file only needs to describe identity, tone, relationships, and boundaries.

### Automation

- Enable periodic screen vision and choose its interval.
- Locate a local GPT-SoVITS installation, validate the Murasame voice weights and references, and check whether the service is online.
- Download missing Murasame GPT/SoVITS weights with resumable in-card progress after accepting the model notice.
- Configure optional faster-whisper input.
- Select a display, portrait scale, idle thresholds, and history size.
- Persist Do Not Disturb from either Settings or the tray, and clear saved conversation history from Settings with confirmation.

## Data and API keys

On Windows, user data is stored under:

```text
%APPDATA%\AIpet-Murasame\
├── config.json
├── history.json
└── personality.txt
```

Temporary audio and screenshots use `%LOCALAPPDATA%\AIpet-Murasame\cache`. New Whisper and TTS downloads use the directories entered in Settings and stop with a prompt when a required directory is blank. The repository's `models` directory, optionally overridden with `AIPET_MODEL_DIR`, is retained only for discovering assets downloaded by older versions and is ignored by Git.

API keys entered in Settings are stored in the user configuration. For better separation, leave those fields blank and use `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`, or `OPENAI_API_KEY`. Runtime files and secrets are ignored by Git.

Screen vision is disabled by default. When enabled, screenshots are sent only to the vision backend selected in Settings.

## GPT-SoVITS

AIpet calls a GPT-SoVITS-compatible endpoint directly; the default is:

```text
http://127.0.0.1:9880/tts
```

The six reference categories are `平静`, `高兴`, `害羞`, `生气`, `惊讶`, and `着急`. Reference audio is stored under `reference_voices` inside the configured voice model directory, so only one voice model path is required.

For a loopback endpoint, the two path fields are also the exact download destinations: character weights and references go to the voice model directory, while the engine archive is extracted into the GPT-SoVITS directory. Downloading prompts for any required path left empty. AIpet no longer silently redirects a new download to the project model directory. If GPT-SoVITS is not detected, AIpet reads the NVIDIA GPU name and downloads the RTX 50-series package or the general Windows package as appropriate. The Settings card reports preparation, verification, download, extraction, installation, and cleanup separately. Extraction prefers native 7-Zip with multithreading enabled and falls back to Windows bsdtar; installation uses a same-volume atomic move instead of copying the extracted tree. Downloads do not open browser pages. Missing character weights come from `LemonQu/Murasame_SoVITS`, while reference voices come from `kuxiaowo/Murasame-tts-reference-voice`.

When a local TTS request arrives and the API is offline, AIpet starts `api_v2.py` with the engine's bundled Python runtime, waits for its OpenAPI endpoint, loads the configured character weights, and then sends the synthesis request. Settings also provides manual start and stop controls with visible startup stages. Duplicate launches are serialized, and AIpet only stops a process it started itself. Remote endpoints are health-checked but never launched or stopped locally.

TTS failures do not discard a model response: AIpet still displays the text and shows the speech error through the tray.

## Controls

| Action | Control |
|---|---|
| Type a message | Left-click the lower part of the character, type, then press Enter |
| Cancel input | Press Escape |
| Pat her head | Hold the left mouse button over her head and move horizontally |
| Move the pet | Drag with the middle mouse button |
| Talk | Hold Caps Lock for two seconds when optional speech input is enabled |
| Settings, vision, DND, memory, exit | Use the system tray menu |

## Development

Run the test suite in the Conda environment:

```bash
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

The tests cover configuration validation, storage, structured responses, provider payloads, portrait composition, prompt-injection boundaries, and an offscreen Qt construction smoke test.

Main modules:

```text
classes/
├── murasame_class.py   # Qt interaction, playback, idle and screen events
└── workers.py          # Background conversation and vision work
tool/
├── backends.py         # Ollama and OpenAI-compatible API adapters
├── config.py           # Validated user settings
├── portraits.py        # Emotion-to-layer mapping
├── storage.py          # Conversation persistence
├── tts.py              # GPT-SoVITS client
└── tts_service.py      # Managed local GPT-SoVITS process
ui/
└── settings_dialog.py  # Visual configuration and prompt editor
```

## Known limitations

- Desktop behavior is designed and tested primarily for Windows.
- Chat and vision credentials are configured separately; selecting OpenAI or Alibaba Cloud for both may therefore require entering the same key in both panels or using an environment variable.
- Network cancellation is cooperative: an interrupted HTTP request may finish in the background, but stale results are ignored.
- Character artwork and voice assets can have terms different from the source-code license.

## License and asset notice

Source code is distributed under the [GNU Affero General Public License v3.0](LICENSE).

This is an unofficial fan project for study and technical exchange. Murasame and the included third-party artwork, voice data, and related assets belong to their respective rights holders, including YUZUSOFT, and are not relicensed by the AGPL. Do not use those assets commercially without permission.

If AIpet made your desktop a little less lonely, consider leaving a ⭐.
