# Flux 2 Klein 9B - RTX 5080 / Blackwell Image Generation

This project enables running the **Flux 2 Klein 9B** image generation model on NVIDIA **RTX 5080 (Blackwell)** GPUs, overcoming initial CUDA compatibility issues and optimizing for 16GB VRAM using GGUF quantization.

## Features
- **RTX 5080 Support**: Configured with PyTorch nightly (CUDA 12.8) for full Blackwell architecture compatibility (`sm_120`).
- **Quantization**: Uses GGUF Q4_K_M quantization to reduce model size from ~18GB to **5.9GB**, allowing it to fit comfortably in 16GB VRAM.
- **High Performance**: ~9 seconds per image with 4 inference steps.
- **Auto-Generation**: Scripted batch generation with prompt templating.

## Hardware Requirements
- **GPU**: NVIDIA RTX 50-series (Blackwell) with at least 8GB VRAM (16GB recommended).
- **RAM**: 16GB+ recommended.
- **Disk Space**: ~25GB for models and dependencies.

## Installation

### 1. Setup Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install PyTorch Nightly
RTX 5080 requires CUDA 12.8 support, found in PyTorch nightly:
```bash
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

### 3. Install Requirements
```bash
pip install -r requirements.txt
```

## Usage

### 1. Download Models
Run the download script to fetch the base pipeline and the quantized GGUF transformer:
```bash
python download.py
```
*Note: You may need to log in to Hugging Face (`huggingface-cli login`) and accept the license for `black-forest-labs/FLUX.2-klein-9B`.*

### 2. Generate Images
Run the generation script:
```bash
python generate.py
```
Generated images will be saved in the `generated_images/` folder.

## Technical Details
- **Quantization**: GGUF Q4_K_M (via `diffusers` + `gguf` library).
- **Backend**: PyTorch 2.6+ with CUDA 12.8 nightly.
- **Speed**: ~1.25s per iteration on RTX 5080.

## License
This project uses models from Black Forest Labs and Unsloth. Please check their respective licenses on Hugging Face.
