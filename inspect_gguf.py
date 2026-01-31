
import gguf
import sys

def inspect_gguf(path):
    print(f"Inspecting {path}...")
    try:
        reader = gguf.GGUFReader(path)
        print(f"Keys found: {len(reader.tensors)}")
        for tensor in reader.tensors:
            if "vector_in" in tensor.name or "time_in" in tensor.name:
                print(f" - {tensor.name} | Shape: {tensor.data.shape}")
            # Also print a few other keys to see the pattern
            if "img_in" in tensor.name or "txt_in" in tensor.name:
                print(f" - {tensor.name} | Shape: {tensor.data.shape}")

    except Exception as e:
        print(f"Error reading GGUF: {e}")

if __name__ == "__main__":
    inspect_gguf("models/transformer/flux-2-klein-9b-Q4_K_M.gguf")
