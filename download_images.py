import json
import os
import time
import random
import requests
import argparse
from pathlib import Path
from urllib.parse import urlparse
from tqdm import tqdm
from PIL import Image

# Configuration
DEFAULT_JSONL_FILE = "subreddit_json/r_trypophobia_posts_2014.jsonl"
DOWNLOAD_DIR = "downloaded"
BASE_DELAY = 1.5  # Minimum seconds to wait between each download
JITTER_MAX = 1.5  # Maximum additional random delay
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Create a session for connection pooling
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# Global stats for reporting
stats = {
    "downloaded": 0,
    "skipped": 0,
    "failed": 0,
    "total_images": 0
}

def setup():
    """Create the download directory if it doesn't exist."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        print(f"Created directory: {DOWNLOAD_DIR}")

def get_total_count(jsonl_path):
    """Rapidly count lines in the JSONL file."""
    if not os.path.exists(jsonl_path):
        return 0
    count = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count

def get_extension(url):
    """Extract file extension from URL or default to .jpg."""
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    if not ext:
        return ".jpg"
    return ext.split('?')[0]

def download_image(url, filename, pbar=None):
    """Download an image with retries and exponential backoff."""
    # Skip GIF and GIFV files
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".gif", ".gifv"]:
        return False

    if os.path.exists(filename):
        stats["skipped"] += 1
        return True

    retries = 0
    max_retries = 3
    backoff = 30  # Initial wait time for 429 in seconds

    while retries <= max_retries:
        try:
            response = session.get(url, timeout=20)
            
            if response.status_code == 429:
                if pbar: pbar.set_postfix_str(f"Rate limited! Backing off {backoff}s")
                time.sleep(backoff)
                retries += 1
                backoff *= 2
                continue
                
            response.raise_for_status()
            
            with open(filename, "wb") as f:
                f.write(response.content)
            
            # Post-download check for compression bombs
            try:
                with Image.open(filename) as img:
                    img.verify()
            except Image.DecompressionBombError:
                if os.path.exists(filename):
                    os.remove(filename)
                if pbar: pbar.set_postfix_str("Bomb detected! Deleted.")
                stats["failed"] += 1
                return False
            except Exception:
                # Silently ignore other image opening errors to maintain original behavior
                pass

            stats["downloaded"] += 1
            
            # Anti-ban delay with jitter
            wait_time = BASE_DELAY + random.uniform(0, JITTER_MAX)
            time.sleep(wait_time)
            return True
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                stats["failed"] += 1
                return False
            retries += 1
            time.sleep(5)
        except Exception:
            retries += 1
            time.sleep(5)
            
    stats["failed"] += 1
    return False

def process_line(line):
    """Extract image URLs from a single JSONL line (Reddit post)."""
    try:
        post = json.loads(line)
    except json.JSONDecodeError:
        return []
        
    post_id = post.get("id")
    urls = []

    # Case 1: Reddit Gallery
    if post.get("is_gallery") and "media_metadata" in post:
        metadata = post["media_metadata"]
        if isinstance(metadata, dict):
            for media_id, info in metadata.items():
                if info.get("status") == "valid" and info.get("e") == "Image":
                    s_info = info.get("s", {})
                    url = s_info.get("u")
                    if url:
                        clean_url = url.replace("&amp;", "&")
                        urls.append((clean_url, f"{post_id}_{media_id}"))

    # Case 2: Single Image
    elif post.get("post_hint") == "image" or ("i.redd.it" in post.get("url", "") and post.get("url")):
        url = post.get("url")
        if url:
            urls.append((url, post_id))

    # Case 3: External site images (e.g. imgur)
    elif "imgur.com" in post.get("url", ""):
        url = post.get("url")
        if url and any(ext in url.lower() for ext in [".jpg", ".png", ".jpeg"]):
            urls.append((url, post_id))

    return urls

def main():
    parser = argparse.ArgumentParser(description="Download images from a Reddit JSONL export with batching and anti-ban features.")
    parser.add_argument("--file", type=str, default=DEFAULT_JSONL_FILE, help=f"Path to the JSONL file. Default: {DEFAULT_JSONL_FILE}")
    parser.add_argument("--start", type=int, default=1, help="Line number to start from (1-indexed). Default: 1")
    parser.add_argument("--end", type=int, help="Line number to stop at (inclusive).")
    parser.add_argument("--limit", type=int, help="Maximum number of posts to process.")
    parser.add_argument("--count", action="store_true", help="Only count the total number of posts and exit.")
    
    args = parser.parse_args()
    jsonl_file = args.file

    if not os.path.exists(jsonl_file):
        print(f"Error: JSONL file not found at {jsonl_file}")
        print("Tip: If the file is inside a folder, make sure to include the folder name (e.g., --file subreddit_json/filename.jsonl)")
        return

    if args.count:
        print(f"Calculating total posts in {jsonl_file}...")
        total = get_total_count(jsonl_file)
        print(f"Total posts: {total}")
        return

    setup()
    
    print(f"Checking total posts in {jsonl_file}...")
    total_posts = get_total_count(jsonl_file)
    print(f"Total posts available: {total_posts}")

    start_line = max(1, args.start)
    end_line = args.end if args.end else total_posts
    if args.limit:
        end_line = min(end_line, start_line + args.limit - 1)

    total_to_process = end_line - start_line + 1
    print(f"\nProcessing Range: Line {start_line} to {end_line} ({total_to_process} posts)")
    print("-" * 50)

    current_line = 0
    
    with open(jsonl_file, "r", encoding="utf-8") as f:
        # progress bar setup
        with tqdm(total=total_to_process, desc="Downloading Posts", unit="post") as pbar:
            for line in f:
                current_line += 1
                
                if current_line < start_line:
                    continue
                if current_line > end_line:
                    break
                
                try:
                    image_targets = process_line(line)
                    post_id = "unknown"
                    try:
                        post_id = json.loads(line).get("id", "unknown")
                    except: pass

                    pbar.set_description(f"Post {current_line}/{end_line} [{post_id}]")
                    
                    if image_targets:
                        for url, name_prefix in image_targets:
                            ext = get_extension(url)
                            filepath = os.path.join(DOWNLOAD_DIR, f"{name_prefix}{ext}")
                            download_image(url, filepath, pbar)
                except Exception as e:
                    tqdm.write(f"\n[Error] Skipping post at line {current_line} due to unexpected error: {e}")
                    stats["failed"] += 1
                
                pbar.update(1)

    print("-" * 50)
    print(f"Processing Complete.")
    print(f"Total posts scanned: {total_to_process}")
    print(f"Images Successfully Downloaded: {stats['downloaded']}")
    print(f"Images Skipped (Already Exist): {stats['skipped']}")
    print(f"Images Failed (404/Error): {stats['failed']}")
    print(f"Results saved to: {os.path.abspath(DOWNLOAD_DIR)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExecution interrupted by user. Exiting gracefully...")
