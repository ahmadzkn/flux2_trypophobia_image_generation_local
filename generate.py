import torch
from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel, GGUFQuantizationConfig
import os
import random
import time
import shutil
import re

# Workaround for RTX 5080 (Blackwell) with PyTorch 2.6+cu124:
# Disable optimized kernels that cause "no kernel image is available"
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
torch.backends.cuda.enable_math_sdp(True)

# Configuration
MODELS_DIR = "models"
MODEL_ID = "black-forest-labs/FLUX.2-klein-9B"
LOCAL_MODEL_PATH = os.path.join(MODELS_DIR, "flux-2-klein-9b")
OUTPUT_DIR = "generated_images"

# --- USER CONFIGURATION ---
NUM_IMAGES = 10
CLEAN_OUTPUT_DIR = False  # Set to True to clear generated_images folder before running
KEYWORDS_FILE = "keywords_trypophobia.md" # Change to "keywords_futuristic.md" or other files
# --------------------------

# Create or clean output directory
if CLEAN_OUTPUT_DIR and os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_config_from_file(filename):
    """Loads keywords and templates from a markdown file."""
    keywords = []
    templates = []
    current_section = None
    
    try:
        if not os.path.exists(filename):
            print(f"Warning: Keyword file '{filename}' not found.")
            return [], []

        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("## Templates"):
                    current_section = "templates"
                    continue
                elif line.startswith("## Categories") or line.startswith("## "):
                    current_section = "keywords"
                    continue
                
                if current_section == "templates":
                    if line.startswith("- "):
                        # Extract template string, handling quotes
                        tmpl = line[2:].strip()
                        if tmpl.startswith('"') and tmpl.endswith('"'):
                            tmpl = tmpl[1:-1]
                        if "{keyword}" in tmpl:
                            templates.append(tmpl)
                            
                elif current_section == "keywords":
                    if line.startswith("- **") or line.startswith("- "):
                        # Extract keywords
                        kw_part = line.split(":", 1)[-1] if ":" in line else line.replace("-", "")
                        kw_list = [k.strip() for k in kw_part.split(",")]
                        keywords.extend([k for k in kw_list if k])
                        
    except Exception as e:
        print(f"Error loading config from {filename}: {e}")
        
    return list(set(keywords)), templates

def generate_images(num_images=5):
    print(f"\n--- Loading Configuration ---")
    print(f"Using keywords file: {KEYWORDS_FILE}")
    
    keywords, templates = load_config_from_file(KEYWORDS_FILE)
    
    if not keywords:
        print("No keywords found. Using fallback.")
        keywords = ["lotus pods", "beehive", "bubbly skin texture"]
    
    if not templates:
        print("No templates found in file. Using default macro template.")
        templates = ["Macro photography of {keyword}, extremely detailed, porous texture, clustered holes, organic patterns, 8k, hyper-realistic."]

    print(f"Loaded {len(keywords)} keywords and {len(templates)} display templates.")
    print(f"Target: {num_images} images")
    
    # Check if we should use local path or model ID (if local download exists)
    model_path_to_use = LOCAL_MODEL_PATH if os.path.exists(LOCAL_MODEL_PATH) else MODEL_ID
    
    print(f"Status: Loading model components from {model_path_to_use}...")
    print(f"Status: Loading model components from {model_path_to_use}...")
    print("Optimization: Loading GGUF Q4_K_M quantized model (5.9GB) for 16GB VRAM.")
    start_time = time.time()
    
    # GGUF uses pre-quantized weights with dynamic dequantization
    # No special CUDA kernels needed - works on any GPU including RTX 5080 Blackwell
    
    try:
        # Use local Q4_K_M GGUF file (5.9GB - fits easily in 16GB VRAM)
        gguf_path = "models/transformer/flux-2-klein-9b-Q4_K_M.gguf"
        
        print(f"Loading GGUF transformer from: {gguf_path}")
        transformer = Flux2Transformer2DModel.from_single_file(
            gguf_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
            config=model_path_to_use,
            subfolder="transformer",
            torch_dtype=torch.bfloat16,
        )
        
        # Load the rest of the pipeline with the quantized transformer
        pipe = Flux2KleinPipeline.from_pretrained(
            model_path_to_use,
            transformer=transformer,
            torch_dtype=torch.bfloat16,
        )
        
        pipe.enable_model_cpu_offload()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nError loading pipeline: {e}")
        return

    print(f"Status: Pipeline loaded in {time.time() - start_time:.2f}s")
    
    # Determine start index for sequential numbering
    current_sequence = 1
    if os.path.exists(OUTPUT_DIR) and not CLEAN_OUTPUT_DIR:
        # Check existing files for highest sequence number
        existing_files = os.listdir(OUTPUT_DIR)
        max_seq = 0
        for f in existing_files:
            # Look for patterns starting with 5 digits followed by underscore
            match = re.match(r'^(\d{5})_', f)
            if match:
                try:
                    seq_num = int(match.group(1))
                    if seq_num > max_seq:
                        max_seq = seq_num
                except ValueError:
                    pass
        current_sequence = max_seq + 1
        print(f"Resuming sequence from index: {current_sequence}")

    for i in range(num_images):
        keyword = random.choice(keywords)
        template = random.choice(templates)
        
        # Clean up keyword if it has markdown syntax or quotes
        clean_keyword = keyword.replace("**", "").replace('"', '').replace("'", "").strip(" .,")
        
        prompt = template.format(keyword=clean_keyword)
        
        print(f"\n[Image {i+1}/{num_images}] Sequence: {current_sequence:05d} | Keyword: {clean_keyword}")
        print(f"Prompt: {prompt}")
        
        gen_start = time.time()
        
        try:
            image = pipe(
                prompt=prompt,
                num_inference_steps=4, # FLUX.2 Klein optimization
                guidance_scale=3.5, # Guidance scale might be different for distilled models, typically 3.5 is okay
                width=512, 
                height=512,
            ).images[0]
            
            # Sanitize filename
            safe_keyword = "".join([c for c in clean_keyword if c.isalnum() or c in (' ', '_')]).rstrip()
            # Filename format: {seq}_{timestamp}_{keyword}.png
            filename = f"{OUTPUT_DIR}/{current_sequence:05d}_img_{int(time.time())}_{safe_keyword.replace(' ', '_')[:20]}.png"
            image.save(filename)
            
            print(f"Status: Image generated and saved in {time.time() - gen_start:.2f}s")
            print(f"Saved to: {filename}")
            
            current_sequence += 1
            
        except Exception as e:
            print(f"Error generating image: {e}")

    print(f"\n--- Generation Complete ---")
    print(f"All images are saved in the '{OUTPUT_DIR}' folder.")

if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("CUDA is not available. Please check your GPU/drivers.")
    else:
        generate_images(num_images=NUM_IMAGES)
