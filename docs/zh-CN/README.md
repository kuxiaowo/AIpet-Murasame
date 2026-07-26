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

## 主要改进

- Ollama / API 双模式，模型后端相互独立。
- 内置 DeepSeek、阿里云和 OpenAI 接口。
- 对话模型和视觉模型可以分别选择。
- 首次启动显示中英双语设置，语言可即时切换。
- 打开设置时会读取当前启用功能的模型列表；屏幕视觉关闭时，其配置整体禁用，也不会请求视觉后端。修改地址、服务商或密钥后可手动刷新，并始终允许直接输入模型 ID。
- 在界面中直接创建、导入或修改人格提示词。
- 模型只返回经过验证的中文、日语、情绪、`a`/`b` 立绘姿态和四种服装枚举，不会直接生成图层编号。
- 模型可根据语境在睡衣、粉白便衣、校服和紫色和服之间换装；服装、姿态与情绪仍由程序映射为固定图层，更换模型也不会随机“拆脸”。
- 中键拖到另一块显示器后，立绘会按新屏幕的可用高度自动缩放。
- 可在“显示”中打开实时诊断命令行，查看带关联 ID 的请求/响应 JSON、后台事件、警告和异常信息；日志按天保存在项目的 `logs/YYYY-MM-DD.log`。API 密钥会脱敏，大型 Base64 媒体只记录长度与 SHA-256 摘要。
- 截图只在 Qt 主线程产生并完整保留丛雨桌宠区域，网络分析放到后台；视觉模型会把画面里的丛雨识别为自己，同时忽略她自身的轻微动作对场景变化判断的干扰。
- 只有显著的屏幕变化会保存为有限、去重的结构化事件摘要，供后续对话参考；原始截图不会写入对话历史。
- 配置、API Key 和历史记录移出仓库目录。
- GPT-SoVITS 失败时仍然显示文本，不会吞掉整次回答。

## 快速开始

```bash
git clone https://github.com/kuxiaowo/AIpet-Murasame.git
cd AIpet-Murasame
conda env create -f environment.yml
conda activate aipet
python main.py
```

也可以手动创建环境：

```bash
conda create -n aipet python=3.10 -y
conda activate aipet
python -m pip install -r requirements.txt
python main.py
```

首次运行会打开 **AIpet 初始设置**。这里可以选择 Ollama / API、填写服务地址或 Key、选择模型、编辑人格并设置屏幕感知和语音。

如果使用 Ollama，可以先准备示例模型：

```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b
```

如果使用云端 API，也可以通过环境变量提供 Key：

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
$env:DASHSCOPE_API_KEY = "your-key"
$env:OPENAI_API_KEY = "your-key"
```

## 可视化设置

托盘菜单中的 **Settings… / 设置…** 可以随时打开设置。

启用语音输入后，可以分别选择 faster-whisper 模型或仓库 ID、模型下载目录和实际录音输入设备；选择“系统默认”时跟随 Windows 默认输入设备。Windows 上的新配置默认使用 `C:\AIpet\models` 下的独立 Whisper、GPT-SoVITS 和丛雨语音模型目录；已有的自定义路径不会被覆盖。下载和加载都严格使用填写的目录，下载进度、大小和当前文件直接显示在语音设置卡片中，关闭设置后下载仍会继续。

- **语言模型**：界面语言、后端模式、服务商、URL、对话模型、DeepSeek 思考模式、Ollama 上下文长度、超时和连接测试。
- **拓展功能 / 屏幕视觉**：独立选择本地 Ollama、阿里云或 OpenAI 视觉后端及模型。
- **Character**：用户名、默认立绘组、默认服装和人格提示词编辑器。
- **自动行为**：设置空闲提醒、历史长度和可持久化的勿扰模式，也可以在确认后立即清除对话及屏幕事件记忆。
- **显示**：选择显示器、立绘比例和实时日志窗口。

程序会自动添加结构化输出规则，所以人格提示词只需要描述身份、说话风格、关系和边界。

打开设置时会按已启用的功能加载模型列表：Ollama 调用 `GET /api/tags`，云端服务调用 OpenAI 兼容的 `GET /models`。屏幕视觉未启用时不会加载视觉模型列表。修改地址、服务商或 API Key 后，可以点击对应按钮重新测试和刷新。所有模型下拉框都可以直接编辑，因此模型列表接口失败、漏掉自定义模型或服务商未返回完整列表时，仍可手动填写。

DeepSeek 已更新为 V4 接口模型名：`deepseek-v4-flash` 和 `deepseek-v4-pro`。旧配置中的 `deepseek-chat`、`deepseek-reasoner` 会自动迁移，并可以在界面中切换思考模式。

## 数据与隐私

Windows 下的用户数据位于：

```text
%APPDATA%\AIpet-Murasame\
├── config.json
├── history.json
├── screen_memory.json
└── personality.txt
```

临时语音和截图仍位于 `%LOCALAPPDATA%\AIpet-Murasame\cache`；Whisper 和 TTS 的新下载位置由用户在设置页分别指定。屏幕感知默认关闭；启用后，截图只会发送给当前配置的视觉模型。程序最多保存最近 12 条显著屏幕事件摘要，并在对话中按字符预算注入最近最多 8 条；连续相同事件会去重，原始截图不会持久化。

通过设置窗口填写的 Key 会保存在用户配置中。如果希望进一步分离凭据，可以把 Key 字段留空并使用 `DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY` 环境变量。

## GPT-SoVITS 与语音输入

默认 TTS 地址为：

```text
http://127.0.0.1:9880/tts
```

六组参考音频统一放在角色语音模型目录内的 `reference_voices` 子目录中，因此只需填写角色语音模型目录。

本地地址启用 TTS 后，AIpet 会依次检查 GPT-SoVITS 引擎目录、丛雨 GPT/SoVITS 权重、六组参考音频和服务状态。两个现有路径框同时也是实际下载目标：引擎解压到 GPT-SoVITS 目录，角色权重和参考音频下载到角色语音模型目录；所需路径为空时会提示用户先选择，不再静默改用项目默认目录。未检测到 GPT-SoVITS 时，程序会读取 NVIDIA 显卡名称：GeForce RTX 50 系列下载专用整合包，其他显卡或无法识别时下载通用整合包。设置卡片会分别显示准备、校验、下载、解压、安装和清理阶段；解压优先使用开启多线程的原生 7-Zip，找不到时使用 Windows bsdtar，安装时通过同盘原子移动避免再次复制整个目录。所有自动下载均不会打开网页。角色权重来自 `LemonQu/Murasame_SoVITS`，参考音频来自 `kuxiaowo/Murasame-tts-reference-voice`。

首次发起本地 TTS 请求时，如果服务尚未运行，AIpet 会使用引擎自带的 Python 启动 `api_v2.py`，等待 OpenAPI 接口就绪，加载角色权重，再继续合成。设置页也可以手动启动或停止服务，并逐步显示定位环境、启动进程、等待接口和加载权重等状态。并发请求不会重复启动服务；退出程序时只关闭由本次 AIpet 进程启动的服务。AutoDL 云端模式由下方的托管 SSH 流程处理。

### AutoDL 云端 TTS

当前版本已经把旧版 README 中的 AutoDL 操作集成进设置页，不再需要手工编写 `.ssh/config`：

1. 启动已经配置好环境的 AutoDL 实例，在控制台复制登录命令，例如
   `ssh -p 12345 root@connect.example.com`。
2. 打开 **设置 → 拓展功能**，启用 TTS，并把 **TTS 位置**选为
   **AutoDL 云端**。
3. 粘贴登录命令和 SSH 密码。使用项目准备好的 AutoDL 镜像时，远程启动命令保持
   `bash -lc 'bash run.sh; bash'`。
4. 服务器参考音频目录默认保持 `/root/reference_voices`；如果镜像里的实际位置不同再修改。
   AIpet 会通过已经建立的 SFTP 会话读取服务器上的参考音频文件名和 `asr.txt`，
   因此 AutoDL 模式不需要下载任何本机 TTS 权重、引擎或参考音频。
5. 保存设置。首次需要合成语音时（或点击手动启动按钮），程序会自动登录 AutoDL、
   执行远程脚本，并把本机 `127.0.0.1:9880` 转发到实例内的 `9880` 端口。

密码不会出现在命令行或日志中，保存前会使用 Windows DPAPI 按当前 Windows 用户加密。
退出程序时只会关闭由 AIpet 创建的 SSH 会话和隧道。使用前仍需确保 AutoDL 实例已经开机、
本机 `9880` 端口未被占用，并且远端 `run.sh` 会在 `127.0.0.1:9880` 启动
GPT-SoVITS API；配置的服务器参考音频目录下还需保留六个情绪目录。

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
- 对话和视觉凭据分别配置；如果两者使用同一个云服务，可以在两个面板填写同一个 Key，或使用对应环境变量。
- HTTP 请求采用协作式取消：旧请求可能在后台结束，但结果会被丢弃，不会覆盖新对话。
- 角色立绘和语音素材的授权范围可能不同于源代码许可证。

## 许可证与素材声明

源代码使用 [GNU Affero General Public License v3.0](../../LICENSE)。

这是用于学习和技术交流的非官方同人项目。丛雨及随附的第三方立绘、语音等素材权利归包括 YUZUSOFT 在内的各自权利人所有，不因源代码使用 AGPL 而被重新许可。未经许可请勿商用相关素材。
