<p align="center">
  <img src="icon.png" width="112" alt="AIpet icon">
</p>

<h1 align="center">AIpet · Murasame</h1>

<p align="center">
  <strong>An AI-powered desktop companion that can talk, listen, react, and keep you company.</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows11&logoColor=white">
  <img alt="PyQt5" src="https://img.shields.io/badge/UI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>

<p align="center">
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/kuxiaowo/AIpet-Murasame?style=flat-square&logo=github"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/tags"><img alt="Latest tag" src="https://img.shields.io/github/v/tag/kuxiaowo/AIpet-Murasame?style=flat-square&label=version&sort=semver"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/kuxiaowo/AIpet-Murasame?style=flat-square"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/network/members"><img alt="GitHub forks" src="https://img.shields.io/github/forks/kuxiaowo/AIpet-Murasame?style=flat-square"></a>
</p>

<p align="center">
  <strong>English</strong> | <a href="docs/zh-CN/README.md">简体中文</a>
</p>

<p align="center">
  <a href="#quick-start"><img alt="Quick start" src="https://img.shields.io/badge/Docs-Quick_Start-0969DA?style=for-the-badge&logo=readthedocs&logoColor=white"></a>
  <a href="#configuration"><img alt="Configuration" src="https://img.shields.io/badge/Setup-Configuration-00897B?style=for-the-badge&logo=json&logoColor=white"></a>
  <a href="https://www.bilibili.com/video/BV1oi4wzSEJJ"><img alt="Watch the demo" src="https://img.shields.io/badge/Demo-Watch_Now-FB7299?style=for-the-badge&logo=bilibili&logoColor=white"></a>
  <a href="#troubleshooting"><img alt="Troubleshooting" src="https://img.shields.io/badge/Help-Troubleshooting-E67E22?style=for-the-badge&logo=bookstack&logoColor=white"></a>
</p>

---

## Overview

AIpet is a Windows desktop companion inspired by Murasame. It combines an always-on-top PyQt5 character window with cloud or local language models, expressive speech, optional voice input, screen awareness, and persistent conversation history.

This project is based in part on [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet) and adds rewritten components and new interaction features.

## Highlights

- **Cloud or local conversations** — use DeepSeek, Qwen, or a local Qwen model through Ollama.
- **Expressive speech** — synthesize emotion-aware voice output with [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS).
- **Voice input** — hold Caps Lock to talk when [faster-whisper](https://github.com/SYSTRAN/faster-whisper) input is enabled.
- **Screen awareness** — optionally let a Qwen vision model respond to what is happening on a selected display.
- **A companion that remembers** — conversation history, idle reactions, welcome-back messages, and two portrait sets.
- **Native desktop interaction** — a transparent, frameless PyQt5 window with tray controls and Do Not Disturb mode.

## Demo and tutorials

| Type | Video |
|---|---|
| Demo | [Let Murasame stay by your side](https://www.bilibili.com/video/BV1oi4wzSEJJ) |
| Latest tutorial | [V1.3.0 deployment tutorial](https://www.bilibili.com/video/BV1iw2XBREpd) |
| Earlier tutorials | [V1.2.2](https://www.bilibili.com/video/BV1ghCMBjEKK) · [V1.2.0](https://www.bilibili.com/video/BV1F6ykBwEDu) |

## Tech stack

| Area | Technology |
|---|---|
| Desktop UI | Python, PyQt5 |
| Language models | Qwen, DeepSeek, Ollama |
| Speech synthesis | GPT-SoVITS |
| Speech recognition | faster-whisper |
| Screen understanding | Qwen VL |
| Local service | FastAPI, Uvicorn |

## Requirements

- Windows
- Python 3.10 or newer; Python 3.10 is recommended if compatibility issues occur
- [Conda](https://docs.conda.io/) or another Python environment manager
- A DeepSeek/Qwen API key **or** a local Ollama model
- GPT-SoVITS locally, or access to a configured remote TTS service
- An NVIDIA GPU is recommended for local model and TTS workloads; cloud mode can avoid most local GPU requirements

> [!IMPORTANT]
> Extract or clone the project into a path without spaces, non-ASCII characters, parentheses, or other special symbols. Some bundled Windows tools are sensitive to such paths.

## Quick start

### 1. Download the project

Download a ZIP from GitHub, or clone the repository:

```bash
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
```

### 2. Create a Conda environment

```bash
conda create -n aipet python=3.10 -y
conda activate aipet
```

### 3. Choose a conversation backend

For a cloud backend, add your own key to the matching empty field in `config.json`, then set `model_type` to `deepseek` or `qwen`.

For local conversations, install [Ollama](https://ollama.com/download), set `model_type` to `local`, and download the required models:

```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

The vision model is only needed for local screen awareness.

### 4. Configure speech synthesis

For local TTS, place a compatible [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) package in `GPT-SoVITS/` next to `main.py`, and set `tts_type` to `local`.

An integrated-package guide is available [here](https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4). Choose a package compatible with your GPU.

For remote TTS, set `tts_type` to `cloud` and configure the SSH host and API endpoints for your deployment. The [AutoDL guide](https://www.autodl.com/docs/ssh/) and the latest [deployment tutorial](https://www.bilibili.com/video/BV1iw2XBREpd) show the expected setup.

### 5. Launch

```bash
python run.py
```

`run.py` checks Python and hardware compatibility, installs the required Python packages, downloads local models when needed, starts the TTS service, and launches the desktop pet.

## Configuration

The main options live in `config.json`.

| Key | Values | Purpose |
|---|---|---|
| `APIKEY.deepseek` | API key | DeepSeek cloud access |
| `APIKEY.qwen` | API key | Qwen cloud and cloud vision access |
| `model_type` | `deepseek`, `qwen`, `local` | Conversation backend |
| `tts_type` | `local`, `cloud` | Speech synthesis backend |
| `portrait` | `a`, `b` | Character outfit / portrait set |
| `user_name` | text | Name used to address the user |
| `screen_type` | `true`, `false` | Enable periodic screen awareness |
| `voice_trigger` | `true`, `false` | Enable Caps Lock voice input |
| `stt_model` | model name | faster-whisper model, such as `large-v3` |
| `screen_interval` | seconds | Delay between screen captures |
| `screen_index` | integer | Display used for the pet and screenshots |
| `DEFAULT_PORTRAIT_SCREEN_RATIO` | decimal | Maximum pet height relative to the display |
| `idle_thinking_minutes` | minutes | Short idle-reaction threshold |
| `idle_away_minutes` | minutes | Away / welcome-back threshold |

Keep API keys private. Do not commit real credentials to a public repository.

## Controls

| Action | Control |
|---|---|
| Type a message | Left-click the lower part of Murasame, type, then press Enter |
| Pat her head | Hold the left mouse button over her head and move horizontally |
| Move the pet | Drag with the middle mouse button |
| Talk | Hold Caps Lock for two seconds when voice input is enabled |
| Do Not Disturb, screenshots, history, exit | Use the system tray menu |

## Troubleshooting

<details>
<summary><strong>CUDA is unavailable</strong></summary>

Update the NVIDIA driver and make sure the installed PyTorch build is compatible with the detected CUDA version. Cloud mode can be used without a local NVIDIA workload.

</details>

<details>
<summary><strong>GPT-SoVITS is very slow</strong></summary>

Use an integrated package that matches your GPU generation. The package used for newer NVIDIA cards may differ from the general build.

</details>

<details>
<summary><strong>Conda says it must be initialized</strong></summary>

Run `conda init`, restart the terminal, and activate the environment again.

</details>

<details>
<summary><strong>An API key is rejected</strong></summary>

Check that the key belongs to the selected `model_type`, is still valid, and has available quota. Save `config.json` as valid UTF-8 JSON.

</details>

<details>
<summary><strong>The launcher closes immediately</strong></summary>

Move the project to a simple path without spaces or special characters, open a terminal in that directory, activate the environment, and run `python run.py` so the error remains visible.

</details>

## Roadmap

- [x] Persistent conversation history
- [x] Configurable pet size and display
- [x] One-command Python launcher
- [x] Alternate portrait / outfit
- [x] Cloud TTS experiment
- [x] Qwen model support
- [ ] More complete application logging
- [ ] More reliable always-on-top behavior in games

## License and asset notice

The source code is distributed under the [GNU Affero General Public License v3.0](LICENSE).

This is an unofficial fan project intended for study and technical exchange. Murasame and the included third-party character artwork, voice data, and related assets belong to their respective rights holders, including YUZUSOFT, and are not relicensed by the AGPL. Do not use this project or those assets commercially.

If AIpet made your desktop a little less lonely, consider leaving a ⭐.
