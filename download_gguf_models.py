#!/usr/bin/env python3
"""
Script to download GGUF quantized models from Hugging Face repository
"""

import os
from huggingface_hub import hf_hub_download, snapshot_download, list_repo_files
import argparse
from pathlib import Path
from tqdm import tqdm

def download_specific_model(repo_id: str, filename: str, local_dir: str = "./models"):
    """
    Download a specific GGUF model file from HF repository
    
    Args:
        repo_id: Hugging Face repository ID
        filename: Name of the GGUF file to download
        local_dir: Local directory to save the model
    """
    
    try:
        # Create local directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)
        
        print(f"📥 Downloading {filename} from {repo_id}...")
        
        # Download the specific file
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=local_dir,
            repo_type="model"
        )
        
        print(f"✅ Successfully downloaded {filename} to {file_path}")
        return file_path
        
    except Exception as e:
        print(f"❌ Failed to download {filename}: {e}")
        return None

def download_all_models(repo_id: str = "wanhin/XiYanSQL-QwenCoder-7B-2504-gguf", 
                       local_dir: str = "./models"):
    """
    Download all GGUF models from HF repository
    
    Args:
        repo_id: Hugging Face repository ID
        local_dir: Local directory to save the models
    """
    
    try:
        # Create local directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)
        
        print(f"📋 Listing files in repository {repo_id}...")
        
        # List all files in the repository
        repo_files = list_repo_files(repo_id, repo_type="model")
        
        # Filter for GGUF files
        gguf_files = [f for f in repo_files if f.endswith('.gguf')]
        
        if not gguf_files:
            print(f"❌ No GGUF files found in repository {repo_id}")
            return
        
        print(f"📁 Found {len(gguf_files)} GGUF files:")
        for file in gguf_files:
            print(f"  - {file}")
        
        # Download each GGUF file
        downloaded_files = []
        for filename in gguf_files:
            file_path = download_specific_model(repo_id, filename, local_dir)
            if file_path:
                downloaded_files.append(file_path)
        
        print(f"\n🎉 Successfully downloaded {len(downloaded_files)} files to {local_dir}")
        
        # Also download important metadata files if they exist
        metadata_files = ["README.md", "config.json", "tokenizer.json", "tokenizer_config.json"]
        for metadata_file in metadata_files:
            if metadata_file in repo_files:
                try:
                    hf_hub_download(
                        repo_id=repo_id,
                        filename=metadata_file,
                        local_dir=local_dir,
                        repo_type="model"
                    )
                    print(f"✅ Downloaded {metadata_file}")
                except Exception as e:
                    print(f"⚠️  Could not download {metadata_file}: {e}")
        
        return downloaded_files
        
    except Exception as e:
        print(f"❌ Failed to download models: {e}")
        return None

def list_available_models(repo_id: str = "wanhin/XiYanSQL-QwenCoder-7B-2504-gguf"):
    """
    List all available GGUF models in the repository
    
    Args:
        repo_id: Hugging Face repository ID
    """
    
    try:
        print(f"📋 Listing available models in {repo_id}...")
        
        # List all files in the repository
        repo_files = list_repo_files(repo_id, repo_type="model")
        
        # Filter for GGUF files
        gguf_files = [f for f in repo_files if f.endswith('.gguf')]
        
        if not gguf_files:
            print(f"❌ No GGUF files found in repository {repo_id}")
            return
        
        print(f"\n📁 Available GGUF models ({len(gguf_files)} files):")
        for i, file in enumerate(gguf_files, 1):
            print(f"  {i}. {file}")
        
        return gguf_files
        
    except Exception as e:
        print(f"❌ Failed to list models: {e}")
        return None

def download_with_progress(repo_id: str, local_dir: str = "./models"):
    """
    Download all models with progress tracking using snapshot_download
    
    Args:
        repo_id: Hugging Face repository ID
        local_dir: Local directory to save the models
    """
    
    try:
        print(f"📥 Downloading entire repository {repo_id}...")
        
        # Download the entire repository
        snapshot_path = snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            repo_type="model",
            allow_patterns="*.gguf"  # Only download GGUF files
        )
        
        print(f"✅ Successfully downloaded repository to {snapshot_path}")
        return snapshot_path
        
    except Exception as e:
        print(f"❌ Failed to download repository: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download GGUF models from Hugging Face")
    parser.add_argument("--repo_id", type=str, default="wanhin/XiYanSQL-QwenCoder-7B-2504-gguf",
                       help="Hugging Face repository ID")
    parser.add_argument("--local_dir", type=str, default="./models",
                       help="Local directory to save models")
    parser.add_argument("--list", action="store_true",
                       help="List available models without downloading")
    parser.add_argument("--filename", type=str,
                       help="Download specific model file by name")
    parser.add_argument("--all", action="store_true",
                       help="Download all GGUF models")
    parser.add_argument("--snapshot", action="store_true",
                       help="Download using snapshot (faster for multiple files)")
    
    args = parser.parse_args()
    
    if args.list:
        list_available_models(args.repo_id)
    elif args.filename:
        download_specific_model(args.repo_id, args.filename, args.local_dir)
    elif args.snapshot:
        download_with_progress(args.repo_id, args.local_dir)
    elif args.all:
        download_all_models(args.repo_id, args.local_dir)
    else:
        print("🤖 Interactive mode - Choose an option:")
        print("1. List available models")
        print("2. Download all models")
        print("3. Download specific model")
        print("4. Download with snapshot (recommended)")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            list_available_models(args.repo_id)
        elif choice == "2":
            download_all_models(args.repo_id, args.local_dir)
        elif choice == "3":
            models = list_available_models(args.repo_id)
            if models:
                try:
                    idx = int(input(f"\nEnter model number (1-{len(models)}): ")) - 1
                    if 0 <= idx < len(models):
                        download_specific_model(args.repo_id, models[idx], args.local_dir)
                    else:
                        print("❌ Invalid model number")
                except ValueError:
                    print("❌ Invalid input")
        elif choice == "4":
            download_with_progress(args.repo_id, args.local_dir)
        else:
            print("❌ Invalid choice") 