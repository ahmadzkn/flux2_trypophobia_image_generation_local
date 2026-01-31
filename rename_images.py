import os
import re

OUTPUT_DIR = "generated_images"

def rename_images():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Directory '{OUTPUT_DIR}' does not exist.")
        return

    # Get all files and sort them to ensure deterministic order (e.g., by creation time)
    # Filter for .png files
    files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith('.png')]
    
    # Sort files by creation time so the chronological generation order is preserved
    files.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)))
    
    print(f"Found {len(files)} images to rename.")
    
    count = 0
    for i, filename in enumerate(files):
        # User requested to KEEP existing name and prepend a number
        # Check if already numbered to prevent double numbering (optional, but good practice)
        # Pattern ^\d{5}_ matches our format
        if re.match(r'^\d{5}_', filename):
            print(f"Skipping {filename} (Already numbered)")
            continue
            
        new_name = f"{i+1:05d}_{filename}"
            
        old_path = os.path.join(OUTPUT_DIR, filename)
        new_path = os.path.join(OUTPUT_DIR, new_name)
        
        if old_path != new_path:
            # Handle collision if file already exists (unlikely in this direction but good practice)
            if os.path.exists(new_path):
                 print(f"Skipping {filename} -> {new_name} (Target exists)")
                 continue
                 
            os.rename(old_path, new_path)
            # print(f"Renamed: {filename} -> {new_name}")
            count += 1
            
    print(f"Successfully renamed {count} images in '{OUTPUT_DIR}'.")

if __name__ == "__main__":
    rename_images()
