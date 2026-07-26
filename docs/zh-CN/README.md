<p align="center">
  <img src="../../icon.png" width="112" alt="AIpet 图标">
</p>

<h1 align="center">AIpet · 丛雨桌宠</h1>

<p align="center">
  <strong>使用提示词塑造人格，可自由切换本地与云端模型的 AI 桌面伴侣。</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows11&logoColor=white">
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

如果你喜欢让丛雨陪在桌面上，就请给项目一颗
[Star ⭐](https://github.com/kuxiaowo/AIpet-Murasame/stargazers)，或去
[B站](https://space.bilibili.com/1067030066)
点个关注吧～丛雨会很开心，维护者也会更有动力继续更新的！

## 项目简介

AIpet 是一款面向 Windows 的丛雨 AI 桌宠。它将透明 PyQt5 角色窗口、本地或
云端对话、可选的屏幕感知、GPT-SoVITS 语音输出和 faster-whisper 语音输入
组合在一起。

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
- 透明多屏窗口、Windows 置顶守护、中英双语设置和结构化诊断日志

## 快速开始

项目主要支持 Windows 10 和 Windows 11。

### 直接运行 Windows EXE

1. 从项目 [Releases 页面](https://github.com/kuxiaowo/AIpet-Murasame/releases)
   中提供 Windows 程序的版本下载 `AIpet.exe`。如果该版本没有 EXE，请使用
   下方的源码方案。
2. 把程序放到长期使用且可写的目录，例如 `C:\AIpet\`。
3. 双击 `AIpet.exe`。

EXE 已包含应用程序和 faster-whisper 运行依赖，不要求安装 Python、Conda
或 Git。聊天模型、Whisper 模型及 GPT-SoVITS 资源不会打进 EXE；可选资源
只会在设置界面确认后下载。

### 从源码运行

先安装 [Git](https://git-scm.com/) 和
[Conda 或 Miniconda](https://docs.conda.io/)，然后执行：

```powershell
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
conda env create -f environment.yml
conda activate aipet
python main.py
```

源码版如需语音输入，再安装附加依赖：

```powershell
python -m pip install -r requirements-voice.txt
```

### 配置对话后端

AIpet 至少需要本地 Ollama 或一种云端 API。

使用 Ollama 时，启动服务并拉取对话模型；视觉模型可选：

```powershell
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

使用云端服务时，可以在设置中填写密钥，也可以使用环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
$env:DASHSCOPE_API_KEY = "your-key"
$env:OPENAI_API_KEY = "your-key"
```

首次启动后，选择后端与模型，填写用户名称，检查人格提示词并保存。视觉、TTS
和语音输入属于可选功能，相关依赖尚未准备好时请先保持关闭。

## 可选功能

| 功能 | 配置方法 |
|---|---|
| 屏幕感知 | 启用“屏幕视觉”，选择 Ollama、阿里云百炼或 OpenAI 兼容视觉模型。截图仅作临时处理，不写入对话历史。 |
| 本地 TTS | 启用“TTS → 本地计算机”，选择 GPT-SoVITS 引擎和丛雨语音模型目录。缺少的托管资源可在确认后下载。 |
| AutoDL TTS | 启用“TTS → AutoDL 云端”，填写 SSH 登录信息、远程命令和参考音频目录。远程实例需已在 `9880` 端口提供 GPT-SoVITS 服务。 |
| 语音输入 | 启用语音输入，选择麦克风、计算设备和 faster-whisper 模型。长按 Caps Lock 两秒开始录音，松开后识别并发送。 |

TTS 失败不会丢弃文字回复。临时截图、录音和合成语音会自动清理，也可以在
设置中手动清除。

## 桌宠操作

| 操作 | 控制方式 |
|---|---|
| 输入消息 | 左键单击角色下半部分，输入后按 Enter |
| 取消输入 | 按 Escape |
| 摸头 | 在头部按住鼠标左键并横向移动 |
| 移动桌宠 | 按住鼠标中键拖动 |
| 语音对话 | 启用语音输入后长按 Caps Lock 两秒 |
| 设置、视觉、勿扰、记忆、退出 | 使用系统托盘菜单 |

把桌宠拖到另一台显示器后，程序会自动更新显示器和立绘比例。

## 数据与隐私

Windows 上的设置和持久化数据保存在：

```text
%APPDATA%\AIpet-Murasame\
├── config.json
├── history.json
├── screen_memory.json
├── personality.txt
└── logs\
```

临时运行数据保存在 `%LOCALAPPDATA%\AIpet-Murasame\cache\`。下载模型默认
保存在 `C:\AIpet\models\`；可以通过 `AIPET_MODEL_DIR` 修改模型目录。

在设置中填写的 API Key 会写入 `config.json`。如果不希望密钥进入配置文件，
请把密钥字段留空并使用环境变量。日志会对已识别的密钥字段脱敏，并把大型
Base64 媒体替换成元数据。

## 开发

在 `aipet` Conda 环境中运行测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

构建 Windows 单文件 EXE：

```powershell
.\packaging\build_exe.ps1
```

脚本会在需要时创建独立的 `aipet_build_whisper` Conda 环境，最终输出
`dist\AIpet.exe`。构建环境未变化时可跳过依赖安装：

```powershell
.\packaging\build_exe.ps1 -SkipDependencyInstall
```

主要目录：

```text
classes\    桌宠交互、后台任务和下载
tool\       模型后端、配置、存储、语音和诊断
ui\         中英双语设置窗口
packaging\  可重复执行的 PyInstaller 构建
tests\      单元测试和 UI 冒烟测试
```

## 已知限制

- 桌面行为目前主要针对 Windows 设计和测试。
- 独占全屏或受反作弊保护的画面仍可能覆盖桌宠。
- 本地对话、视觉与 TTS 的速度取决于模型和硬件。
- 角色立绘与语音素材的使用条款可能不同于源代码许可证。

## 致谢与许可证

- 原作桌宠项目：
  [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)
- 语音合成项目：
  [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)

源代码依据
[GNU Affero General Public License v3.0](../../LICENSE)
发布。

本项目是用于学习与技术交流的非官方同人项目。丛雨以及项目包含的第三方立绘、
语音和其他相关素材，其权利归 YUZUSOFT 等各自权利人所有，不因 AGPL
源代码许可证而被重新授权。未经许可，请勿将这些素材用于商业用途。
