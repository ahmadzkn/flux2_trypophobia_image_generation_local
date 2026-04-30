import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import imagehash
import torch
import torchvision.transforms as transforms
from transformers import AutoImageProcessor, AutoModel
from threading import Thread
import concurrent.futures
import time

# --- Setup Aesthetics ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DuplicateDetector:
    def __init__(self, use_dinov2=True):
        self.use_dinov2 = use_dinov2
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if use_dinov2:
            print("Loading DinoV2 model (Replacing SSCD due to Meta server 403 error)...")
            self.processor = AutoImageProcessor.from_pretrained('facebook/dinov2-base')
            self.model = AutoModel.from_pretrained('facebook/dinov2-base').to(self.device)
            self.model.eval()
        
    def get_phash(self, image_path):
        try:
            with Image.open(image_path) as img:
                return str(imagehash.phash(img))
        except Exception:
            return None

class DedupeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Visual Image Deduplicator")
        self.geometry("1200x800")

        self.detector = None
        self.clusters = []
        self.current_cluster_idx = -1
        self.processed_clusters = set()
        self.image_objects = [] # To prevent GC
        self.selected_indices = set()
        self.source_dir = ""
        
        # Pagination for large groups
        self.page_size = 50
        self.current_page = 0
        
        # Double-Tap & Toast State
        self.trash_armed = False
        self.trash_timer = None
        self.toast_frame = None
        self.toast_timer = None
        self.toast_anim_timer = None

        self._setup_ui()
        self.bind("<Left>", self.prev_cluster)
        self.bind("<Right>", self.next_cluster)
        
        # Action Shortcuts
        self.bind("<d>", self.trash_all)
        self.bind("<D>", self.trash_all)
        self.bind("<a>", self.keep_all)
        self.bind("<A>", self.keep_all)
        self.bind("<s>", self.keep_selected)
        self.bind("<S>", self.keep_selected)

    def _setup_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="Dedupe Tool", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(padx=20, pady=(20, 10))

        self.scan_button = ctk.CTkButton(self.sidebar, text="Scan Folder", command=self.select_folder)
        self.scan_button.pack(padx=20, pady=10)

        self.threshold_label = ctk.CTkLabel(self.sidebar, text="pHash Threshold: 5")
        self.threshold_label.pack(padx=20, pady=(20, 0))
        self.phash_threshold = ctk.CTkSlider(self.sidebar, from_=0, to=20, number_of_steps=20, command=self.update_threshold_label)
        self.phash_threshold.set(5)
        self.phash_threshold.pack(padx=20, pady=5)

        self.dinov2_var = tk.BooleanVar(value=True)
        self.dinov2_checkbox = ctk.CTkCheckBox(self.sidebar, text="Use DinoV2 (AI)", variable=self.dinov2_var)
        self.dinov2_checkbox.pack(padx=20, pady=20)

        self.progress_label = ctk.CTkLabel(self.sidebar, text="Ready")
        self.progress_label.pack(padx=20, pady=(20, 0))
        self.progress_bar = ctk.CTkProgressBar(self.sidebar)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=20, pady=10)

        self.device_label = ctk.CTkLabel(self.sidebar, text="Device: Checking...", font=ctk.CTkFont(size=10))
        self.device_label.pack(side="bottom", pady=10)


        # Main Content
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Header with cluster info
        self.header_label = ctk.CTkLabel(self.main_frame, text="Select a folder to start scanning", font=ctk.CTkFont(size=16))
        self.header_label.pack(pady=(10, 0))
        
        self.folder_label = ctk.CTkLabel(self.main_frame, text="No folder selected", font=ctk.CTkFont(size=11), text_color="gray")
        self.folder_label.pack(pady=(0, 10))

        # Scrollable Image Grid
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="Duplicates Found")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Dedicated container for images to avoid destroying scrollbar/label
        self.grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)
        self.grid_container.grid_columnconfigure((0,1,2), weight=1)

        # Footer Actions
        self.action_frame = ctk.CTkFrame(self.main_frame, height=100)
        self.action_frame.pack(fill="x", side="bottom", padx=10, pady=10)

        self.prev_btn = ctk.CTkButton(self.action_frame, text="< Prev", command=self.prev_cluster, state="disabled", width=60)
        self.prev_btn.pack(side="left", padx=(20, 5), pady=20)

        self.keep_selected_btn = ctk.CTkButton(self.action_frame, text="Keep Selected (S)", 
                                                command=self.keep_selected, state="disabled", fg_color="green", hover_color="#006400")
        self.keep_selected_btn.pack(side="left", padx=5, pady=20, expand=True)

        self.keep_all_btn = ctk.CTkButton(self.action_frame, text="Keep All (A)", 
                                           command=self.keep_all, state="disabled")
        self.keep_all_btn.pack(side="left", padx=5, pady=20, expand=True)

        self.trash_all_btn = ctk.CTkButton(self.action_frame, text="Trash All (D)", 
                                            command=self.trash_all, state="disabled", fg_color="red", hover_color="#8B0000")
        self.trash_all_btn.pack(side="left", padx=5, pady=20, expand=True)

        self.next_btn = ctk.CTkButton(self.action_frame, text="Next >", command=self.next_cluster, state="disabled", width=60)
        self.next_btn.pack(side="left", padx=(5, 20), pady=20)
        
        # Pagination Controls
        self.pagination_frame = ctk.CTkFrame(self.main_frame, height=40, fg_color="transparent")
        self.pagination_frame.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        
        self.page_prev_btn = ctk.CTkButton(self.pagination_frame, text="< Prev Page", command=self.prev_page, state="disabled", width=100)
        self.page_prev_btn.pack(side="left", padx=20)
        
        self.page_label = ctk.CTkLabel(self.pagination_frame, text="Page 1/1")
        self.page_label.pack(side="left", expand=True)
        
        self.page_next_btn = ctk.CTkButton(self.pagination_frame, text="Next Page >", command=self.next_page, state="disabled", width=100)
        self.page_next_btn.pack(side="right", padx=20)

    def update_threshold_label(self, value):
        self.threshold_label.configure(text=f"pHash Threshold: {int(value)}")

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_dir = folder
            self.folder_label.configure(text=folder)
            self.start_scan_thread()

    def start_scan_thread(self):
        self.scan_button.configure(state="disabled")
        self.progress_label.configure(text="Scanning...")
        Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        if not self.detector or (self.detector.use_dinov2 != self.dinov2_var.get()):
            self.detector = DuplicateDetector(use_dinov2=self.dinov2_var.get())

        # 0. Global Safety Settings
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None # Disable decompression bomb warning for high-res images
        
        # Update device label immediately
        dev_text = f"Device: {self.detector.device.upper()}"
        self.after(0, lambda: self.device_label.configure(text=dev_text))

        files = [os.path.join(self.source_dir, f) for f in os.listdir(self.source_dir) 
                 if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
        
        total = len(files)
        hashes = {}
        embeddings = {}
        invalid_images = []
        
        # 1. Calculate pHashes (Parallelized CPU Bound)
        print(f"Starting parallel pHash for {total} files...")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(self.detector.get_phash, f): f for f in files}
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                f = future_to_file[future]
                try:
                    h = future.result()
                    if h:
                        hashes[f] = imagehash.hex_to_hash(h)
                    else:
                        invalid_images.append(f)
                except Exception as e:
                    print(f"Error hashing {f}: {e}")
                    invalid_images.append(f)
                
                completed += 1
                if completed % 50 == 0 or completed == total:
                    self.progress_bar.set((completed / total) * 0.5)
                    self.after(0, lambda c=completed, t=total: 
                               self.progress_label.configure(text=f"Hashing {c}/{t}"))

        # 2. Calculate AI Embeddings (Parallel Load + Batch Processing)
        if self.dinov2_var.get():
            batch_size = 128
            print(f"--- Starting hardware-accelerated DinoV2 scanning (batch size: {batch_size}) ---")
            
            # Use threads ONLY for the slow disk loading part
            def load_image_only(path):
                try:
                    with Image.open(path) as img:
                        img_rgb = img.convert("RGB")
                        img_rgb.thumbnail((250, 250))
                        return img_rgb, path
                except Exception as e:
                    print(f"  [DEBUG] Error loading {os.path.basename(path)}: {e}")
                    return None, path

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                def iter_batches():
                    for i in range(0, total, batch_size):
                        yield i, files[i:i + batch_size]
                
                batch_iterator = iter_batches()

                try:
                    current_i, current_batch_files = next(batch_iterator)
                    current_futures = [executor.submit(load_image_only, f) for f in current_batch_files]
                except StopIteration:
                    current_futures = None

                while current_futures is not None:
                    # Pre-submit the NEXT batch to keep workers busy while GPU infers
                    try:
                        next_i, next_batch_files = next(batch_iterator)
                        next_futures = [executor.submit(load_image_only, f) for f in next_batch_files]
                    except StopIteration:
                        next_futures = None
                        next_i = None

                    # 2a. Realize the current batch (Wait for it to finish loading)
                    results = [f.result() for f in current_futures]
                    
                    batch_imgs = []
                    valid_batch_paths = []
                    for img, path in results:
                        if img is not None:
                            batch_imgs.append(img)
                            valid_batch_paths.append(path)
                        else:
                            if path not in invalid_images:
                                invalid_images.append(path)
                            print(f"  [Error] Skipping unreadable image: {os.path.basename(path)}")
                    
                    # 2b. Batch Preprocess and GPU Inference (Main thread for stability)
                    if batch_imgs:
                        try:
                            inputs = self.detector.processor(images=batch_imgs, return_tensors="pt").to(self.detector.device)
                            
                            with torch.no_grad():
                                outputs = self.detector.model(**inputs)
                            
                            # Extract CLS token as global descriptor
                            batch_outputs = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                            
                            for idx in range(len(batch_outputs)):
                                embeddings[valid_batch_paths[idx]] = batch_outputs[idx].flatten()
                            
                            print(f"DinoV2 Scan: Batch {current_i//batch_size + 1} | Processed {len(batch_outputs)} images")
                        except Exception as e:
                            print(f"  [DinoV2 Error] Batch {current_i//batch_size + 1} failed: {e}")
                    else:
                        print(f"DinoV2 Scan: Batch {current_i//batch_size + 1} | SKIPPED (No valid images in this block)")

                    # Update UI progress
                    self.progress_bar.set(0.5 + ((min(current_i + batch_size, total) / total) * 0.5))
                    self.after(0, lambda curr=min(current_i+batch_size, total), t=total: 
                               self.progress_label.configure(text=f"DinoV2 AI Scanning {curr}/{t}"))

                    # Move to next batch
                    current_futures = next_futures
                    current_i = next_i

            print(f"--- AI SCAN COMPLETE: Stored {len(embeddings)} embeddings ---")
            if len(embeddings) == 0:
                print("WARNING: DinoV2 AI found 0 valid images. Clustering will fall back to pHash only.")

        # 2c. Log invalid images to file
        if invalid_images:
            try:
                with open("invalid_images.txt", "w", encoding="utf-8") as f:
                    for img_path in sorted(list(set(invalid_images))):
                        f.write(f"{img_path}\n")
                print(f"Logged {len(set(invalid_images))} invalid images to 'invalid_images.txt'")
            except Exception as e:
                print(f"Failed to write invalid_images.txt: {e}")

        # 3. Clustering Logic (Mark 2.0: Batched GPU + Graph Theory)
        self.after(0, lambda: self.progress_label.configure(text="Building Group Graph..."))
        threshold = self.phash_threshold.get()
        clip_threshold = 0.95
        
        import numpy as np
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import connected_components
        
        # Build an adjacency matrix (Graph edges)
        rows = []
        cols = []
        
        # 3a. pHash Graph building (GPU Vectorized)
        hash_file_list = list(hashes.keys())
        # Map filenames to their original indices in 'files' list
        file_to_idx = {f: idx for idx, f in enumerate(files)}
        n_hashed = len(hash_file_list)
        
        if n_hashed > 0:
            print(f"Building GPU-accelerated pHash graph for {n_hashed} images...")
            # Convert pHashes to bit-vectors (-1 and 1) for dot product trick
            # Each hash is 64 bits. 
            bit_vectors = []
            for f in hash_file_list:
                # Get boolean array and convert to -1/1
                b = hashes[f].hash.flatten()
                bit_vectors.append(np.where(b, 1, -1))
            
            all_bits = torch.tensor(np.array(bit_vectors), dtype=torch.float32).to(self.detector.device)
            
            # Dot product P = 64 - 2*Hamming => Hamming = (64 - P)/2
            # Threshold H means P >= 64 - 2*H
            dot_threshold = 64 - 2 * threshold
            
            sim_batch_size = 5000
            for i in range(0, n_hashed, sim_batch_size):
                end_i = min(i + sim_batch_size, n_hashed)
                batch = all_bits[i:end_i]
                
                # Matrix multiplication on bits
                scores = torch.matmul(batch, all_bits.T) # [5000, n_hashed]
                
                # Find indices above dot_threshold
                mask = scores >= dot_threshold
                
                # Get indices and map back to absolute file indices
                match_indices = torch.nonzero(mask).cpu().numpy()
                for row, col in match_indices:
                    r_local = i + row
                    if r_local < col: 
                        rows.append(file_to_idx[hash_file_list[r_local]])
                        cols.append(file_to_idx[hash_file_list[col]])
                
                self.after(0, lambda curr=end_i, t=n_hashed: 
                           self.progress_label.configure(text=f"pHash Clustering {curr}/{t}"))

        # 3b. Vectorized AI edges on GPU (The fast part)
        if self.dinov2_var.get() and embeddings:
            self.after(0, lambda: self.progress_label.configure(text="AI Clustering..."))
            print(f"Calculating GPU Similarity Matrix (Batched: 5000)...")
            # Get an arbitrary sample embedding to find its size (DinoV2 base is 768)
            emb_size = len(next(iter(embeddings.values()))) if embeddings else 768
            emb_list = [embeddings.get(f, np.zeros(emb_size)) for f in files]
            all_embs = torch.tensor(np.array(emb_list), dtype=torch.float32).to(self.detector.device)
            # Normalize
            all_embs = all_embs / (all_embs.norm(dim=1, keepdim=True) + 1e-9)
            
            # Batch the N x N calculation to avoid OOM
            sim_batch_size = 5000
            for i in range(0, total, sim_batch_size):
                end_i = min(i + sim_batch_size, total)
                batch = all_embs[i:end_i]
                
                # Multiply batch by all other embeddings (Matrix Multi)
                scores = torch.matmul(batch, all_embs.T) # size: [5000, N]
                
                # Find indices above threshold
                mask = scores >= clip_threshold
                
                # Get indices where mask is True (on GPU if possible, then move)
                match_indices = torch.nonzero(mask).cpu().numpy()
                for row, col in match_indices:
                    r_idx = i + row
                    if r_idx < col: # Only need one half of the matrix for undirected graph
                        rows.append(r_idx)
                        cols.append(col)
                
                self.after(0, lambda curr=end_i, t=total: 
                           self.progress_label.configure(text=f"AI Clustering {curr}/{t}"))

        # 3c. Solve Graph: All connected images form a cluster
        self.after(0, lambda: self.progress_label.configure(text="Finalizing groups..."))
        if len(rows) > 0:
            data = np.ones(len(rows))
            adj = csr_matrix((data, (rows, cols)), shape=(total, total))
            n_comp, labels = connected_components(adj, directed=False)
            
            # Group files by labels
            comp_to_files = {}
            for idx, label in enumerate(labels):
                if label not in comp_to_files:
                    comp_to_files[label] = []
                comp_to_files[label].append(files[idx])
                
            self.clusters = [c for c in comp_to_files.values() if len(c) > 1]
            print(f"Clustering complete. Found {len(self.clusters)} groups of duplicates.")
        else:
            self.clusters = []
            print("Clustering complete. No duplicates found.")
            
        self.after(0, self.finish_scan)

    def cosine_similarity(self, v1, v2):
        import numpy as np
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    def finish_scan(self):
        self.scan_button.configure(state="normal")
        dev_text = f"Device: {self.detector.device.upper()}"
        self.device_label.configure(text=dev_text)
        self.progress_label.configure(text=f"Done! Found {len(self.clusters)} groups.")
        self.processed_clusters.clear()
        if self.clusters:
            self.current_cluster_idx = 0
            self.current_page = 0
            self.show_cluster()
        else:
            messagebox.showinfo("Scan Complete", "No duplicates found with current threshold.")

    def show_cluster(self):
        if self.current_cluster_idx >= len(self.clusters):
            messagebox.showinfo("Finished", "All duplicates have been reviewed!")
            self.header_label.configure(text="Review complete.")
            self.keep_selected_btn.configure(state="disabled")
            self.keep_all_btn.configure(state="disabled")
            self.trash_all_btn.configure(state="disabled")
            if hasattr(self, 'next_btn'): self.next_btn.configure(state="disabled")
            if self.current_cluster_idx > 0 and hasattr(self, 'prev_btn'):
                self.prev_btn.configure(state="normal")
            return

        # Clear grid (safely destroy only image containers)
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        
        self.image_objects = []
        self.selected_indices = set()
        
        cluster = self.clusters[self.current_cluster_idx]
        
        # Navigation Buttons Update
        if hasattr(self, 'prev_btn'):
            self.prev_btn.configure(state="normal" if self.current_cluster_idx > 0 else "disabled")
        if hasattr(self, 'next_btn'):
            self.next_btn.configure(state="normal" if self.current_cluster_idx < len(self.clusters) - 1 else "disabled")

        # Processed status checking
        if self.current_cluster_idx in self.processed_clusters:
            self.header_label.configure(text=f"Group {self.current_cluster_idx + 1} of {len(self.clusters)} (Processed)")
            self.keep_selected_btn.configure(state="disabled")
            self.keep_all_btn.configure(state="disabled")
            self.trash_all_btn.configure(state="disabled")
        else:
            self.header_label.configure(text=f"Group {self.current_cluster_idx + 1} of {len(self.clusters)} (Found {len(cluster)} images)")
            self.keep_selected_btn.configure(state="normal")
            self.keep_all_btn.configure(state="normal")
            self.trash_all_btn.configure(state="normal")

        # Pagination Logic
        total_images = len(cluster)
        total_pages = (total_images + self.page_size - 1) // self.page_size
        
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)
            
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total_images)
        
        self.page_label.configure(text=f"Page {self.current_page + 1}/{max(1, total_pages)} (Showing {start_idx+1}-{end_idx})")
        
        if hasattr(self, 'page_prev_btn'):
            self.page_prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        if hasattr(self, 'page_next_btn'):
            self.page_next_btn.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

        page_cluster = cluster[start_idx:end_idx]

        for i, path in enumerate(page_cluster):
            # Pass the absolute index for selection tracking, but relative i for grid placement
            self.add_image_to_grid(path, i, absolute_idx=start_idx + i)

    def prev_page(self):
        if hasattr(self, 'disarm_trash'): self.disarm_trash()
        if self.current_page > 0:
            self.current_page -= 1
            self.show_cluster()
            
    def next_page(self):
        if hasattr(self, 'disarm_trash'): self.disarm_trash()
        cluster = self.clusters[self.current_cluster_idx]
        total_pages = (len(cluster) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.show_cluster()

    def add_image_to_grid(self, path, grid_idx, absolute_idx):
        try:
            # Stats
            size_kb = os.path.getsize(path) / 1024
            with Image.open(path) as temp_img:
                res = f"{temp_img.width}x{temp_img.height}"
                # Thumbnail
                aspect = temp_img.width / temp_img.height
                new_w = 250
                new_h = int(new_w / aspect)
                temp_img.thumbnail((new_w, new_h))
                img = ImageTk.PhotoImage(temp_img)
            
            self.image_objects.append(img) # Prevent GC

            # Container (3 columns for better fit on 1200px width)
            container = ctk.CTkFrame(self.grid_container)
            container.grid(row=grid_idx // 3, column=grid_idx % 3, padx=10, pady=10, sticky="nsew")

            # Restore Selection State if it was selected on a previous viewing of this page
            if absolute_idx in self.selected_indices:
                container.configure(fg_color="#1f538d")

            # Image Label (Clickable)
            img_label = tk.Label(container, image=img, bg="#2b2b2b")
            img_label.pack(pady=5)
            img_label.bind("<Button-1>", lambda e, i=absolute_idx, c=container: self.toggle_selection(i, c))
            img_label.bind("<Button-3>", lambda e, p=path, c=container: self.on_right_click(p, c))
            img_label.bind("<Double-Button-1>", lambda e, p=path: self.open_image_viewer(p))

            # Info Labels
            info = f"{os.path.basename(path)}\n{res} | {size_kb:.1f} KB"
            ctk.CTkLabel(container, text=info, font=ctk.CTkFont(size=10)).pack()

        except Exception as e:
            print(f"Error loading {path}: {e}")

    def open_image_viewer(self, path):
        viewer = ctk.CTkToplevel(self)
        viewer.title(f"Viewing: {os.path.basename(path)}")
        viewer.geometry("800x800")
        viewer.focus()
        
        try:
            img = Image.open(path)
            viewer.original_image = img
            viewer.zoom_factor = 1.0
            
            canvas = tk.Canvas(viewer, bg="#1e1e1e", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            
            viewer.img_id = None
            viewer.cx, viewer.cy = 400, 400
            
            def render():
                w, h = viewer.original_image.size
                new_w = max(1, int(w * viewer.zoom_factor))
                new_h = max(1, int(h * viewer.zoom_factor))
                resized = viewer.original_image.resize((new_w, new_h), Image.Resampling.NEAREST)
                viewer.tk_img = ImageTk.PhotoImage(resized)
                
                if viewer.img_id is not None:
                    canvas.delete(viewer.img_id)
                viewer.img_id = canvas.create_image(viewer.cx, viewer.cy, image=viewer.tk_img, anchor="center")
            
            def init_render(event=None):
                if viewer.img_id is None:
                    cw, ch = canvas.winfo_width(), canvas.winfo_height()
                    w, h = viewer.original_image.size
                    viewer.cx, viewer.cy = cw//2, ch//2
                    if w > 0 and h > 0:
                        viewer.zoom_factor = min(cw/w, ch/h)
                    render()
            
            canvas.bind("<Configure>", init_render)
            
            def on_mousewheel(event):
                if event.delta > 0:
                    viewer.zoom_factor *= 1.2
                else:
                    viewer.zoom_factor /= 1.2
                render()
                
            viewer.bind("<MouseWheel>", on_mousewheel)
            
            viewer.drag_data = {"x": 0, "y": 0}
            def on_drag_start(event):
                viewer.drag_data["x"] = event.x
                viewer.drag_data["y"] = event.y
            def on_drag_motion(event):
                dx = event.x - viewer.drag_data["x"]
                dy = event.y - viewer.drag_data["y"]
                viewer.cx += dx
                viewer.cy += dy
                if viewer.img_id is not None:
                    canvas.move(viewer.img_id, dx, dy)
                viewer.drag_data["x"] = event.x
                viewer.drag_data["y"] = event.y
                
            canvas.bind("<ButtonPress-1>", on_drag_start)
            canvas.bind("<B1-Motion>", on_drag_motion)
            
        except Exception as e:
            print(f"Error opening viewer for {path}: {e}")

    def toggle_selection(self, idx, container):
        """Toggle blue tint and add to selected list."""
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
            container.configure(fg_color="transparent")
        else:
            self.selected_indices.add(idx)
            container.configure(fg_color="#1f538d") 

    def custom_askyesno(self, title, message, callback):
        """A custom popup replacement for messagebox.askyesno that supports y/n keys."""
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("350x150")
        
        # Make modal
        popup.transient(self)
        popup.grab_set()
        popup.focus()
        
        label = ctk.CTkLabel(popup, text=message, wraplength=300)
        label.pack(pady=20, padx=20, expand=True)
        
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=20)
        
        def confirm(event=None):
            popup.grab_release()
            popup.destroy()
            callback(True)
            
        def decline(event=None):
            popup.grab_release()
            popup.destroy()
            callback(False)
        
        yes_btn = ctk.CTkButton(btn_frame, text="Yes (Y)", command=confirm, width=100)
        yes_btn.pack(side="left", padx=10)
        
        no_btn = ctk.CTkButton(btn_frame, text="No (N)", command=decline, width=100, fg_color="gray", hover_color="#4f4f4f")
        no_btn.pack(side="left", padx=10)
        
        # Bindings
        popup.bind("<y>", confirm)
        popup.bind("<Y>", confirm)
        popup.bind("<n>", decline)
        popup.bind("<N>", decline)
        popup.bind("<Return>", confirm)
        popup.bind("<Escape>", decline)
        
        popup.protocol("WM_DELETE_WINDOW", decline)

    def on_right_click(self, path, container):
        if hasattr(self, 'processed_clusters') and self.current_cluster_idx in self.processed_clusters:
            return

        def process_delete(result):
            if result:
                cluster = self.clusters[self.current_cluster_idx]
                if path in cluster:
                    cluster.remove(path)
                self.move_to_trash([path])
                
                if len(cluster) <= 1:
                    self.processed_clusters.add(self.current_cluster_idx)
                
                self.show_cluster()

        self.custom_askyesno("Confirm Delete", f"Move {os.path.basename(path)} to trash?", process_delete)

    def prev_cluster(self, event=None):
        if hasattr(self, 'disarm_trash'): self.disarm_trash()
        if hasattr(self, 'prev_btn') and self.prev_btn.cget("state") == "normal":
            self.current_cluster_idx -= 1
            self.current_page = 0
            if self.current_cluster_idx < 0:
                self.current_cluster_idx = 0
            self.show_cluster()

    def next_cluster(self, event=None):
        if hasattr(self, 'disarm_trash'): self.disarm_trash()
        if hasattr(self, 'next_btn') and self.next_btn.cget("state") == "normal":
            self.current_page = 0
            if self.current_cluster_idx < len(self.clusters) - 1:
                self.current_cluster_idx += 1
                self.show_cluster()
            else:
                self.show_cluster()

    def update_cluster_paths(self, old_new_pairs):
        if not hasattr(self, 'current_cluster_idx') or self.current_cluster_idx < 0:
            return
        if self.current_cluster_idx >= len(self.clusters):
            return
        cluster = self.clusters[self.current_cluster_idx]
        for old_p, new_p in old_new_pairs:
            for i in range(len(cluster)):
                if cluster[i] == old_p:
                    cluster[i] = new_p

    def disarm_trash(self):
        if self.trash_armed:
            self.trash_armed = False
            if self.trash_timer is not None:
                self.after_cancel(self.trash_timer)
                self.trash_timer = None
            if hasattr(self, 'trash_all_btn'):
                self.trash_all_btn.configure(text="Trash All (D)", fg_color="red", hover_color="#8B0000")

    def show_toast(self, message):
        if self.toast_frame is not None:
            self.toast_frame.destroy()
        if self.toast_timer is not None:
            self.after_cancel(self.toast_timer)
        if self.toast_anim_timer is not None:
            self.after_cancel(self.toast_anim_timer)
            
        self.toast_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=8, border_width=1, border_color="#555555")
        label = ctk.CTkLabel(self.toast_frame, text=message, font=ctk.CTkFont(size=14, weight="bold"), text_color="white")
        label.pack(padx=20, pady=10)
        
        # Start at bottom (off-screen)
        self.toast_frame.place(relx=0.5, rely=1.1, anchor="center")
        
        # Animate slide up
        target_rely = 0.90
        current_rely = 1.1
        steps = 15
        step_size = (current_rely - target_rely) / steps
        
        def animate_up(step):
            nonlocal current_rely
            if step < steps:
                current_rely -= step_size
                self.toast_frame.place(relx=0.5, rely=current_rely, anchor="center")
                self.toast_anim_timer = self.after(16, animate_up, step + 1)
            else:
                self.toast_frame.place(relx=0.5, rely=target_rely, anchor="center")
                self.toast_timer = self.after(2500, slide_down)
                
        def slide_down(step=0):
            nonlocal current_rely
            if step < steps:
                current_rely += step_size
                self.toast_frame.place(relx=0.5, rely=current_rely, anchor="center")
                self.toast_anim_timer = self.after(16, slide_down, step + 1)
            else:
                if self.toast_frame:
                    self.toast_frame.destroy()
                    self.toast_frame = None

        animate_up(0)

    def keep_selected(self, event=None):
        if hasattr(self, 'disarm_trash'): self.disarm_trash()
        if self.keep_selected_btn.cget("state") == "disabled": return
        if not self.selected_indices:
            messagebox.showwarning("Warning", "Please select at least one image to KEEP.")
            return
        
        cluster = self.clusters[self.current_cluster_idx]
        to_keep = [path for i, path in enumerate(cluster) if i in self.selected_indices]
        to_trash = [path for i, path in enumerate(cluster) if i not in self.selected_indices]
        
        self.move_to_deduplicated(to_keep)
        self.move_to_trash(to_trash)
        self.processed_clusters.add(self.current_cluster_idx)
        self.next_cluster()

    def keep_all(self, event=None):
        if hasattr(self, 'disarm_trash'): self.disarm_trash()
        if self.keep_all_btn.cget("state") == "disabled": return
        self.move_to_deduplicated(self.clusters[self.current_cluster_idx])
        self.processed_clusters.add(self.current_cluster_idx)
        self.next_cluster()

    def trash_all(self, event=None):
        if self.trash_all_btn.cget("state") == "disabled": return

        if not self.trash_armed:
            self.trash_armed = True
            self.trash_all_btn.configure(text="PRESS D AGAIN TO TRASH", fg_color="#ff0000", hover_color="#cc0000")
            self.trash_timer = self.after(3000, self.disarm_trash)
        else:
            if self.trash_timer is not None:
                self.after_cancel(self.trash_timer)
                self.trash_timer = None
            
            cluster = self.clusters[self.current_cluster_idx]
            self.move_to_trash(cluster)
            self.processed_clusters.add(self.current_cluster_idx)
            self.disarm_trash()
            self.next_cluster()

    def move_to_trash(self, paths):
        if not paths: return
        trash_dir = os.path.join(self.source_dir, "_Trash")
        os.makedirs(trash_dir, exist_ok=True)
        new_paths = []
        for p in paths:
            try:
                dest = os.path.join(trash_dir, os.path.basename(p))
                if os.path.exists(dest):
                    dest = os.path.join(trash_dir, f"{int(time.time())}_{os.path.basename(p)}")
                shutil.move(p, dest)
                new_paths.append((p, dest))
            except Exception as e:
                print(f"Error trashing {p}: {e}")
        self.update_cluster_paths(new_paths)
        if hasattr(self, 'show_toast'):
            self.show_toast(f"Moved {len(paths)} images to _Trash")

    def move_to_deduplicated(self, paths):
        if not paths: return
        dedupe_dir = os.path.join(self.source_dir, "deDuplicated")
        os.makedirs(dedupe_dir, exist_ok=True)
        new_paths = []
        for p in paths:
            try:
                dest = os.path.join(dedupe_dir, os.path.basename(p))
                if os.path.exists(dest):
                    dest = os.path.join(dedupe_dir, f"{int(time.time())}_{os.path.basename(p)}")
                shutil.move(p, dest)
                new_paths.append((p, dest))
            except Exception as e:
                print(f"Error moving {p} to deDuplicated: {e}")
        self.update_cluster_paths(new_paths)
        if hasattr(self, 'show_toast'):
            self.show_toast(f"Moved {len(paths)} images to deDuplicated")

if __name__ == "__main__":
    app = DedupeApp()
    app.mainloop()
