<p align="center">
  <img src="../../icon.png" width="112" alt="AIpet 图标">
</p>

<h1 align="center">AIpet · 丛雨 AI 桌宠</h1>

<p align="center">
  <strong>一个能对话、倾听、感知并陪伴你的 AI 桌面宠物。</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows11&logoColor=white">
  <img alt="PyQt5" src="https://img.shields.io/badge/UI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white">
  <a href="../../LICENSE"><img alt="许可证" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>

<p align="center">
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/stargazers"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/kuxiaowo/AIpet-Murasame?style=flat-square&logo=github"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/tags"><img alt="最新标签" src="https://img.shields.io/github/v/tag/kuxiaowo/AIpet-Murasame?style=flat-square&label=version&sort=semver"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/commits/main"><img alt="最近提交" src="https://img.shields.io/github/last-commit/kuxiaowo/AIpet-Murasame?style=flat-square"></a>
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/network/members"><img alt="GitHub Forks" src="https://img.shields.io/github/forks/kuxiaowo/AIpet-Murasame?style=flat-square"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> | <strong>简体中文</strong>
</p>

<p align="center">
  <a href="#快速开始"><img alt="快速开始" src="https://img.shields.io/badge/文档-快速开始-0969DA?style=for-the-badge&logo=readthedocs&logoColor=white"></a>
  <a href="#配置"><img alt="配置" src="https://img.shields.io/badge/设置-配置说明-00897B?style=for-the-badge&logo=json&logoColor=white"></a>
  <a href="https://www.bilibili.com/video/BV1oi4wzSEJJ"><img alt="观看演示" src="https://img.shields.io/badge/演示-立即观看-FB7299?style=for-the-badge&logo=bilibili&logoColor=white"></a>
  <a href="#常见问题"><img alt="常见问题" src="https://img.shields.io/badge/帮助-常见问题-E67E22?style=for-the-badge&logo=bookstack&logoColor=white"></a>
</p>

---

## 项目简介

AIpet 是一款以丛雨为灵感的 Windows 桌面宠物。它将置顶显示的 PyQt5 角色窗口与云端或本地大语言模型、情感语音、可选语音输入、屏幕感知及持久化对话记录结合在一起。

本项目部分参考了 [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)，并重写了部分组件、加入了新的交互功能。

## 功能亮点

- **云端或本地对话**：支持 DeepSeek、Qwen，也可以通过 Ollama 使用本地 Qwen 模型。
- **情感语音**：通过 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 合成带情绪的语音。
- **语音输入**：启用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 后，长按 Caps Lock 即可说话。
- **屏幕感知**：可以让 Qwen 视觉模型定期感知指定显示器上的内容。
- **有记忆的陪伴**：保存对话记录，支持闲置反应、回来时问候和两套立绘。
- **原生桌面交互**：透明无边框 PyQt5 窗口、托盘菜单和勿扰模式。

## 演示与教程

| 类型 | 视频 |
|---|---|
| 项目演示 | [让丛雨陪在你身边](https://www.bilibili.com/video/BV1oi4wzSEJJ) |
| 最新教程 | [V1.3.0 部署教程](https://www.bilibili.com/video/BV1iw2XBREpd) |
| 较早教程 | [V1.2.2](https://www.bilibili.com/video/BV1ghCMBjEKK) · [V1.2.0](https://www.bilibili.com/video/BV1F6ykBwEDu) |

## 技术栈

| 模块 | 技术 |
|---|---|
| 桌面界面 | Python、PyQt5 |
| 语言模型 | Qwen、DeepSeek、Ollama |
| 语音合成 | GPT-SoVITS |
| 语音识别 | faster-whisper |
| 屏幕理解 | Qwen VL |
| 本地服务 | FastAPI、Uvicorn |

## 环境要求

- Windows
- Python 3.10 或更高版本；遇到兼容问题时建议使用 Python 3.10
- [Conda](https://docs.conda.io/) 或其他 Python 环境管理工具
- DeepSeek / Qwen API Key，或本地 Ollama 模型
- 本地 GPT-SoVITS，或已经配置好的远程 TTS 服务
- 本地模型和 TTS 推荐使用 NVIDIA 显卡；云端模式可以避免大部分本地 GPU 要求

> [!IMPORTANT]
> 请把项目解压或克隆到不含空格、中文、括号及其他特殊符号的路径中。部分随附的 Windows 工具对路径字符较敏感。

## 快速开始

### 1. 下载项目

从 GitHub 下载 ZIP，或者克隆仓库：

```bash
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
```

### 2. 创建 Conda 环境

```bash
conda create -n aipet python=3.10 -y
conda activate aipet
```

### 3. 选择对话后端

使用云端模型时，在 `config.json` 对应的空字段中填入自己的 API Key，并把 `model_type` 设为 `deepseek` 或 `qwen`。

使用本地模型时，安装 [Ollama](https://ollama.com/download)，把 `model_type` 设为 `local`，并下载所需模型：

```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

只有启用本地屏幕感知时才需要视觉模型。

### 4. 配置语音合成

使用本地 TTS 时，将兼容的 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 整合包放到与 `main.py` 同级的 `GPT-SoVITS/` 目录，并将 `tts_type` 设为 `local`。

[这里](https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4)有整合包说明，请选择与你显卡兼容的版本。

使用远程 TTS 时，将 `tts_type` 设为 `cloud`，并配置远程部署所需的 SSH 主机和 API 地址。可以参考 [AutoDL SSH 文档](https://www.autodl.com/docs/ssh/)和最新的[部署教程](https://www.bilibili.com/video/BV1iw2XBREpd)。

### 5. 启动

```bash
python run.py
```

`run.py` 会检查 Python 与硬件兼容性、安装 Python 依赖、按需下载本地模型、启动 TTS 服务并运行桌宠。

## 配置

主要选项都在 `config.json` 中。

| 配置项 | 可选值 | 说明 |
|---|---|---|
| `APIKEY.deepseek` | API Key | DeepSeek 云端访问凭据 |
| `APIKEY.qwen` | API Key | Qwen 云端和云端视觉访问凭据 |
| `model_type` | `deepseek`、`qwen`、`local` | 对话后端 |
| `tts_type` | `local`、`cloud` | 语音合成后端 |
| `portrait` | `a`、`b` | 角色服装 / 立绘组 |
| `user_name` | 文本 | 丛雨称呼用户时使用的名字 |
| `screen_type` | `true`、`false` | 是否定期进行屏幕感知 |
| `voice_trigger` | `true`、`false` | 是否启用 Caps Lock 语音输入 |
| `stt_model` | 模型名 | faster-whisper 模型，例如 `large-v3` |
| `screen_interval` | 秒 | 两次屏幕截图之间的间隔 |
| `screen_index` | 整数 | 桌宠所在及截图使用的显示器 |
| `DEFAULT_PORTRAIT_SCREEN_RATIO` | 小数 | 桌宠相对屏幕的最大高度 |
| `idle_thinking_minutes` | 分钟 | 短时间闲置反应阈值 |
| `idle_away_minutes` | 分钟 | 离开及回来问候阈值 |

请妥善保管 API Key，不要把真实凭据提交到公开仓库。

## 操作方式

| 操作 | 控制方式 |
|---|---|
| 输入消息 | 左键点击丛雨下半部分，输入文字后按 Enter |
| 摸头 | 在头部按住鼠标左键并横向移动 |
| 移动桌宠 | 按住鼠标中键拖动 |
| 语音输入 | 启用语音功能后长按 Caps Lock 两秒 |
| 勿扰、截图、清空记录、退出 | 使用系统托盘菜单 |

## 常见问题

<details>
<summary><strong>CUDA 不可用</strong></summary>

更新 NVIDIA 驱动，并确认安装的 PyTorch 版本与检测到的 CUDA 版本兼容。也可以改用不依赖本地 NVIDIA 负载的云端模式。

</details>

<details>
<summary><strong>GPT-SoVITS 响应很慢</strong></summary>

请使用与你显卡代际匹配的整合包。较新的 NVIDIA 显卡可能需要不同于通用版本的专用包。

</details>

<details>
<summary><strong>Conda 提示尚未初始化</strong></summary>

执行 `conda init`，重启终端，然后再次激活环境。

</details>

<details>
<summary><strong>API Key 被拒绝</strong></summary>

确认 Key 与当前选择的 `model_type` 对应、仍然有效且账户有可用额度，同时将 `config.json` 保存为有效的 UTF-8 JSON。

</details>

<details>
<summary><strong>启动器立即关闭</strong></summary>

将项目移动到不含空格或特殊字符的简单路径，在该目录打开终端并激活环境，然后运行 `python run.py`，这样可以保留错误信息。

</details>

## 开发计划

- [x] 对话记录持久化
- [x] 可配置桌宠大小和显示器
- [x] Python 一键启动
- [x] 可切换立绘 / 服装
- [x] 云端 TTS 尝试
- [x] Qwen 模型支持
- [ ] 更完整的应用日志
- [ ] 改进游戏中的窗口置顶可靠性

## 许可证与素材声明

源代码使用 [GNU Affero General Public License v3.0](../../LICENSE) 发布。

这是一个用于学习和技术交流的非官方同人项目。丛雨及项目中包含的第三方角色立绘、语音数据和其他相关素材，权利归包括 YUZUSOFT 在内的各自权利人所有，且不因源代码采用 AGPL 而被重新许可。请勿将本项目或相关素材用于商业用途。

如果 AIpet 让你的桌面没那么冷清，欢迎点个 ⭐。
