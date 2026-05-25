import os
import shutil
import zipfile
import scanner

def clean_chat(chat_id):
    """
    Globally walks the AntiGravity root and deletes ANY file or folder 
    containing the chat_id, ensuring no ghost data is left behind.
    """
    ag_root = scanner.get_antigravity_root()
    deleted_count = 0
    
    # Surgical index purging: Overwrite the chat_id in global protobuf indexes
    # to safely remove it from the left-side bar without corrupting the file structure.
    zero_uuid = b"00000000-0000-0000-0000-000000000000"
    target_uuid = chat_id.encode('utf-8')
    
    for filename in os.listdir(ag_root):
        if filename.endswith(".pb") or filename.endswith(".pbtxt"):
            filepath = os.path.join(ag_root, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    if target_uuid in content:
                        new_content = content.replace(target_uuid, zero_uuid)
                        with open(filepath, 'wb') as f:
                            f.write(new_content)
                        deleted_count += 1
                except Exception:
                    pass
    
    # We walk bottom-up so we can safely delete directories without breaking the walk
    for root, dirs, files in os.walk(ag_root, topdown=False):
        for f in files:
            if chat_id in f or chat_id in root:
                fp = os.path.join(root, f)
                try:
                    os.remove(fp)
                    deleted_count += 1
                except Exception:
                    pass
        
        for d in dirs:
            if chat_id in d:
                dp = os.path.join(root, d)
                try:
                    shutil.rmtree(dp)
                    deleted_count += 1
                except Exception:
                    pass
                    
    if deleted_count > 0:
        return True, f"Session thoroughly purged. {deleted_count} scattered artifacts removed."
    return False, "No data found to clean."

def package_chat(chat_id, output_dir):
    """
    Globally packages all files related to the chat_id from anywhere inside 
    the AntiGravity root into a structured zip file.
    """
    ag_root = scanner.get_antigravity_root()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    zip_filename = f"{chat_id}_global_backup.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            files_added = 0
            for root, dirs, files in os.walk(ag_root):
                for f in files:
                    if chat_id in f or chat_id in root:
                        fp = os.path.join(root, f)
                        # The arcname is the relative path from the antigravity root
                        arcname = os.path.relpath(fp, ag_root)
                        zipf.write(fp, arcname)
                        files_added += 1
                        
        if files_added > 0:
            return True, f"Global package successful! {files_added} artifacts safely archived at {zip_path}"
        else:
            return False, "No files found to package for this session."
    except Exception as e:
        return False, f"Failed to package session: {e}"

def restore_chat(zip_path):
    """
    Restores a globally packaged zip file directly into the AntiGravity root.
    """
    ag_root = scanner.get_antigravity_root()
    
    if not os.path.exists(zip_path):
        return False, "Zip file does not exist."
    
    if not zipfile.is_zipfile(zip_path):
        return False, "File is not a valid zip archive."

    try:
        # Extract directly into the antigravity root to mirror the saved structure
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(path=ag_root)
        return True, "Session fully restored across all global directories!"
    except Exception as e:
        return False, f"Failed to restore session: {e}"
