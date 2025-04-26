# Qwen2.5-VL OpenAI compatible API

Implementation of OpenAI Chat Completions API for Qwen2.5-VL on WSL2 Linux.

---

## 🌟 Key Features

### 🧑‍💻 OpenAI-Compatible API
- Drop-in replacement for the OpenAI Chat Completions API.
- Works with your favorite chat UIs and tools—no extra setup required.

### ⚡️ Streaming
- Get responses as they are generated, with no waiting for the full answer.
- Enjoy fluid, conversational AI that feels instant and interactive.

### 🖼️ Multiple images upload
- Supports uploading multiple images in a single request.

### 🚀 Function calling
- Supports calling functions defined in the request.

### 🔒 Privacy & Security Friendly
- Local deployment means your data stays with you.
- No cloud dependency—full control over your information and experience.

### 🤫 AWQ
- Supports both 7B and 32B AWQ models for consumer-grade inference.

### 🛠️ PowerShell
- PowerShell scripts for port forwarding and firewall rules.

---

## 🛠️ Installation

## create conda environment
```bash
conda env create --file environment.yml
```

## activate conda environment
```bash
conda activate autoawq
```

## install torch
```bash
pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## autoawq
```bash
pip install autoawq
pip install autoawq-kernels
```

## install transformers and accelerate
```bash
pip install git+https://github.com/huggingface/transformers accelerate
```

## install requirements
```bash
pip install -r requirements.txt
```

## run api
```bash
python api.py --port 9192 --size 32B
```

## test api
```bash
pytest test
```

## setup port forwarding on the windows host
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-portproxy.ps1
```

## test API from LAN
```powershell
Invoke-RestMethod -Uri "http://windows_host_ip:9192/v1/chat/completions" `
  -Method Post `
  -Headers @{"Content-Type" = "application/json"} `
  -Body '{
    "model": "Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
    "messages": [
      {
        "role": "user",
        "content": "What is the capital of France?"
      }
    ]
  }'
```

---

# ❌ Uninstall
```bash
conda deactivate
conda remove --name autoawq --all -y
conda clean --all -y
```

## remove port forwarding and firewall rules
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove-portproxy.ps1
```

---

# 🙏 Thanks

- [Qwen](https://github.com/QwenLM/Qwen2.5-VL)
- [Huggingface](https://huggingface.co/Qwen/Qwen2.5-VL-32B-Instruct-AWQ)
- [AutoAWQ](https://github.com/casper-hansen/AutoAWQ)

---

# 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
