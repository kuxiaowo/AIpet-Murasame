# AIpet - 丛雨AI桌宠

# 本项目仅供学习交流使用，所使用的所有数据均归YuzuSoft所有
# 本项目严格禁止用于任何商业用途

## 📖 项目简介

一个基于AI的桌面宠物应用，灵感来自丛雨角色。本项目参考了原项目MurasamePet，进行部分重构和重写，并根据GPL-3.0许可证要求进行开源。


## 🔗 原项目指路

- **GitHub 项目**: [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet?tab=readme-ov-file)
- **演示视频**: [Bilibili 视频](https://www.bilibili.com/video/BV1vjeGzfE1w)

## 🚀 快速开始
### V1.2.0版本支持一键部署与运行
### 环境准备

#### 1. 创建虚拟环境
安装anaconda配置环境[anaconda官网](https://www.anaconda.com/download)（如果你用其他的虚拟环境也可以）

执行env.bat自动创建环境


#### 2. 安装Ollama（可选）
项目里支持deepseek的API调用，需要自己获取并填入APIkey.json
在 https://ollama.com/download 下载 Ollama 并安装
```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b #如果需要屏幕识别
```
~~（注意：本地必须跑一个微调的qwen3-14b模型作为对话模型，其他辅助模型可由deepseek担任）~~

V1.0.1版本支持除了语音合成，全部AI跑在云端deepseek，相应的download.py也会检查配置文件，若是"deepseek"则不会下载对话模型，想要后面跑在本地的需要修改配置后再下载一次

V1.1.0版本支持屏幕识别，只支持跑在本地qwen2.5vl模型上，可以在配置文件设置此选项的开关


#### 3. 部署 GPT-SoVITS
https://github.com/RVC-Boss/GPT-SoVITS

下载整合包，更方便：https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4
（我用的GPT-SoVITS-v2pro-20250604-nvidia50，你们看显卡兼容）
##### 配置模型文件
将刚刚下好的项目解压，将其中整个GPT-Sovits文件夹放入AIpet-Murasame目录下（与tool和classes这些文件并列）

### 开始运行

#### 直接执行start_ai_pet.bat

### 过程中
点击丛雨下半部分可以输入内容，鼠标中建按住可以调整位置，长按鼠标按住丛雨的头部并左右移动可以摸头……

### 配置文件
``` json
{
  "local_api": {              #本地api端口，如果远程部署自己改地址
    "ollama": "http://localhost:28565/ollama",
    "qwen3_lora": "http://localhost:28565/qwen3-lora",
    "gpt_sovits_tts": "http://localhost:28565/tts",
    "deepseek_api": "http://localhost:28565/deepseekAPI"
  },
  "portrait": "a",            #立绘模式，可以改为b
  "user_name": "Kuxw",        #用户名字
  "model_type": "deepseek",   #模型类型，local为本地模型
  "screen_type": "false"      #屏幕识别开关
}
```

If you like, i want a little star.
