<p align="center">
  <img src="../../icon.png" width="112" alt="AIpet 图标">
</p>

<h1 align="center">AIpet · 丛雨桌宠</h1>

<p align="center">
  <strong>使用提示词模拟人格、可自由切换本地与云端模型的 AI 桌面伴侣。</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows11&logoColor=white">
  <img alt="PyQt5" src="https://img.shields.io/badge/UI-PyQt5-41CD52?style=flat-square&logo=qt&logoColor=white">
  <img alt="Ollama" src="https://img.shields.io/badge/Local-Ollama-111111?style=flat-square&logo=ollama&logoColor=white">
  <a href="../../LICENSE"><img alt="许可证" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>

<p align="center">
  <a href="../../README.md">English</a> | <strong>简体中文</strong>
</p>

---

## 项目简介

AIpet 是一个面向 Windows 的丛雨桌宠。人格完全由提示词模拟，项目不再内置聊天 Transformer、LoRA、PyTorch 推理服务或模型下载脚本。

目前有两种后端模式：

| 模式 | 服务商 | 对话 | 视觉 | 默认对话模型 | 默认视觉模型 |
|---|---|:---:|:---:|---|---|
| Ollama | 任意兼容的本地模型 | ✓ | ✓ | `qwen3:14b` | `qwen2.5vl:7b` |
| API | DeepSeek | ✓ | — | `deepseek-chat` | — |
| API | 阿里云百炼 | ✓ | ✓ | `qwen-plus` | `qwen3-vl-plus` |

模型名都可以在设置窗口中修改。DeepSeek 当前只接入对话；需要屏幕视觉时请选择 Ollama 或阿里云。

## 主要改进

- Ollama / API 双模式，模型后端相互独立。
- 内置 DeepSeek 与阿里云 OpenAI 兼容接口。
- 对话模型和视觉模型可以分别选择。
- 首次启动显示可视化设置工作室，可测试连接并读取模型列表。
- 在界面中直接创建、导入或修改人格提示词。
- 模型只返回经过验证的中文、日语和情绪，不再生成立绘图层编号。
- 情绪由程序映射为固定立绘图层，更换模型也不会随机“拆脸”。
- 截图只在 Qt 主线程产生，网络分析放到后台。
- 配置、API Key 和历史记录移出仓库目录。
- GPT-SoVITS 失败时仍然显示文本，不会吞掉整次回答。

## 快速开始

```bash
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
conda env create -f environment.yml
conda activate aipet
python run.py
```

也可以手动创建环境：

```bash
conda create -n aipet python=3.10 -y
conda activate aipet
python -m pip install -r requirements.txt
python run.py
```

首次运行会打开 **AIpet Setup Studio**。这里可以选择 Ollama / API、填写服务地址或 Key、选择模型、编辑人格并设置屏幕感知和语音。

如果使用 Ollama，可以先准备示例模型：

```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

如果使用云端 API，也可以通过环境变量提供 Key：

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
$env:DASHSCOPE_API_KEY = "your-key"
```

## 可视化设置工作室

托盘菜单中的 **Settings Studio…** 可以随时打开设置。

- **Models**：后端模式、服务商、URL、对话模型、视觉模型、Ollama 上下文长度、超时和连接测试。
- **Character**：用户名、立绘组和人格提示词编辑器。
- **Automation**：屏幕感知、GPT-SoVITS、可选语音输入、显示器、立绘比例、空闲提醒和历史长度。

程序会自动添加结构化输出规则，所以人格提示词只需要描述身份、说话风格、关系和边界。

## 数据与隐私

Windows 下的用户数据位于：

```text
%APPDATA%\AIpet-Murasame\
├── config.json
├── history.json
└── personality.txt
```

临时语音和截图位于 `%LOCALAPPDATA%\AIpet-Murasame\cache`。屏幕感知默认关闭；启用后，截图只会发送给当前配置的视觉模型。

通过设置窗口填写的 Key 会保存在用户配置中。如果希望进一步分离凭据，可以把 Key 字段留空并使用 `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY` 环境变量。

## GPT-SoVITS 与语音输入

默认 TTS 地址为：

```text
http://127.0.0.1:9880/tts
```

远程部署时，把 **Remote reference root** 设置成 GPT-SoVITS 服务端看到的 `reference_voices` 路径。

Caps Lock 语音输入是可选功能，需要额外安装：

```bash
python -m pip install -r requirements-voice.txt
```

## 操作方式

| 操作 | 方式 |
|---|---|
| 输入消息 | 左键点击角色下半部分，输入后按 Enter |
| 取消输入 | 按 Escape |
| 摸头 | 在头部按住左键并横向移动 |
| 移动桌宠 | 按住鼠标中键拖动 |
| 语音输入 | 启用可选语音功能后长按 Caps Lock 两秒 |
| 设置、视觉、勿扰、记忆、退出 | 使用系统托盘菜单 |

## 测试

在 Conda 环境中运行：

```bash
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

## 已知限制

- 桌面行为主要面向 Windows 开发和测试。
- DeepSeek 当前只接入对话，不提供屏幕视觉选项。
- HTTP 请求采用协作式取消：旧请求可能在后台结束，但结果会被丢弃，不会覆盖新对话。
- 角色立绘和语音素材的授权范围可能不同于源代码许可证。

## 许可证与素材声明

源代码使用 [GNU Affero General Public License v3.0](../../LICENSE)。

这是用于学习和技术交流的非官方同人项目。丛雨及随附的第三方立绘、语音等素材权利归包括 YUZUSOFT 在内的各自权利人所有，不因源代码使用 AGPL 而被重新许可。未经许可请勿商用相关素材。
