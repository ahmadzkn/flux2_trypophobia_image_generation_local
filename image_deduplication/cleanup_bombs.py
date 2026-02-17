import os
from PIL import Image
try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm is not installed
    def tqdm(iterable):
        return iterable

def cleanup_bombs(target_dir):
    """
    Identifies and deletes images that exceed the PIL DecompressionBomb threshold.
    Standard THRESHOLD = 89,478,485 pixels.
    """
    THRESHOLD = 89478485 
    
    # Temporarily allow loading very large images to check their dimensions
    Image.MAX_IMAGE_PIXELS = None 
    
    deleted_count = 0
    total_scanned = 0
    
    # Gather all potential image files
    files = []
    for dp, dn, filenames in os.walk(target_dir):
        for f in filenames:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff')):
                files.append(os.path.join(dp, f))
    
    print(f"Scanning {len(files)} files in '{target_dir}' for Decompression Bombs...")
    
    for f_path in tqdm(files):
        try:
            with Image.open(f_path) as img:
                w, h = img.size
                pixel_count = w * h
                
                if pixel_count > THRESHOLD:
                    # Explicitly close to release handle
                    img_size_str = f"{w}x{h}"
                    img.close() 
                    
                    os.remove(f_path)
                    print(f"\n[DELETED] {os.path.basename(f_path)} | Size: {img_size_str} | Pixels: {pixel_count:,}")
                    deleted_count += 1
            total_scanned += 1
        except Exception:
            # Skip errors (corrupt files, non-images already filtered by extension but just in case)
            continue
            
    print(f"\nScan Complete!")
    print(f"Total Scanned: {total_scanned}")
    print(f"Total Decompression Bombs REMOVED: {deleted_count}")

if __name__ == "__main__":
    # Target our main download folder
    download_folder = "downloaded"
    
    if os.path.exists(download_folder):
        cleanup_bombs(download_folder)
    else:
        # Fallback to current directory if 'downloaded' doesn't exist
        print(f"Directory '{download_folder}' not found. Checking local folder...")
        cleanup_bombs(".")
