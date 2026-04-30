# Feature Plan: Dedupe GUI Enhancements (Mark 3.5)

## 1. Goal Description
The objective is to refine the workflow for the "Trash All" action by replacing the custom popup confirmation with a more fluid, stylish "double-tap" confirmation mechanism directly on the button.
- When the user presses 'D' (or clicks the Trash All button) for the first time, the button will enter a "Warning State" (e.g., turning bright red, changing text to "Press D Again to Trash All").
- If the user presses 'D' again while in this Warning State, the deletion triggers.
- If the user presses any other key, clicks elsewhere, or waits for a timeout (e.g., 3 seconds), the button reverts to its normal state.

Additionally, we will add an **Animated Toast Notification** system:
- When files are moved to `_Trash` or `deDuplicated`, a small, non-obtrusive "toast" message will slide up from the bottom of the GUI (e.g. "Moved 5 images to Trash").
- The toast will stay visible for a short duration (e.g., 2.5 seconds) and then smoothly fade or slide away, keeping the user informed of background actions without blocking their workflow.

## 2. Proposed Changes
### `image_deduplication/dedupe_gui.py`

#### 2.1 Double-Tap State Management
- Introduce a new state variable in `DedupeApp`: `self.trash_armed = False`.
- Introduce a timer variable: `self.trash_timer = None`.

#### 2.2 Redesigning `trash_all`
- Update the `trash_all` method to handle the two-stage process:
  - **First Press (`self.trash_armed == False`)**:
    - Set `self.trash_armed = True`.
    - Change `self.trash_all_btn` appearance: `fg_color="#ff0000"` (bright red), `text="PRESS D AGAIN TO TRASH"`.
    - Set a timer using `self.after(3000, self.disarm_trash)` to automatically cancel the armed state after 3 seconds.
  - **Second Press (`self.trash_armed == True`)**:
    - Cancel the timer (`self.after_cancel(self.trash_timer)`).
    - Execute the actual deletion (`self.move_to_trash(...)`).
    - Reset the button appearance and state (`self.disarm_trash()`).

#### 2.3 `disarm_trash` Helper
- Create a `disarm_trash` method that resets `self.trash_armed = False` and restores the standard appearance of the `trash_all_btn` (`fg_color="red"`, `text="Trash All (D)"`).

#### 2.4 Navigation Canceling
- Modify `next_cluster`, `prev_cluster`, `keep_all`, and `keep_selected` to call `self.disarm_trash()` if triggered, ensuring the armed state doesn't accidentally carry over to the next group or action.

#### 2.5 Right-Click Consistency (Optional)
- *Note:* The user only mentioned the "D button" (Trash All). The single-image right-click delete (`on_right_click`) currently uses the custom popup. We will keep the custom popup *only* for single right-clicks, and use the double-tap for the global Trash All.

#### 2.6 Animated Toast Notification
- Add a new method `show_toast(self, message)` to `DedupeApp`.
- The method will create a `ctk.CTkFrame` with a `ctk.CTkLabel` inside it, initially placed off-screen or totally transparent at the bottom center of the main window.
- Use `self.after` loops to animate the toast sliding up into view (`place` with changing `rely`), pausing for 2.5 seconds, and then animating back down/destroying itself.
- Update `move_to_trash` and `move_to_deduplicated` to call `self.show_toast(f"Moved {len(paths)} images to ...")`.

## 3. User Review Required
> [!NOTE]
> Are you okay with implementing this double-tap logic strictly for the main "Trash All (D)" button, while leaving the existing custom popup for when you right-click a single image to delete it?

## 4. Verification Plan
- Launch the application and select a folder.
- Press 'D'. Verify the button turns bright red and changes text.
- Wait 3 seconds. Verify the button resets.
- Press 'D', then press 'A'. Verify the Keep All action triggers and the Trash button resets immediately.
- Press 'D', then press 'D' again within 3 seconds. Verify the images are trashed and it navigates to the next page.
