# Mark 5: Cleanup & Person Removal GUI

This plan outlines the creation of a modern GUI for image cleanup tasks, merging existing CLI features with a new AI-powered "Person Removal" tool.

## User Review Required

> [!IMPORTANT]
> **Face Recognition Library**: I propose using `deepface`. It is accurate for identifying the same person across different photos and handles model management well on Windows.
>
> **UI Style**: I will use `customtkinter` to provide a premium, dark-mode interface consistent with your other tools.

## Proposed Changes

### New GUI Tool: [cleanup_gui.py](file:///c:/Data/code/ag/flux2/image_deduplication/cleanup_gui.py) [NEW]

We will create a multi-tabbed interface:

#### 1. Tab: Extension Cleanup
- **Features**: Scan the directory for all unique file types. Display a list of extensions with checkboxes.
- **Action**: Delete all files matching the selected extensions.

#### 2. Tab: Small Image Removal
- **Features**: Input field for "Minimum Dimension" (default 440px).
- **Action**: Scans for any image where width or height is below the threshold and deletes them.

#### 3. Tab: Person Removal (AI)
- **Features**: 
    - "Select Reference Person" button to upload a photo of the person you want to remove.
    - "Similarity Threshold" slider to tune how strict the matching is.
- **Logic**:
    - Uses a face recognition model to extract a "fingerprint" of the target person.
    - Scans the dataset, detects all faces in each image, and compares them to the target.
    - Displays matches and allows for bulk deletion.

#### 4. Tab: Invalid List
- **Features**: Select an `invalid_images.txt` file.
- **Action**: Deletes files listed in the document (standard cleanup).

## Technical Implementation Details

- **Backend**: Move core logic from `delete_invalid_images.py` into a `CleanupManager` class.
- **Threading**: All scanning operations will run in background threads to keep the UI responsive.
- **Dependencies**: 
    - `customtkinter`
    - `deepface`
    - `opencv-python`

## Verification Plan

### Manual Verification
1. **Extension Scan**: Verify it correctly lists `.jpg`, `.txt`, etc.
2. **Small Image Scan**: Verify it catches a known small image (e.g., 200x200).
3. **Person Removal**: 
    - Select a reference image.
    - Run scan on a small folder containing that person and others.
    - Verify it correctly identifies the target person.
4. **Dry Run**: Ensure all tabs have a "Dry Run" mode enabled by default.
