# Feature Plan: Dedupe GUI Enhancements (Mark 2)

## 1. Goal Description
The objective is to implement new features in `dedupe_gui.py` to improve the workflow for deduplication safely without breaking existing logic:
- Move kept files to a new `deDuplicated` folder instead of leaving them in the source directory.
- Update the UI slider to dynamically display the currently selected pHash threshold value.
- Add double-click functionality to images in the grid to open them in a new window with zoom and pan support.
- Allow back/forward navigation between duplicate groups using UI buttons and keyboard arrow keys.
- Log every modification made to the script in a new `implementations.md` file.

## 2. Proposed Changes
### `image_deduplication/dedupe_gui.py`

#### Modify Class `DedupeApp`
1. **File Movement Logic**:
   - Create a new `move_to_deduplicated(paths)` method mathematically identical to `move_to_trash(paths)` but targeting a `deDuplicated` folder.
   - Update `keep_selected()` to move the selected (kept) files to `os.path.join(self.source_dir, "deDuplicated")` and move the non-selected (trashed) files to `_Trash`.
   - Update `keep_all()` to move all files in the current group to the `deDuplicated` folder.

2. **pHash Slider Value Display**:
   - Create a bound `tk.DoubleVar` (or `IntVar`) for the `self.phash_threshold` slider.
   - Attach a command callback to the slider that updates the text of `self.threshold_label` in real-time to reflect the current value (e.g., "pHash Threshold: 5").

3. **Double-Click Image Viewer**:
   - In `add_image_to_grid()`, bind `<Double-Button-1>` on the image label to a new method `open_image_viewer(path)`.
   - Create `open_image_viewer(path)` which spawns a `ctk.CTkToplevel` window.
   - Inside the Toplevel, load the *full resolution* image using `PIL.Image`.
   - Implement a custom Canvas-based viewer or use a simpler approach allowing mouse-wheel zoom and click-drag panning on the canvas. 

4. **UI Updates (Navigation)**:
   - Add `< Prev` and `Next >` buttons to the `self.action_frame` alongside the existing Action buttons.
   - Bind `<Left>` and `<Right>` arrow keys on the main window to trigger the previous and next cluster functions.

5. **Navigation Logic**:
   - Implement `prev_cluster(event=None)` to decrement `self.current_cluster_idx` and call `show_cluster()` when `self.current_cluster_idx > 0`.
   - Update `next_cluster(event=None)` to handle the forward keybind constraint.
   - **Crucial Fix for Navigation**: Since moving files changes their paths, navigating *backwards* to a processed cluster would crash when trying to open the old path. To fix this, `move_to_trash` and `move_to_deduplicated` will *update and replace* the file paths inside `self.clusters[self.current_cluster_idx]` with their new absolute paths. This allows the images to still be previewed if you go backward!

## 3. User Review Required
> [!IMPORTANT]
> **Re-processing already-processed groups:**
> If you process a group (meaning files are moved to `_Trash` or `deDuplicated`) and then navigate *back* to that group, the UI will still display the images (because I'll track their new paths). However, to prevent weird bugs, I plan to **disable** the "Keep" and "Trash" buttons for any cluster that has already been processed. 
> You will be able to *look* at what you did, but not accidentally process them a second time.
> **Does this sound good to you?**

## 4. Verification Plan
- **Manual Verification**: Run `python image_deduplication/dedupe_gui.py`.
- Select a folder with duplicate images.
- Verify that moving the pHash slider updates the label text to show the exact number.
- Click "Next" and "Prev" and try Arrow Left/Right to verify navigation.
- Double click an image to ensure it opens in a new window, and verify scroll-to-zoom and click-to-pan work.
- Select images to keep and click "Keep Selected". Verify the kept images are physically moved to a `deDuplicated` subfolder and the rest are in `_Trash`.
- Go back to the previously processed cluster and verify it renders correctly from the new folders, but the action buttons are grayed out.
