#!/usr/bin/env python3
"""
Simple script to download specific GGUF models
"""

import os
from huggingface_hub import hf_hub_download

def download_model(repo_id: str, filename: str, local_dir: str = "./models"):
    os.makedirs(local_dir, exist_ok=True)
    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=local_dir,
        repo_type="model"
    )

if __name__ == "__main__":
    # Model configurations
    models = [
        {
            "repo_id": "wanhin/XiYanSQL-QwenCoder-7B-2504-gguf", 
            "filename": "xiyan-sqlcoder-7b-q4_k_m.gguf"
        }
    ]
    
    # Download both models
    for model in models:
        print(f"Downloading {model['filename']}...")
        download_model(model["repo_id"], model["filename"])
        print(f"Completed {model['filename']}") 