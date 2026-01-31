import os
from huggingface_hub import snapshot_download, hf_hub_download

# Configuration
MODELS_DIR = "models"
REPO_ID = "black-forest-labs/FLUX.2-klein-9B"
GGUF_REPO_ID = "unsloth/FLUX.2-klein-9B-GGUF"
GGUF_FILENAME = "flux-2-klein-9b-Q4_K_M.gguf"

def download_model():
    print(f"--- Starting Download Process ---")
    print(f"Models will be saved in: {os.path.abspath(MODELS_DIR)}")
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(os.path.join(MODELS_DIR, "transformer"), exist_ok=True)
    
    # Step 1: Download base pipeline (for text encoder, VAE, etc.)
    print(f"\n[Step 1/2] Downloading base pipeline from {REPO_ID}")
    print("Note: This requires a Hugging Face token and approval for the gated repository.")
    
    local_dir = os.path.join(MODELS_DIR, "flux-2-klein-9b")
    
    path = snapshot_download(
        repo_id=REPO_ID,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        ignore_patterns=["*.safetensors", "*.bin"],  # Skip transformer weights (we use GGUF)
    )
    print(f"Base pipeline downloaded to: {path}")
    
    # Step 2: Download GGUF quantized transformer
    print(f"\n[Step 2/2] Downloading GGUF Q4_K_M transformer from {GGUF_REPO_ID}")
    print("This is a publicly available quantized version (~5.9GB)")
    
    gguf_local_path = os.path.join(MODELS_DIR, "transformer", GGUF_FILENAME)
    
    if os.path.exists(gguf_local_path):
        print(f"GGUF model already exists at: {gguf_local_path}")
    else:
        gguf_path = hf_hub_download(
            repo_id=GGUF_REPO_ID,
            filename=GGUF_FILENAME,
            local_dir=os.path.join(MODELS_DIR, "transformer"),
        )
        print(f"GGUF transformer downloaded to: {gguf_path}")
    
    print(f"\n--- Download Complete ---")
    print(f"Base pipeline: {local_dir}")
    print(f"GGUF transformer: {gguf_local_path}")
    print(f"\nYou can now run 'python generate.py'.")

if __name__ == "__main__":
    try:
        download_model()
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("\nIf you encounter a 401 Unauthorized or Repository Not Found error:")
        print("1. Ensure you have accepted the license at https://huggingface.co/black-forest-labs/FLUX.2-klein-9B")
        print("2. Run: huggingface-cli login")
