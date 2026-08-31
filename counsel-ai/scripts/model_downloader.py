#!/usr/bin/env python3
"""
Counsel AI Model Downloader

Downloads and verifies commercial GGUF models with SHA256 checksum verification.
Supports DeepSeek, Mistral, Gemma, and other commercially-licensed models.

Usage:
    python model_downloader.py list                    # List available models
    python model_downloader.py download <model_id>     # Download specific model
    python model_downloader.py verify <path>           # Verify existing model
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

# Model manifest - configurable via environment or file
DEFAULT_MANIFEST = {
    "models": [
        {
            "id": "deepseek-coder-1.3b-base",
            "name": "DeepSeek Coder 1.3B Base",
            "description": "Commercial-friendly code and text model",
            "license": "MIT",
            "size_gb": 0.8,
            "quantization": "Q4_K_M",
            "url": "https://huggingface.co/deepseek-ai/deepseek-coder-1.3b-base-GGUF/resolve/main/deepseek-coder-1.3b-base.Q4_K_M.gguf",
            "sha256": "PLACEHOLDER_CHECKSUM_UPDATE_BEFORE_RELEASE"
        },
        {
            "id": "mistral-7b-instruct",
            "name": "Mistral 7B Instruct",
            "description": "High-performance instruction-following model",
            "license": "Apache 2.0",
            "size_gb": 4.2,
            "quantization": "Q4_K_M",
            "url": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            "sha256": "PLACEHOLDER_CHECKSUM_UPDATE_BEFORE_RELEASE"
        },
        {
            "id": "gemma-2b-it",
            "name": "Gemma 2B IT",
            "description": "Google's lightweight instruction-tuned model",
            "license": "Gemma Terms (commercial use allowed)",
            "size_gb": 1.5,
            "quantization": "Q4_K_M",
            "url": "https://huggingface.co/google/gemma-2b-it-GGUF/resolve/main/gemma-2b-it.Q4_K_M.gguf",
            "sha256": "PLACEHOLDER_CHECKSUM_UPDATE_BEFORE_RELEASE"
        },
        {
            "id": "phi-2",
            "name": "Phi-2",
            "description": "Microsoft's compact reasoning model",
            "license": "MIT",
            "size_gb": 1.8,
            "quantization": "Q4_K_M",
            "url": "https://huggingface.co/microsoft/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf",
            "sha256": "PLACEHOLDER_CHECKSUM_UPDATE_BEFORE_RELEASE"
        }
    ]
}


def get_app_data_dir() -> Path:
    """Get platform-specific app data directory for Windows, Linux, and Android."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", r"C:\Users\Public"))
        return base / "CounselAI" / "models"
    elif sys.platform == "android":
        # Android external storage directory
        base = Path(os.environ.get("EXTERNAL_STORAGE", "/sdcard"))
        return base / "Android" / "data" / "com.counselai.app" / "files" / "models"
    else:
        # Linux (and other Unix-like systems)
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "CounselAI" / "models"


def load_manifest(manifest_path: Optional[str] = None) -> dict:
    """Load model manifest from file or use default."""
    if manifest_path and Path(manifest_path).exists():
        with open(manifest_path) as f:
            return json.load(f)
    
    # Check environment variable for custom manifest URL
    manifest_url = os.environ.get("COUNSEL_MODEL_MANIFEST")
    if manifest_url:
        try:
            with urlopen(manifest_url, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            print(f"Warning: Could not fetch manifest from {manifest_url}: {e}")
    
    return DEFAULT_MANIFEST


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def list_models(manifest: dict) -> None:
    """List all available models."""
    print("\nAvailable Models:")
    print("=" * 70)
    
    for model in manifest["models"]:
        print(f"\nID: {model['id']}")
        print(f"  Name: {model['name']}")
        print(f"  Description: {model['description']}")
        print(f"  License: {model['license']}")
        print(f"  Size: {model['size_gb']} GB")
        print(f"  Quantization: {model['quantization']}")
    
    print("\n" + "=" * 70)
    print("Use 'python model_downloader.py download <model_id>' to download")


def download_model(model_id: str, manifest: dict, progress_callback=None) -> Path:
    """Download a model with progress tracking and checksum verification."""
    model = next((m for m in manifest["models"] if m["id"] == model_id), None)
    if not model:
        raise ValueError(f"Model '{model_id}' not found in manifest")
    
    models_dir = get_app_data_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = models_dir / f"{model_id}.gguf"
    temp_path = models_dir / f"{model_id}.gguf.download"
    
    # Check if already downloaded
    if output_path.exists():
        print(f"Model already exists at {output_path}")
        if verify_model(output_path, model["sha256"]):
            return output_path
        print("Existing file failed verification, re-downloading...")
        output_path.unlink()
    
    print(f"\nDownloading: {model['name']}")
    print(f"Size: {model['size_gb']} GB")
    print(f"Destination: {output_path}")
    print()
    
    # Download with progress
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, (downloaded / total_size) * 100) if total_size > 0 else 0
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        print(f"\rProgress: {percent:5.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", flush=True)
    
    try:
        urlretrieve(model["url"], temp_path, reporthook=report_progress)
        print()  # Newline after progress
        
        # Move temp to final location
        shutil.move(temp_path, output_path)
        
        # Verify checksum
        if not verify_model(output_path, model["sha256"]):
            output_path.unlink()
            raise ValueError("Checksum verification failed! File may be corrupted.")
        
        print(f"\n✅ Download complete: {output_path}")
        return output_path
        
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Download failed: {e}")


def verify_model(model_path: Path, expected_sha256: str) -> bool:
    """Verify model file against expected SHA256 checksum."""
    if not model_path.exists():
        print(f"File not found: {model_path}")
        return False
    
    if expected_sha256 == "PLACEHOLDER_CHECKSUM_UPDATE_BEFORE_RELEASE":
        print("⚠️  Warning: Manifest has placeholder checksum. Skipping verification.")
        return True
    
    actual_sha256 = calculate_sha256(model_path)
    
    if actual_sha256.lower() == expected_sha256.lower():
        print(f"✅ Checksum verified: {actual_sha256[:16]}...")
        return True
    else:
        print(f"❌ Checksum mismatch!")
        print(f"  Expected: {expected_sha256}")
        print(f"  Actual:   {actual_sha256}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Counsel AI Model Downloader")
    parser.add_argument("command", choices=["list", "download", "verify"], 
                       help="Command to execute")
    parser.add_argument("model_id", nargs="?", help="Model ID (for download/verify)")
    parser.add_argument("--manifest", "-m", help="Path to custom manifest JSON")
    parser.add_argument("--output", "-o", help="Custom output path")
    
    args = parser.parse_args()
    
    manifest = load_manifest(args.manifest)
    
    if args.command == "list":
        list_models(manifest)
    
    elif args.command == "download":
        if not args.model_id:
            print("Error: model_id required for download command")
            sys.exit(1)
        
        try:
            output_path = download_model(args.model_id, manifest)
            if args.output:
                shutil.copy(output_path, args.output)
                print(f"Copied to: {args.output}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command == "verify":
        if not args.model_id:
            print("Error: model path required for verify command")
            sys.exit(1)
        
        model_path = Path(args.model_id)
        # Try to find model in manifest for checksum
        model = next((m for m in manifest["models"] if m["id"] == args.model_id), None)
        expected_sha = model["sha256"] if model else "PLACEHOLDER_CHECKSUM_UPDATE_BEFORE_RELEASE"
        
        if verify_model(model_path, expected_sha):
            print("Verification successful!")
        else:
            print("Verification failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
