from safetensors.torch import load_file
import os

model_path = "models/flux-2-klein-9b/transformer/diffusion_pytorch_model-00001-of-00002.safetensors"

if not os.path.exists(model_path):
    # Try finding any safetensors in that dir
    files = [f for f in os.listdir("models/flux-2-klein-9b/transformer") if f.endswith(".safetensors")]
    if files:
        model_path = os.path.join("models/flux-2-klein-9b/transformer", files[0])
    else:
        print("No safetensors found.")
        exit(1)

print(f"Inspecting {model_path}...")
try:
    state_dict = load_file(model_path)
    keys = list(state_dict.keys())
    print(f"Found {len(keys)} keys.")
    print("First 20 keys:")
    for k in keys[:20]:
        print(f" - {k}")
except Exception as e:
    print(f"Error: {e}")
