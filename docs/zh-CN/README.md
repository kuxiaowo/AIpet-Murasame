



## macOS（Apple Silicon）


macOS Apple Silicon 适配版请前往[Releases 页面](../../releases)下载；从源码运行时，请在项目目录执行 `start_macos.command`。<p align="center">
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
  <img alt="云端 API" src="https://img.shields.io/badge/API-DeepSeek%20%7C%20Alibaba%20%7C%20OpenAI-6246EA?style=flat-square">
  <a href="../../LICENSE"><img alt="许可证" src="https://img.shields.io/github/license/kuxiaowo/AIpet-Murasame?style=flat-square&color=8A2BE2"></a>
</p>


<p align="center">
  <a href="../../README.md">English</a> | <strong>简体中文</strong>
</p>


---


## 项目简介


AIpet 是一个面向 Windows 的丛雨桌宠。人格完全由提示词模拟，项目不再内置聊天 Transformer、LoRA、PyTorch 推理服务或模型下载脚本。


对话和视觉后端现在分别配置：


| 用途 | 服务商 | 默认模型 |
|---|---|---|
| 对话 | Ollama | `qwen3:14b` |
| 对话 | DeepSeek | `deepseek-v4-flash` |
| 对话 | 阿里云百炼 | `qwen-plus` |
| 对话 | OpenAI | `gpt-5.6-luna` |
| 视觉 | Ollama（本地） | `qwen2.5vl:7b` |
| 视觉 | 阿里云百炼 | `qwen3-vl-plus` |
| 视觉 | OpenAI | `gpt-5.6-luna` |


模型名都可以在设置窗口中修改。语言模型使用云端 API 时，视觉仍可独立选择本地 Ollama。

## macOS（适用于 Mac M 系列芯片）

适用于 Mac M 系列芯片的 macOS 适配版请前往[Releases 页面](../../releases)下载；从源码运行时，请在项目目录执行 `start_macos.command`。
