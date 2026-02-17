import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import imagehash
import torch
from transformers import CLIPProcessor, CLIPModel
from threading import Thread
import concurrent.futures
import time

# --- Setup Aesthetics ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DuplicateDetector:
    def __init__(self, use_clip=True):
        self.use_clip = use_clip
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if use_clip:
            print("Loading CLIP model...")
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
    def get_phash(self, image_path):
        try:
            with Image.open(image_path) as img:
                return str(imagehash.phash(img))
        except Exception:
            return None

    def get_clip_embedding(self, image_path):
        try:
            with Image.open(image_path) as img:
                inputs = self.processor(images=img, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    outputs = self.model.get_image_features(**inputs)
                
                if isinstance(outputs, torch.Tensor):
                    return outputs.cpu().numpy().flatten()
                elif hasattr(outputs, "image_embeds"):
                    return outputs.image_embeds.cpu().numpy().flatten()
                elif hasattr(outputs, "pooler_output"):
                    return outputs.pooler_output.cpu().numpy().flatten()
                else:
                    try:
                        return outputs[0].cpu().numpy().flatten()
                    except:
                        return outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()
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
        self.image_objects = [] # To prevent GC
        self.selected_indices = set()
        self.source_dir = ""

        self._setup_ui()

    def _setup_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="Dedupe Tool", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(padx=20, pady=(20, 10))

        self.scan_button = ctk.CTkButton(self.sidebar, text="Scan Folder", command=self.select_folder)
        self.scan_button.pack(padx=20, pady=10)

        self.threshold_label = ctk.CTkLabel(self.sidebar, text="pHash Threshold (0-10)")
        self.threshold_label.pack(padx=20, pady=(20, 0))
        self.phash_threshold = ctk.CTkSlider(self.sidebar, from_=0, to=20, number_of_steps=20)
        self.phash_threshold.set(5)
        self.phash_threshold.pack(padx=20, pady=5)

        self.clip_var = tk.BooleanVar(value=True)
        self.clip_checkbox = ctk.CTkCheckBox(self.sidebar, text="Use CLIP (AI)", variable=self.clip_var)
        self.clip_checkbox.pack(padx=20, pady=20)

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
        self.header_label.pack(pady=10)

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

        self.keep_selected_btn = ctk.CTkButton(self.action_frame, text="Keep Selected & Trash Others", 
                                                command=self.keep_selected, state="disabled", fg_color="green", hover_color="#006400")
        self.keep_selected_btn.pack(side="left", padx=20, pady=20, expand=True)

        self.keep_all_btn = ctk.CTkButton(self.action_frame, text="Keep All (Move Next)", 
                                           command=self.keep_all, state="disabled")
        self.keep_all_btn.pack(side="left", padx=20, pady=20, expand=True)

        self.trash_all_btn = ctk.CTkButton(self.action_frame, text="Trash All", 
                                            command=self.trash_all, state="disabled", fg_color="red", hover_color="#8B0000")
        self.trash_all_btn.pack(side="left", padx=20, pady=20, expand=True)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_dir = folder
            self.start_scan_thread()

    def start_scan_thread(self):
        self.scan_button.configure(state="disabled")
        self.progress_label.configure(text="Scanning...")
        Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        if not self.detector or (self.detector.use_clip != self.clip_var.get()):
            self.detector = DuplicateDetector(use_clip=self.clip_var.get())

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

        # 2. Calculate CLIP Embeddings (Parallel Load + Batch Processing)
        if self.clip_var.get():
            batch_size = 256
            print(f"--- Starting hardware-accelerated CLIP scanning (batch size: {batch_size}) ---")
            
            # Use threads ONLY for the slow disk loading part
            def load_image_only(path):
                try:
                    with Image.open(path) as img:
                        # Pre-convert and pre-resize on CPU to save memory and speed up
                        img_rgb = img.convert("RGB")
                        img_rgb.thumbnail((250, 250)) 
                        return img_rgb, path
                except Exception as e:
                    print(f"  [DEBUG] Error loading {os.path.basename(path)}: {e}")
                    return None, path

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                for i in range(0, total, batch_size):
                    batch_files = files[i:i + batch_size]
                    
                    # 2a. Parallel Load from Disk (Disk/CPU bound)
                    results = list(executor.map(load_image_only, batch_files))
                    
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
                            # Processor is much faster when processing a list of images at once
                            inputs = self.detector.processor(images=batch_imgs, return_tensors="pt").to(self.detector.device)
                            
                            with torch.no_grad():
                                outputs = self.detector.model.get_image_features(**inputs)
                            
                            # Extremely robust extraction for different CLIP output formats
                            if isinstance(outputs, torch.Tensor):
                                batch_outputs = outputs.cpu().numpy()
                            elif hasattr(outputs, "image_embeds"):
                                batch_outputs = outputs.image_embeds.cpu().numpy()
                            elif hasattr(outputs, "pooler_output"):
                                batch_outputs = outputs.pooler_output.cpu().numpy()
                            else:
                                # Final fallback for dict-like or wrapped outputs
                                try:
                                    batch_outputs = outputs[0].cpu().numpy()
                                except:
                                    batch_outputs = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                            
                            for idx in range(len(batch_outputs)):
                                embeddings[valid_batch_paths[idx]] = batch_outputs[idx].flatten()
                            
                            print(f"CLIP Scan: Batch {i//batch_size + 1} | Processed {len(batch_outputs)} images")
                        except Exception as e:
                            print(f"  [CLIP Error] Batch {i//batch_size + 1} failed: {e}")
                            # Fallback: try images one by one if the whole batch crashed (unlikely but safe)
                    else:
                        print(f"CLIP Scan: Batch {i//batch_size + 1} | SKIPPED (No valid images in this block)")

                    # Update UI progress
                    self.progress_bar.set(0.5 + ((min(i + batch_size, total) / total) * 0.5))
                    self.after(0, lambda curr=min(i+batch_size, total), t=total: 
                               self.progress_label.configure(text=f"CLIP AI Scanning {curr}/{t}"))

            print(f"--- AI SCAN COMPLETE: Stored {len(embeddings)} embeddings ---")
            if len(embeddings) == 0:
                print("WARNING: CLIP AI found 0 valid images. Clustering will fall back to pHash only.")

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

        # 3b. Vectorized CLIP edges on GPU (The fast part)
        if self.clip_var.get() and embeddings:
            self.after(0, lambda: self.progress_label.configure(text="AI Clustering..."))
            print(f"Calculating GPU Similarity Matrix (Batched: 5000)...")
            emb_list = [embeddings.get(f, np.zeros(512)) for f in files]
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
        if self.clusters:
            self.current_cluster_idx = 0
            self.show_cluster()
        else:
            messagebox.showinfo("Scan Complete", "No duplicates found with current threshold.")

    def show_cluster(self):
        if self.current_cluster_idx >= len(self.clusters):
            messagebox.showinfo("Finished", "All duplicates have been reviewed!")
            self.header_label.configure(text="Review complete.")
            return

        # Clear grid (safely destroy only image containers)
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        
        self.image_objects = []
        self.selected_indices = set()
        
        cluster = self.clusters[self.current_cluster_idx]
        self.header_label.configure(text=f"Group {self.current_cluster_idx + 1} of {len(self.clusters)} (Found {len(cluster)} images)")

        # Enable Buttons
        self.keep_selected_btn.configure(state="normal")
        self.keep_all_btn.configure(state="normal")
        self.trash_all_btn.configure(state="normal")

        for i, path in enumerate(cluster):
            self.add_image_to_grid(path, i)

    def add_image_to_grid(self, path, idx):
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
            container.grid(row=idx // 3, column=idx % 3, padx=10, pady=10, sticky="nsew")

            # Image Label (Clickable)
            img_label = tk.Label(container, image=img, bg="#2b2b2b")
            img_label.pack(pady=5)
            img_label.bind("<Button-1>", lambda e, i=idx, c=container: self.toggle_selection(i, c))
            img_label.bind("<Button-3>", lambda e, p=path, c=container: self.on_right_click(p, c))

            # Info Labels
            info = f"{os.path.basename(path)}\n{res} | {size_kb:.1f} KB"
            ctk.CTkLabel(container, text=info, font=ctk.CTkFont(size=10)).pack()

        except Exception as e:
            print(f"Error loading {path}: {e}")

    def toggle_selection(self, idx, container):
        """Toggle blue tint and add to selected list."""
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
            container.configure(fg_color="transparent")
        else:
            self.selected_indices.add(idx)
            container.configure(fg_color="#1f538d") 

    def on_right_click(self, path, container):
        if messagebox.askyesno("Confirm Delete", f"Move {os.path.basename(path)} to trash?"):
            self.move_to_trash([path])
            # Remove from current cluster
            cluster = self.clusters[self.current_cluster_idx]
            if path in cluster:
                cluster.remove(path)
            
            # If cluster has <= 1 image, it's no longer a group of duplicates
            if len(cluster) <= 1:
                self.clusters.pop(self.current_cluster_idx)
                # Don't increment index, just show whatever is now at this index
                self.show_cluster()
            else:
                self.show_cluster()

    def keep_selected(self):
        if not self.selected_indices:
            messagebox.showwarning("Warning", "Please select at least one image to KEEP.")
            return
        
        cluster = self.clusters[self.current_cluster_idx]
        to_trash = [path for i, path in enumerate(cluster) if i not in self.selected_indices]
        
        self.move_to_trash(to_trash)
        self.next_cluster()

    def keep_all(self):
        self.next_cluster()

    def trash_all(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to trash ALL images in this group?"):
            self.move_to_trash(self.clusters[self.current_cluster_idx])
            self.next_cluster()

    def move_to_trash(self, paths):
        trash_dir = os.path.join(self.source_dir, "_Trash")
        os.makedirs(trash_dir, exist_ok=True)
        for p in paths:
            try:
                dest = os.path.join(trash_dir, os.path.basename(p))
                if os.path.exists(dest):
                    dest = os.path.join(trash_dir, f"{int(time.time())}_{os.path.basename(p)}")
                shutil.move(p, dest)
            except Exception as e:
                print(f"Error trashing {p}: {e}")

    def next_cluster(self):
        self.current_cluster_idx += 1
        self.show_cluster()

if __name__ == "__main__":
    app = DedupeApp()
    app.mainloop()
