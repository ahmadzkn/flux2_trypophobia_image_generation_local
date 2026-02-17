# IMPL_PLAN: Desktop Image Deduplication Tool (Mark 1)

## Goal
Create a local Python desktop application (`image_deduplication/dedupe_gui.py`) to visually find and clean up duplicate images. The tool will use a hybrid detection engine (Perceptual Hashing + CLIP AI) to find both exact and semantic duplicates. It will provide a user-friendly "Tinder-like" or Grid-based review interface to decide which images to keep.

## User Review Required
> [!IMPORTANT]
> **"Keep All" Logic**: When you select "Keep All", the tool will simply **ignore** this group of duplicates and move to the next set. No files will be moved or deleted.
>
> **Trash Mechanism**: Deleted files will be moved to a `_Trash` folder within the source directory instead of permanent deletion, for safety.

## Proposed Architecture

### 1. The Detection Engine (`DuplicateDetector` class)
*   **Level 1 (Fast):** Perceptual Hashing (`phash`).
    *   Rapidly groups near-identical images (resizes, format changes).
    *   Calculates Hamming distance between hashes.
*   **Level 2 (Smart):** CLIP Model (`openai/clip-vit-base-patch32`).
    *   For groups that pHash misses or for deep scans.
    *   Encodes images into vectors and calculates Cosine Similarity.
    *   Runs on GPU (RTX 5080) for speed.

### 2. The GUI (`DedupeApp` class using `customtkinter`)
*   **Main Window**:
    *   **Sidebar**: Settings (Threshold sliders), "Scan Folder" button, Progress Bar.
    *   **Main Area**: A dynamic grid displaying the current "Cluster" of duplicates.
*   **Review Flow**:
    *   The app presents one cluster of duplicates at a time.
    *   User sees images side-by-side with resolution and file size labels.
*   **Controls**:
    *   `[Keep Selected]`: Moves unselected images to `_Trash`.
    *   `[Keep All]`: Skips this cluster (keeps everything).
    *   `[Delete All]`: Moves entire cluster to `_Trash`.

## Proposed Component Structure

#### [NEW] `image_deduplication/dedupe_gui.py`
This single file (splitting into modules if it gets too large) will contain:
1.  **Imports**: `customtkinter`, `PIL`, `imagehash`, `torch`, `transformers`.
2.  **`start_scan()`**: Runs detection in a background thread to keep UI responsive.
3.  **`show_cluster()`**: Renders images in the grid.
4.  **`on_keep_all()`**: Logic to skip current cluster.
5.  **`on_keep_selected()`**: Logic to move others to trash.

## Verification Plan

### Automated Tests
*   We cannot easily unit test the GUI, but we can verify the **Logic**:
    *   Create a test script `image_deduplication/test_detection.py` that generates 5 variations of an image (crop, blur, resize) and asserts that the `DuplicateDetector` groups them together.

### Manual Verification
1.  **Setup**: Create a folder `image_deduplication/test_images` with:
    *   `img1.jpg` (Original)
    *   `img1_copy.jpg` (Exact duplicate)
    *   `img1_small.jpg` (Resized)
    *   `img2.jpg` (Different image)
    *   `img2_rotated.jpg` (Rotated version)
2.  **Run Tool**: Launch `image_deduplication/dedupe_gui.py`.
3.  **Test Scan**: Verify it finds 2 groups (img1 group, img2 group).
4.  **Test "Keep All"**: On img2 group, click "Keep All". Verify both files remain.
5.  **Test "Keep One"**: On img1 group, select `img1.jpg` and click "Keep Selected". Verify `img1_copy` and `img1_small` are moved to `image_deduplication/test_images/_Trash`.
