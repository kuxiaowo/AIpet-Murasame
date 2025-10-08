# AIpet - 丛雨AI桌宠

# 本项目仅供学习交流使用，所使用的所有数据均归YuzuSoft所有
# 本项目严格禁止用于任何商业用途

## 📖 项目简介

一个基于AI的桌面宠物应用，灵感来自丛雨角色。本项目参考了原项目MurasamePet，进行部分重构和重写，并根据GPL-3.0许可证要求进行开源。


## 🔗 原项目指路

- **GitHub 项目**: [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet?tab=readme-ov-file)
- **演示视频**: [Bilibili 视频](https://www.bilibili.com/video/BV1vjeGzfE1w)

## 🚀 快速开始

### 环境准备

#### 1. 创建虚拟环境
安装anaconda配置环境[anaconda官网](https://www.anaconda.com/download)（如果你用其他的虚拟环境也可以）
```bash
# 使用 conda 创建虚拟环境
conda create -n aipet_env python=3.13
conda activate aipet_env

# 进入项目目录
cd /d 项目路径

# 安装依赖
pip install -r requirements.txt
```
Pytorch根据cuda版本自己安装：https://pytorch.org/get-started/locally/

#### 2. 安装Ollama（可选）
项目里支持deepseek的API调用，需要自己获取并填入APIkey.json
在 https://ollama.com/download 下载 Ollama 并安装
```bash
ollama pull qwen3:14b
```
~~（注意：本地必须跑一个微调的qwen3-14b模型作为对话模型，其他辅助模型可由deepseek担任）~~

V1.0.1版本支持除了语音合成，全部AI跑在云端deepseek，相应的download.py也会检查配置文件，若是"deepseek"则不会下载对话模型，想要后面跑在本地的需要修改配置后再下载一次

#### 3. 下载微调模型
```bash
python ./download.py
```

#### 4. 部署 GPT-SoVITS
https://github.com/RVC-Boss/GPT-SoVITS

这里建议下载整合包，更方便，但体积也更大：https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4
（我用的GPT-SoVITS-v2pro-20250604-nvidia50，你们看显卡兼容）
##### 配置模型文件
将刚刚下好的模型中./models/Murasame_SoVITS中的.ckpt、.pth文件分别放入整合包中的GPT_weights、SoVITS_weights文件夹
并修改\整合包\GPT_SoVITS\configs\tts_infer.yaml配置文件，将custom中t2s_weights_path、vits_weights_path都改成刚刚拷进去的模型文件的地址，注意斜杠方向

### 开始运行

#### 1. 启动 GPT-SoVITS 服务
在正常环境中运行：
```bash
"你的地址\GPT-SoVITS-v2pro-20250604-nvidia50\GPT-SoVITS-v2pro-20250604-nvidia50\runtime\python.exe" api_v2.py
```
前面是指定整合包python解释器
注意，api_v2.py 为 GPT-SoVITS Repository 中的文件 [GPT-SoVITS 官方仓库](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/api_v2.py)

#### 2. 运行本地API
```bash
conda activate aipet_env

python ./api.py
```
#### 3. 运行主程序
```bash
python ./main.py
```

### 过程中
点击丛雨下半部分可以输入内容，鼠标中建按住可以调整位置，长按鼠标按住丛雨的头部并左右移动可以摸头……

#### （注意：程序默认采用deepseek接口，要使用本地算力请将config.json中的model_type改为"local"
#### 倘若远程部署，则需要将config.json中local_api修改成自己的端口
#### 用户名字也可以改，查看config.json
