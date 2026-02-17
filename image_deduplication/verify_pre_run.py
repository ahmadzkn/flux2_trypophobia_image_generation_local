import os
from PIL import Image, ImageDraw

def create_test_images(base_dir):
    os.makedirs(base_dir, exist_ok=True)
    
    # 1. Base Image
    img = Image.new('RGB', (500, 500), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((10,10), "Test Image 1", fill=(255,255,0))
    img.save(os.path.join(base_dir, "img1.jpg"))
    
    # 2. Exact Duplicate
    img.save(os.path.join(base_dir, "img1_copy.jpg"))
    
    # 3. Resized Version (Should be caught by pHash)
    img_small = img.resize((100, 100))
    img_small.save(os.path.join(base_dir, "img1_small.jpg"))
    
    # 4. Unique Image
    img2 = Image.new('RGB', (500, 500), color=(137, 73, 109))
    d2 = ImageDraw.Draw(img2)
    d2.text((10,10), "Unique Image", fill=(255,255,0))
    img2.save(os.path.join(base_dir, "img2.jpg"))

    print(f"Test images created in {base_dir}")

if __name__ == "__main__":
    test_path = r"c:\Data\code\ag\flux2\image_deduplication\test_images"
    create_test_images(test_path)
