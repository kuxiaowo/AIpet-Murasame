# AIpet - Murasame AI Desktop Pet

# This project is for learning and communication only. All data used by this project belongs to YuzuSoft.
# This project is strictly prohibited from any commercial use.

## 📖 Project Introduction

An AI-based desktop pet application inspired by the character Murasame. This project references the original project [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet?tab=readme-ov-file), with partial rewrites and new features, and is open-sourced under the GPL-3.0 license requirements.
Speech synthesis: [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)
Speech recognition: [faster-whisper](https://github.com/SYSTRAN/faster-whisper)

## Latest Version News

#### 1.3.0 Voice conversation and idle voice.

## Project Links

- **Demo video**: [Murasame AI Desktop Pet - Let Murasame Stay by Your Side](https://www.bilibili.com/video/BV1oi4wzSEJJ)
- **Tutorial video**: [Murasame AI Desktop Pet V1.2.0 Deployment Tutorial](https://www.bilibili.com/video/BV1F6ykBwEDu)
- **Tutorial video**: [Murasame AI Desktop Pet V1.2.2 Deployment Tutorial](https://www.bilibili.com/video/BV1ghCMBjEKK)
- **Tutorial video**: [Murasame AI Desktop Pet V1.3.0 Deployment Tutorial](https://www.bilibili.com/video/BV1iw2XBREpd)


## 🚀 Quick Start
### Versions later than V1.2.2 support one-click deployment and launch
### Tutorial video [Murasame AI Desktop Pet V1.3.0 Deployment Tutorial](https://www.bilibili.com/video/BV1iw2XBREpd)


### Environment Preparation

### 1. Download the project files
Code > Download ZIP
After extraction, place the project in the path you want. Do not use special symbols in the path.

### 2. Install Ollama (optional)
##### Install this only if you need local conversations

The project supports API calls for DeepSeek and Qwen. You need to obtain your own key and fill it into `APIkey.json`.

Download and install Ollama from https://ollama.com/download
```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b # If local screen recognition is needed
```


### 3. Deploy GPT-SoVITS

##### 1 Local deployment
  https://github.com/RVC-Boss/GPT-SoVITS

  Download the integrated package for easier setup: https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4
  (I use GPT-SoVITS-v2pro-20250604-nvidia50. Choose according to your GPU compatibility.)

##### 2 Cloud deployment
  [AutoDL cloud computing](https://www.autodl.com/home)

  I use this platform. Student verification gives a pretty large discount.
  
  In the compute marketplace, choose the GPU and region. For the image, select a community image and choose "kuxiaowo/AIpet-Murasame/AIpet-Murasame_GPT-SoVITs", then create an instance.

  You can follow the tutorial to configure passwordless login: [AutoDL Help Documentation](https://www.autodl.com/docs/ssh/)
  In the console, open the container instance, then choose key login settings in the upper-right corner. Open cmd:
  ```bash
  ssh-keygen -t rsa
  ```
  Copy the entire public key from `user/.ssh/id_rsa.pub` (must be `.pub`!!! Never leak the private key!!!) into the SSH public key field.
  Start the instance and copy the SSH login command. (`ssh -p 12345 root@connect.cqa1.seetacloud.com`)
  Put the `.ssh/config` file from this project into your `user/.ssh/` directory and open it with Notepad
  ```
  Host aipet
    HostName Fill in the URL after root@
    Port Fill in the port after -p
    User root 
    IdentityFile ~/.ssh/id_rsa
    LocalForward 9880 localhost:9880
  ```
  Save


### 4. Get API keys

##### 1 DeepSeek
   https://platform.deepseek.com/usage
   Register or log in, recharge your account, then create a new API key
   (If you want cloud screen recognition, you must have a Qwen API key because only Qwen provides image recognition models.)

##### 2 Qwen series models (free quota available)
   [Alibaba Model Studio](https://bailian.console.aliyun.com/?spm=5176.29597918.J_SEsSjsNv72yRuRFS2VknO.2.49d77b08RWidjt&tab=model#/efm/model_experience_center/text)
   Register or log in. Open key management in the lower-left corner and create an API key. New users initially get 1 million free tokens for each model.

### 5. One-click launch
Run `run.py` with the default Python environment. (`python>=3.10`; if errors occur, try Python 3.10)
```bash
python run.py
```

If you need a virtual environment, create one with Python >= 3.10.
After activating the environment
```bash
conda activate AIpet_env  # Example; you can use another name
python run.py
```

--------------------------------------------------------------------------------------------------

<details>
  
<summary> ⚠️ V1.2.0 Notes (click to expand)</summary>

  ### V1.2.0 supports one-click deployment and launch
  ### [Tutorial video](https://www.bilibili.com/video/BV1vjeGzfE1w)
  ### Environment Preparation
  
  #### 1. Create a virtual environment
  Install Anaconda to configure the environment: [Anaconda official website](https://www.anaconda.com/download) (other virtual environments are also fine)
  
  
  #### 2. Install Ollama (optional)
  The project supports DeepSeek API calls. You need to obtain your own key and fill it into `APIkey.json`.
  Download and install Ollama from https://ollama.com/download
  ```bash
  ollama pull qwen3:14b
  ollama pull qwen2.5vl:7b # If screen recognition is needed
  ```
  ~~Note: locally, a fine-tuned qwen3-14b model previously had to run as the conversation model, while other auxiliary models could be handled by DeepSeek.~~
  
  V1.0.1 supports running all AI except speech synthesis on cloud DeepSeek. The corresponding `download.py` also checks the configuration file. If it is set to `"deepseek"`, it will not download the conversation model. If you want to run locally later, modify the configuration and download again.
  
  V1.1.0 supports screen recognition, only on the local qwen2.5vl model. You can toggle this option in the configuration file.
  
  
  #### 3. Deploy GPT-SoVITS
  https://github.com/RVC-Boss/GPT-SoVITS
  
  Download the integrated package for easier setup: https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4
  (I use GPT-SoVITS-v2pro-20250604-nvidia50. Choose according to your GPU compatibility.)
  ##### Configure model files
  Extract the downloaded project, then put the entire `GPT-SoVITS` folder into the `AIpet-Murasame` directory (alongside files and folders such as `tool` and `classes`)
  Rename `"GPT-SoVITS-...-......-......"` to `"GPT-SoVITS"`
  
  #### 4. One-click environment installation
  
  Directly run `env.bat`.
  ##### Manual installation
  1. Create a conda environment
  ```bash
  conda create -n AIpet_env python=3.10
  ```
  2. Install dependencies
  ```bash
  conda activate AIpet_env  # Activate the environment
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130   # PyTorch is not needed if models do not run locally
  cd /d Your project path
  pip -r requirements.txt   # Install dependencies
  python download.py   # Download models
  ```
  ### Start Running
  
  #### Directly run `start_ai_pet.bat`
  
  #### Manual launch
  1. Start the desktop pet itself (from the project directory)
  ```bash
  conda activate AIpet_env
  python main.py
  ```
  2. Start TTS
  ```bash
  cd /d Project path/GPT-SoVITS
  "Project path/GPT-SoVITS/runtime/python.exe" api_v2.py
  ```
  
  3. Start interacting

  ### Configuration File
  ``` json
  {
    "local_api": {              # Local API ports. Change the address yourself if deployed remotely
      "ollama": "http://localhost:28565/ollama",
      "qwen3_lora": "http://localhost:28565/qwen3-lora",
      "gpt_sovits_tts": "http://localhost:28565/tts",
      "deepseek_api": "http://localhost:28565/deepseekAPI"
    },
    "portrait": "a",            # Portrait mode. Can be changed to b
    "user_name": "Kuxw",        # User name
    "model_type": "deepseek",   # Model type. local means local model
    "screen_type": "false",     # Screen recognition toggle
  }
  ```

</details>

--------------------------------------------------------------------------------------------------

### During Use
Click the lower half of Murasame to enter text. Hold the mouse middle button to adjust her position. Long-press and hold Murasame's head, then move left or right to pat her head...

### Configuration File
``` json
{
  "local_api": {              # Local API ports. Change the address yourself if API forwarding is deployed remotely
    "ollama": "http://localhost:28565/ollama",
    "qwen3_lora": "http://localhost:28565/qwen3-lora",
    "gpt_sovits_tts": "http://localhost:28565/tts",
    "deepseek_api": "http://localhost:28565/deepseekAPI"
  },
  "portrait": "a",            # Portrait mode. Can be changed to b
  "user_name": "Kuxw",        # User name
  "model_type": "deepseek",   # Model type. local means local model, qwen means Qwen series model, deepseek means DeepSeek model. Screen recognition uses Qwen by default, so Qwen is recommended
  "tts_type": "local",        # Speech synthesis. local means local model, cloud means cloud model
  "screen_type": "false",     # Screen recognition toggle. false disables it, true enables it
  "voice_trigger": "false",   # Speech recognition toggle
  "stt_model": "large-v3",    # Speech recognition model. See the original project for details
  "screen_interval": 300,     # Screenshot interval in seconds
  "DEFAULT_PORTRAIT_SCREEN_RATIO": 0.8,    # Maximum ratio of desktop pet height to screen height
  "screen_index": 0,          # Which screen the desktop pet runs on and screenshots are taken from
  "idle_thinking_minutes": 1, # Threshold for short idle-away detection
  "idle_away_minutes": 2      # Threshold for long idle-away detection
}
```

### ⭐ If you find this useful, please give it a Star!


## 💬 Q&A

### 1️⃣ GPU unavailable  
> **Problem:** You have a GPU, but TTS shows  
> `Warning: CUDA is not available, set device to CPU.`  
> **Solution:** Try updating the GPU driver and make sure CUDA matches PyTorch.  

---

### 2️⃣ SoVITS responds slowly  
> **Problem:** SoVITS responds, but it is extremely slow.  
> **Solution:** Download the version that matches your GPU:  
> -  50 series: use the **dedicated version**  
> -  40 series and earlier: use the **general version**

---

### 3️⃣ Conda activation error  
> **Problem:** `CondaError: Run 'conda init' before 'conda activate'`  
> **Solution:**  
> - Miniconda is recommended instead of the full version;  
> - Or manually run this in the command line:  
>   ```bash
>   conda init
>   ```

---

### 4️⃣ API Key error  
![Q&A4](https://github.com/kuxiaowo/AIpet-Murasame/blob/resource/readme_resource/qa4.png) 
> **Problem:** On startup, as shown in the image, the API cannot be used.  
> **Solution:**  
> - Check whether the **API key is valid and whether the account balance is sufficient**;  
> - If it is a file encoding problem, resave the file with **ANSI encoding**.

---

### 5️⃣ `start_ai_pet.bat` exits immediately  (V1.2.0)
> **Problem:** After double-clicking the startup script, the window closes immediately.  
> **Solution:**  
> - Make sure the path contains **no special symbols or spaces**.  
>   (For example, avoid Chinese characters, parentheses, exclamation marks, and similar characters)

---

### 6️⃣ Script garbled text or immediate exit  (V1.2.0)
> **Problem:** `env.bat` or `start_ai_pet.bat` shows garbled text or cannot run.  
> **Solution:**  
> - Resave it with **ANSI encoding**.  

---

## Development Tasks

| Status | Task |
|:--:|:--|
| ✅ | Long-term memory feature |
| ✅ | Write desktop pet display size into the configuration file |
| ✅ | Add Q&A support and resolve some common issues |
| ✅ | One-click Python script startup with better compatibility and optimized dependencies (avoiding forced PyTorch downloads) |
| ✅ | Change clothes |
|  | Complete and improve logging |
|  | Check the "always-on-top logic" to ensure the window always stays on top during games |
| ✅ | Try deploying TTS to Alibaba Cloud |
| ✅ | Switch all models to the Qwen series |
