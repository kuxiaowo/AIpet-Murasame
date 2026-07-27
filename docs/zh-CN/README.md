<p align="center">
  <img src="../../icon.png" width="112" alt="AIpet 图标">
</p>

<h1 align="center">AIpet · 丛雨桌宠 for macOS</h1>

<p align="center">
  <strong>面向 Apple Silicon macOS 的丛雨桌宠适配版。</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="macOS" src="https://img.shields.io/badge/Platform-macOS-000000?style=flat-square&logo=apple&logoColor=white">
  <img alt="PyQt5" src="https://img.shields.io/badge/UI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white">
  <img alt="Ollama" src="https://img.shields.io/badge/Local-Ollama-111111?style=flat-square&logo=ollama&logoColor=white">
  <a href="../../LICENSE"><img alt="许可证" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>

<p align="center">
  <a href="https://github.com/kuxiaowo/AIpet-Murasame/stargazers"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/kuxiaowo/AIpet-Murasame?style=flat-square&logo=github"></a>
  <a href="https://space.bilibili.com/1067030066"><img alt="哔哩哔哩" src="https://img.shields.io/badge/Bilibili-视频教程-00A1D6?style=flat-square&logo=bilibili&logoColor=white"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> | <strong>简体中文</strong>
</p>

---

> 本 Fork 是 AIpet-Murasame 的 macOS 版本，保留原项目的界面和操作方式，
> 并补充 Apple Silicon、全屏 Space、macOS 输入法和本地 TTS 等原生适配。

如果你喜欢让丛雨陪在桌面上，就请给项目一颗
[Star ⭐](https://github.com/kuxiaowo/AIpet-Murasame/stargazers)，或去
[B站](https://space.bilibili.com/1067030066)
点个关注吧～丛雨会很开心，维护者也会更有动力继续更新的！

## 项目简介

本项目是 AIpet-Murasame 的 Apple Silicon macOS 适配版。它将透明 PyQt5
角色窗口、本地或云端对话、可选的屏幕感知、GPT-SoVITS 语音输出和
faster-whisper 语音输入组合在一起，保留原作者 V2 的界面和操作方式，
并补充 macOS 原生适配。

项目基于
[LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)
继续开发。演示、部署视频和项目动态见
[哔哩哔哩主页](https://space.bilibili.com/1067030066)。

## 主要功能

- 支持 Ollama 本地对话，以及 DeepSeek、阿里云百炼和 OpenAI 兼容 API
- 对话与视觉后端可独立配置，屏幕感知默认关闭
- 提示词人格、两套立绘姿态、六种情绪和四套服装
- 本地或 AutoDL 云端 GPT-SoVITS 语音合成
- 基于 faster-whisper 的按键语音输入
- 对话记忆、屏幕事件摘要、主动提醒和持久化勿扰模式
- 透明多屏窗口、macOS 菜单栏集成、全屏 Space 与原生输入法兼容、
  中英双语设置和结构化诊断日志

## 快速开始

本 Fork 面向 Apple Silicon macOS。Windows EXE 和构建说明属于原作者项目，
这里不作为本版本的安装方式。

### 在 macOS 上运行

需要：

- Apple Silicon Mac
- Python 3.10 或更高版本
- Xcode Command Line Tools（运行 `xcode-select --install` 安装）

双击 **`start_macos.command`**，或在终端执行：

```zsh
./start_macos.command
```

首次启动会创建 `.venv`、安装程序及语音输入依赖，并编译一个很小的原生
全屏辅助组件。macOS 可能会请求以下权限：

- “屏幕录制”：供屏幕视觉使用
- “麦克风”：供语音输入使用
- “辅助功能 / 输入监控”：供 macOS 上长按 Option+V 触发语音输入

只有当其他应用进入全屏 Space 时，程序才会切换到原生辅助窗口。它沿用原来
的桌宠操作，并支持在全屏中使用 macOS 拼音组合输入和候选词。

### 配置对话后端

AIpet 至少需要本地 Ollama 或一种云端 API。

使用 Ollama 时，启动服务并拉取对话模型；视觉模型可选：

```zsh
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

使用云端服务时，可以在设置中填写密钥，也可以使用环境变量：

```zsh
export DEEPSEEK_API_KEY="your-key"
export DASHSCOPE_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

macOS 终端中请使用对应的 `export NAME="value"` 写法。

首次启动后，选择后端与模型，填写用户名称，检查人格提示词并保存。视觉、TTS
和语音输入属于可选功能，相关依赖尚未准备好时请先保持关闭。

## 可选功能

| 功能 | 配置方法 |
|---|---|
| 屏幕感知 | 启用“屏幕视觉”，选择 Ollama、阿里云百炼或 OpenAI 兼容视觉模型。截图仅作临时处理，不写入对话历史。 |
| 本地 TTS | 启用“TTS → 本地计算机”，在设置中点击“安装 macOS GPT-SoVITS”；安装程序会把官方引擎和基础模型放在项目目录内，并将 Conda 环境放在 `~/.local/share/AIpet-Murasame/`。完成后点击“下载角色语音模型”，获取丛雨权重和参考音频。 |
| AutoDL TTS | 启用“TTS → AutoDL 云端”，填写 SSH 登录信息、远程命令和参考音频目录。远程实例需已在 `9880` 端口提供 GPT-SoVITS 服务。 |
| 语音输入 | 启用语音输入，选择麦克风和 faster-whisper 模型，长按 Option+V 两秒开始录音。 |

TTS 失败不会丢弃文字回复。临时截图、录音和合成语音会自动清理，也可以在
设置中手动清除。

如果 macOS 的 GPT-SoVITS Python 环境不在引擎目录内，可将
`AIPET_GPT_SOVITS_PYTHON` 指向该环境的 Python 可执行文件。

## 桌宠操作

| 操作 | 控制方式 |
|---|---|
| 输入消息 | 左键单击角色下半部分，输入后按 Enter |
| 取消输入 | 按 Escape |
| 摸头 | 在头部按住鼠标左键并横向移动 |
| 移动桌宠 | 按住鼠标中键拖动 |
| 语音对话 | 长按 Option+V 两秒 |
| 设置、视觉、勿扰、记忆、退出 | 使用系统托盘菜单 |

把桌宠拖到另一台显示器后，程序会自动更新显示器和立绘比例。
macOS 原生全屏窗口保持相同的操作方式。

## 数据与隐私

macOS 上的持久化数据及日志位于 `~/.config/AIpet-Murasame/`，运行缓存位于
其 `cache/` 子目录，下载模型默认位于项目的 `models/` 目录。AutoDL 密码
保存在 macOS 钥匙串中。

在设置中填写的 API Key 会写入 `config.json`。如果不希望密钥进入配置文件，
请把密钥字段留空并使用环境变量。日志会对已识别的密钥字段脱敏，并把大型
Base64 媒体替换成元数据。

## 开发

macOS 上运行：

```zsh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

主要目录：

```text
classes\    桌宠交互、后台任务和下载
tool\       模型后端、配置、存储、语音和诊断
ui\         中英双语设置窗口
native_overlay/  macOS 原生全屏及输入桥接
packaging\  可重复执行的 PyInstaller 构建
tests\      单元测试和 UI 冒烟测试
```

## 已知限制

- 独占全屏或受反作弊保护的画面仍可能覆盖桌宠。
- macOS 辅助组件面向 Apple Silicon，并在首次启动时于本机编译。
- Apple Silicon 上的 faster-whisper 使用 CPU。
- 本地对话、视觉与 TTS 的速度取决于模型和硬件。
- 角色立绘与语音素材的使用条款可能不同于源代码许可证。

## 致谢与许可证

- 原作桌宠项目：
  [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)
- AIpet V2 原项目：
  [kuxiaowo/AIpet-Murasame](https://github.com/kuxiaowo/AIpet-Murasame)
- 语音合成项目：
  [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)

源代码依据
[GNU Affero General Public License v3.0](../../LICENSE)
发布。

本项目是用于学习与技术交流的非官方同人项目。丛雨以及项目包含的第三方立绘、
语音和其他相关素材，其权利归 YUZUSOFT 等各自权利人所有，不因 AGPL
源代码许可证而被重新授权。未经许可，请勿将这些素材用于商业用途。
