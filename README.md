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
  <img alt="macOS" src="https://img.shields.io/badge/Platform-macOS-000000?style=flat-square&logo=apple&logoColor=white">
  <img alt="PyQt5" src="https://img.shields.io/badge/UI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white">
  <img alt="Ollama" src="https://img.shields.io/badge/Local-Ollama-111111?style=flat-square&logo=ollama&logoColor=white">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>

<p align="center">
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/kuxiaowo/AIpet-Murasame?style=flat-square&logo=github"></a>
  <a href="https://space.bilibili.com/1067030066"><img alt="Bilibili" src="https://img.shields.io/badge/Bilibili-Video%20guides-00A1D6?style=flat-square&logo=bilibili&logoColor=white"></a>
</p>

<p align="center">
  <strong>English</strong> | <a href="docs/zh-CN/README.md">简体中文</a>
</p>

---

If you enjoy having Murasame on your desktop, please leave a
[Star ⭐](https://github.com/kuxiaowo/AIpet-Murasame/stargazers) or follow the
project on [Bilibili](https://space.bilibili.com/1067030066). It would make
her—and the maintainer—very happy.

## Overview

AIpet is an always-on-top Murasame desktop companion for Windows and Apple
Silicon macOS. It combines a transparent PyQt5 character window with local or
cloud conversations, optional screen awareness, GPT-SoVITS speech output, and
faster-whisper speech input. This edition keeps the upstream V2 interface and
behavior while adding native macOS integration.

Based on [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet).
Videos and project updates are available on
[Bilibili](https://space.bilibili.com/1067030066).

## Features

- Local conversations with Ollama, or cloud conversations through DeepSeek,
  Alibaba Cloud Model Studio, and OpenAI-compatible APIs
- Independent local or cloud vision backend for optional screen awareness
- Prompt-based personality, two portrait sets, six emotions, and four outfits
- Local or AutoDL-hosted GPT-SoVITS speech synthesis
- Hold-to-talk speech input powered by faster-whisper
- Conversation memory, screen-event summaries, proactive reminders, and a
  persistent Do Not Disturb mode
- Transparent multi-monitor window, Windows topmost watchdog, native macOS
  fullscreen Spaces and input-method support, bilingual settings, and
  structured diagnostic logs

## Quick start

Windows 10/11 and Apple Silicon macOS are supported.

### Run the Windows EXE

Choose one executable from the
[Releases page](https://github.com/kuxiaowo/AIpet-Murasame/releases):

- **`AIpet.exe` (standard build, about 194 MiB):** does not bundle CUDA.
  Use this build for CPU-based Whisper transcription or when local
  speech-recognition GPU acceleration is not needed. This is the recommended
  download if you are unsure which build to choose.
- **`AIpet-with-cuda.exe` (CUDA build, about 1.06 GiB):** bundles CUDA 12
  cuBLAS, cuDNN 9, and NVRTC for local faster-whisper acceleration on a
  compatible NVIDIA GPU. A compatible NVIDIA graphics driver is still
  required. If CUDA is selected in Settings, use this build.

Both builds provide the same application features and settings interface.
The CUDA build is larger only because it includes the GPU runtime libraries.

1. Download the selected EXE. If a release has no EXE asset, use the source
   installation below.
2. Place it in a writable permanent directory such as `C:\AIpet\`.
3. Double-click the downloaded EXE.

The EXEs include the application and faster-whisper runtime, so Python, Conda,
and Git are not required. Chat models, Whisper models, and GPT-SoVITS assets
are not bundled; optional downloads begin only after confirmation in Settings.

### Run from source

Install [Git](https://git-scm.com/) and
[Conda or Miniconda](https://docs.conda.io/), then run:

```powershell
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
conda env create -f environment.yml
conda activate aipet
python main.py
```

To enable speech input in a source installation:

```powershell
python -m pip install -r requirements-voice.txt
```

### Run on macOS

Requirements:

- Apple Silicon Mac
- Python 3.10 or later
- Xcode Command Line Tools (`xcode-select --install`)

Double-click **`start_macos.command`**, or run:

```zsh
./start_macos.command
```

The first launch creates `.venv`, installs the application and speech-input
dependencies, and compiles the small native fullscreen helper. macOS may ask
for these permissions:

- **Screen Recording** for Screen Vision
- **Microphone** for speech input
- **Accessibility / Input Monitoring** for the macOS Option+V hold-to-talk trigger

The native helper appears only while another application occupies a fullscreen
Space. It preserves the original character interaction and supports macOS
Pinyin composition and candidate selection in fullscreen.

### Configure a conversation backend

AIpet needs either a local Ollama service or a cloud API.

For Ollama, start the service and pull a chat model. The vision model is
optional:

```powershell
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

For cloud services, enter credentials in Settings or use environment variables:

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
$env:DASHSCOPE_API_KEY = "your-key"
$env:OPENAI_API_KEY = "your-key"
```

On macOS, use the equivalent `export NAME="value"` syntax in Terminal.

On first launch, select the backend and model, set the user name, review the
personality prompt, and save. Keep vision, TTS, and speech input disabled until
their dependencies are ready.

## Optional capabilities

| Capability | Setup |
|---|---|
| Screen awareness | Enable **Screen Vision** and choose an Ollama, Alibaba Cloud, or OpenAI-compatible vision model. Screenshots are temporary and are not added to conversation history. |
| Local TTS | Enable **TTS → Local computer**. On macOS, click **Install GPT-SoVITS for macOS** in Settings; the installer places the official engine and base models in the project and keeps its Conda environment under `~/.local/share/AIpet-Murasame/`. Then click **Download voice model** for Murasame's weights and references. |
| AutoDL TTS | Enable **TTS → AutoDL cloud**, provide the SSH login, password, remote command, and reference-voice directory. The remote instance must already expose GPT-SoVITS on port `9880`. |
| Speech input | On Windows, enable speech input, choose a microphone, device, and faster-whisper model, then hold Caps Lock for two seconds to record. On macOS, hold Option+V for two seconds instead. |

TTS errors do not discard text replies. Temporary screenshots, recordings, and
generated speech are cleaned automatically and can also be cleared from
Settings.

For a macOS GPT-SoVITS environment outside the engine directory, set
`AIPET_GPT_SOVITS_PYTHON` to that environment's Python executable.

## Controls

| Action | Control |
|---|---|
| Type a message | Left-click the lower part of the character, type, then press Enter |
| Cancel input | Press Escape |
| Pat her head | Hold the left mouse button over her head and move horizontally |
| Move the pet | Drag with the middle mouse button |
| Talk | On Windows, hold Caps Lock for two seconds; on macOS, hold Option+V for two seconds |
| Settings, vision, DND, memory, exit | Use the system tray menu |

Dragging the pet to another monitor updates its display and portrait scale.
The same controls remain available in the native macOS fullscreen window.

## Data and privacy

On Windows, settings and persistent state are stored under:

```text
%APPDATA%\AIpet-Murasame\
├── config.json
├── history.json
├── screen_memory.json
├── personality.txt
└── logs\
```

Disposable runtime data is stored under
`%LOCALAPPDATA%\AIpet-Murasame\cache\`. Downloaded models use
`C:\AIpet\models\` by default; set `AIPET_MODEL_DIR` to override that location.

On macOS, persistent data and logs are stored under
`~/.config/AIpet-Murasame/`, runtime cache under its `cache/` subdirectory,
and downloaded models in the repository's `models/` directory by default.
AutoDL passwords are stored in macOS Keychain.

API keys entered in Settings are stored in `config.json`. Leave those fields
blank and use environment variables if you prefer to keep keys out of the
configuration file. Logs redact recognized secret fields and replace large
Base64 media with metadata.

## Development

Run the test suite in the `aipet` Conda environment:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

On macOS:

```zsh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Build both single-file Windows executables with:

```powershell
.\packaging\build_exe.ps1
```

The script creates an isolated `aipet_build_whisper` Conda environment when
needed and writes:

- `dist\AIpet.exe`: standard CPU build.
- `dist\AIpet-with-cuda.exe`: CUDA build with the CUDA 12 cuBLAS, cuDNN 9,
  and NVRTC runtime bundled for local Whisper GPU inference.

Reuse the installed build dependencies with:

```powershell
.\packaging\build_exe.ps1 -SkipDependencyInstall
```

When skipping dependency installation, the build environment must already
contain the CUDA 12 cuBLAS, cuDNN 9, and NVRTC DLLs. If they are outside the
build environment's `Library\bin`, provide their locations with:

```powershell
.\packaging\build_exe.ps1 -SkipDependencyInstall `
  -CudaDllDirectory C:\path\to\cublas\bin `
  -CudnnDllDirectory C:\path\to\cudnn\bin `
  -CudaNvrtcDllDirectory C:\path\to\nvrtc\bin
```

Main project areas:

```text
classes\    desktop interaction, workers, and downloads
tool\       backends, configuration, storage, speech, and diagnostics
ui\         bilingual settings window
native_overlay/  native macOS fullscreen and input bridge
packaging\  reproducible PyInstaller build
tests\      unit and UI smoke tests
```

## Limitations

- Exclusive-fullscreen or anti-cheat-protected surfaces may cover the pet.
- The macOS helper targets Apple Silicon and is compiled locally on first run.
- faster-whisper runs on CPU on Apple Silicon; its CUDA mode is for compatible
  Windows/NVIDIA systems.
- Local chat, vision, and TTS performance depends on the selected model and
  hardware.
- Character artwork and voice assets may have terms different from the source
  code license.

## Credits and license

- Original desktop-pet project:
  [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)
- Upstream AIpet V2 project and Windows implementation:
  [kuxiaowo/AIpet-Murasame](https://github.com/kuxiaowo/AIpet-Murasame)
- Speech-synthesis project:
  [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)

Source code is distributed under the
[GNU Affero General Public License v3.0](LICENSE).

This is an unofficial fan project for study and technical exchange. Murasame
and the included third-party artwork, voice data, and related assets belong to
their respective rights holders, including YUZUSOFT, and are not relicensed by
the AGPL. Do not use those assets commercially without permission.
