# Install

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

Edit `scripts\setup-portproxy.ps1` to set the desired port number (default is 9192)
```
param(
    [int]$Port = 9192
)
```

Run the script:
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

# Uninstall
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
