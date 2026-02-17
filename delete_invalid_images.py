import os

def delete_invalid_images(file_list_path, dry_run=True):
    """
    Deletes images listed in file_list_path.
    :param file_list_path: Path to the text file containing image paths.
    :param dry_run: If True, only print what would be deleted.
    """
    if not os.path.exists(file_list_path):
        print(f"Error: {file_list_path} not found.")
        return

    with open(file_list_path, 'r') as f:
        paths = [line.strip() for line in f if line.strip()]

    deleted_count = 0
    missing_count = 0
    error_count = 0

    print(f"{'DRY RUN: ' if dry_run else ''}Processing {len(paths)} files...")

    for path in paths:
        # Normalize path for Windows/Unix compatibility
        path = os.path.normpath(path)
        
        if os.path.exists(path):
            if dry_run:
                print(f"[DRY RUN] Would delete: {path}")
                deleted_count += 1
            else:
                try:
                    os.remove(path)
                    print(f"Deleted: {path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {path}: {e}")
                    error_count += 1
        else:
            print(f"File not found: {path}")
            missing_count += 1

    print("\nSummary:")
    print(f"{'Would be deleted' if dry_run else 'Deleted'}: {deleted_count}")
    print(f"Missing: {missing_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")

def scan_file_types(directory_path, output_file):
    """
    Scans the directory for unique file extensions and writes them to output_file.
    """
    if not os.path.isdir(directory_path):
        print(f"Error: {directory_path} is not a valid directory.")
        return

    extensions = set()
    for filename in os.listdir(directory_path):
        ext = os.path.splitext(filename)[1].lower()
        if ext:
            extensions.add(ext)
        else:
            extensions.add("(no extension)")

    with open(output_file, 'w') as f:
        for ext in sorted(extensions):
            f.write(f"{ext}\n")
    
    print(f"Found {len(extensions)} unique file types. Results written to {output_file}")

def delete_files_by_extension(directory_path, extensions, dry_run=True):
    """
    Deletes files in directory_path if their extension matches any in the extensions list exactly.
    """
    if not os.path.exists(directory_path):
        print(f"Error: {directory_path} not found.")
        return

    deleted_count = 0
    error_count = 0

    print(f"{'DRY RUN: ' if dry_run else ''}Deleting files with EXACT extensions: {extensions}")

    for filename in os.listdir(directory_path):
        path = os.path.join(directory_path, filename)
        if os.path.isfile(path):
            ext = os.path.splitext(filename)[1].lower()
            target_ext = ext if ext else "(no extension)"
            
            if target_ext in extensions:
                if dry_run:
                    print(f"[DRY RUN] Would delete: {path}")
                    deleted_count += 1
                else:
                    try:
                        os.remove(path)
                        print(f"Deleted: {path}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"Error deleting {path}: {e}")
                        error_count += 1

    print(f"\nSummary:")
    print(f"{'Would be deleted' if dry_run else 'Deleted'}: {deleted_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")

def get_extensions_from_file(file_path):
    """Reads extensions from a file, one per line."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return [line.strip().lower() for line in f if line.strip()]

if __name__ == "__main__":
    import sys
    
    INVALID_IMAGES_FILE = "invalid_images.txt"
    IMAGE_DIR = "downloaded_trypo"
    TYPES_FILE = "temp_file_types.txt"

    # Handle command line arguments
    args = sys.argv[1:]
    
    if "--scan" in args:
        print("--- Scanning File Types ---")
        scan_file_types(IMAGE_DIR, TYPES_FILE)
        print(f"File types written to {TYPES_FILE}. Please edit this file to select types for deletion.")
        print("---------------------------\n")
    
    elif "--delete-types" in args:
        # Step 2: Delete by extension if temp_file_types.txt exists
        extensions_to_delete = get_extensions_from_file(TYPES_FILE)
        if extensions_to_delete:
            print("--- Extension Deletion Start ---")
            delete_files_by_extension(IMAGE_DIR, extensions_to_delete, dry_run=True)
            print("--- Extension Deletion End ---\n")
            
            confirm = input(f"Are you sure you want to delete all files with these extensions in {IMAGE_DIR}? (y/N): ").lower()
            if confirm == 'y':
                delete_files_by_extension(IMAGE_DIR, extensions_to_delete, dry_run=False)
            else:
                print("Deletion by extension cancelled.")
        else:
            print(f"No extensions found in {TYPES_FILE}. Run with --scan first or add them manually.")

    elif "--delete-invalid" in args:
        # Step 3: Specific file deletion (if it exists)
        if os.path.exists(INVALID_IMAGES_FILE):
            print("\n--- Specific File Deletion Start (invalid_images.txt) ---")
            delete_invalid_images(INVALID_IMAGES_FILE, dry_run=True)
            print("--- Specific File Deletion End ---\n")
            
            confirm = input("Confirm deletion of specific files? (y/N): ").lower()
            if confirm == 'y':
                delete_invalid_images(INVALID_IMAGES_FILE, dry_run=False)
        else:
            print(f"{INVALID_IMAGES_FILE} not found.")

    else:
        print("Usage:")
        print("  python delete_invalid_images.py --scan           # Scan unique file types")
        print("  python delete_invalid_images.py --delete-types   # Delete files with extensions in temp_file_types.txt")
        print("  python delete_invalid_images.py --delete-invalid # Delete files listed in invalid_images.txt")
