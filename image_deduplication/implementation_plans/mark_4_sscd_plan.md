# Dedupe GUI Mark 4 (SSCD Implementation)

This document outlines the plan to create a new version of the image deduplication tool, migrating from CLIP to the Self-Supervised Copy Detection (SSCD) model. 

## User Review Required
> [!IMPORTANT]
> The original `dedupe_gui.py` will be left **completely untouched**. A new file, `dedupe_gui_SSCD.py`, will be created alongside it. This ensures you can always fall back to the CLIP version if needed.

## Proposed Changes

### 1. New File Creation
#### [NEW] [dedupe_gui_SSCD.py](file:///c:/Data/code/ag/flux2/image_deduplication/dedupe_gui_SSCD.py)
We will create a new Python file based on the existing `dedupe_gui.py` structure.

### 2. SSCD Model Integration
The core change involves swapping out the `transformers` CLIP model for the Meta SSCD TorchScript model.

*   **Model Download & Loading**: SSCD is not hosted natively on Hugging Face like CLIP. We will implement an automatic downloader in the `DuplicateDetector` class that fetches the `sscd_resnet50_disc_mixup.torchscript.pt` model directly from Meta's public servers and caches it locally (e.g., in a `models/` directory) so it only downloads once.
*   **Loading Mechanism**: We will use `torch.jit.load()` to load the model efficiently.

### 3. Preprocessing Updates
SSCD requires different image preprocessing than CLIP.
*   We will replace `CLIPProcessor` with `torchvision.transforms`.
*   The standard SSCD pipeline requires resizing the image to a specific resolution (e.g., 288x288), converting to a tensor, and applying ImageNet normalization (mean `[0.485, 0.456, 0.406]`, std `[0.229, 0.224, 0.225]`).

### 4. Inference & Efficiency Improvements
*   **Faster Batching**: The batched inference logic currently used for CLIP will be adapted for SSCD. Since we won't need the heavy `transformers` processor, we can use a more lightweight PyTorch DataLoader or optimized tensor stacking for batch processing.
*   **L2 Normalized Output**: SSCD outputs natively L2-normalized 512-dimensional vectors. This simplifies the similarity matrix calculation (which is already implemented efficiently via matrix multiplication). We will adjust the logic to consume this output directly.

## Verification Plan

### Automated/Manual Testing
1.  **Execution**: Run `python image_deduplication/dedupe_gui_SSCD.py`.
2.  **Model Download Test**: Ensure the script successfully downloads the SSCD `.torchscript.pt` file on the first run.
3.  **Deduplication Test**: Run a scan on a test folder containing known edited copies (e.g., crops, resized versions). Verify that SSCD correctly groups these copies with higher precision than the previous CLIP model.
4.  **UI Functionality**: Ensure all keyboard shortcuts, pagination, and deletion logic function identically to the previous version.
