# Feature Plan: Dedupe GUI Enhancements (Mark 3)

## 1. Goal Description
The objective is to further streamline the workflow in `dedupe_gui.py` by introducing keyboard shortcuts and better folder context:
- Bind keyboard keys to the main action buttons: 'd' or 'D' for Trash All, 'a' or 'A' for Keep All, and 's' or 'S' for Keep Selected & Trash Others.
- Ensure the "Trash All" confirmation popup can be accepted/declined using 'y' and 'n'.
- Display the currently selected target folder path in the GUI for constant reference.

## 2. Proposed Changes
### `image_deduplication/dedupe_gui.py`

#### 2.1 Keyboard Shortcuts
- In `_setup_ui` (or `__init__`), bind the keys `<d>`, `<D>`, `<a>`, `<A>`, `<s>`, and `<S>` to their respective methods (`trash_all`, `keep_all`, `keep_selected`).
- Modify the event handlers (e.g., `def trash_all(self, event=None):`) so they can accept the event object passed by Tkinter keybindings.
- Ensure that the action is only triggered if the corresponding button is active (e.g., checking `if self.trash_all_btn.cget("state") == "normal":`).

#### 2.2 Yes/No Keyboard Bindings for Custom Popups
- `tkinter.messagebox` is a blocking native OS call that unfortunately intercepts the main loop, meaning we cannot easily bind `y` and `n` globally while the standard messagebox is open.
- **Solution**: Replace the native `messagebox.askyesno` in `trash_all` and `on_right_click` with a custom `ctk.CTkToplevel` popup confirmation window. 
- The custom popup will explicitly bind `<y>`, `<Y>`, `<n>`, `<N>`, `<Return>`, and `<Escape>` to handle the confirmation organically via keyboard.

#### 2.3 Selected Folder Path Display
- In `_setup_ui`, add a new `ctk.CTkLabel` (e.g., `self.folder_label`) underneath the "Select a folder to start scanning" header, initially set to "No folder selected".
- Update `select_folder(self)` to change the text of `self.folder_label` to `self.source_dir` once a folder is chosen.

## 3. User Review Required
> [!NOTE]
> Are you okay with replacing the native Windows popup (which you get from `messagebox.askyesno`) with a custom Dark Mode UI popup so that we can support the 'Y' and 'N' keyboard bindings? The native Windows popup usually captures all input and can't be modified to accept custom keys easily in Tkinter.

## 4. Verification Plan
- Launch the application and select a folder.
- Verify the selected folder's absolute path appears at the top of the main window.
- Scan for duplicates.
- Press 'S', verify Keep Selected works. 
- Press 'A', verify Keep All works.
- Press 'D', verify a custom popup appears for Trash All. Press 'N' to cancel, verify the popup closes. Press 'D' again, and press 'Y', verify the images are trashed.
