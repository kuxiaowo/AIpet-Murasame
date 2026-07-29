# 共享核心与平台适配层

AIpet 使用一套共享业务代码，并通过平台运行时隔离操作系统 API。
`aipet/platforms/macos` 提供 macOS 适配实现；是否随正式版本发布由维护者决定。

## 目录边界

- `aipet/core`：配置、AI/视觉后端、存储、下载、TTS/STT、缓存和工作线程。
- `aipet/ui`：跨平台 Qt 桌宠与设置窗口。
- `aipet/platforms/contracts.py`：所有平台必须遵守的接口。
- `aipet/platforms/windows`：Win32、DPAPI、CapsLock、进程和归档工具实现。
- `aipet/platforms/macos`：macOS 平台实现和使用说明。

共享目录不得直接使用 `sys.platform`、`os.name`、`ctypes`、Win32、Cocoa 或
Quartz。新平台能力必须先加入聚焦的契约，再由平台注册器提供实现。

## 平台运行时

`PlatformRuntime` 聚合以下策略：

| 策略 | 职责 |
|---|---|
| `PathPolicy` | 用户数据、缓存、下载目录和旧路径迁移 |
| `WindowIntegration` | Qt 窗口初始化、原生置顶与窗口生命周期 |
| `InputIntegration` | 用户空闲时间与全局语音快捷键 |
| `CredentialStore` | 安全保存和读取 AutoDL 密码 |
| `ProcessPolicy` | 子进程窗口、生命周期、日志查看器和 TTS Python |
| `ArchivePolicy` | 平台 TTS 引擎包与解压工具 |
| `AudioPolicy` | 平台音频设备筛选和排序 |

应用启动时通过 `get_platform_runtime()` 选择一次运行时。共享组件可以接收同一个
`PlatformRuntime`，不得自行选择具体平台实现。

## macOS 实现约束

macOS 贡献者应只修改 `aipet/platforms/macos`、macOS 原生资源、依赖和
打包脚本。当前适配包括：

1. 路径、空闲时间和音频设备策略；
2. Option+V 全局语音快捷键；
3. Keychain 凭据存储；
4. GPT-SoVITS 进程和本地运行时发现；
5. 全屏 Space 原生窗口行为；
6. Apple Silicon 应用包和 DMG 构建。

不得通过删除 Windows 行为、复制共享模块或在共享代码中加入平台分支完成适配。

## 导入路径

项目内部统一从 `aipet.core`、`aipet.ui` 和 `aipet.platforms` 导入。旧的
`tool`、`classes` 和根目录 `ui` 路径已经移除，禁止重新建立平行实现或兼容副本。
根目录 `main.py` 只保留薄启动入口。
