import os
import shutil
import zipfile
from pathlib import Path

def clean_chat(chat_path):
    """
    Deeply deletes a chat folder and all its contents.
    Returns True if successful, False otherwise.
    """
    if os.path.exists(chat_path) and os.path.isdir(chat_path):
        try:
            shutil.rmtree(chat_path)
            return True, "Chat successfully cleaned."
        except Exception as e:
            return False, f"Failed to clean chat: {e}"
    return False, "Chat path does not exist."

def package_chat(chat_id, chat_path, output_dir):
    """
    Zips a chat folder to the given output directory.
    Returns True and the zip path if successful, False otherwise.
    """
    if not os.path.exists(chat_path):
        return False, "Chat path does not exist."
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    zip_filename = f"{chat_id}_backup.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    try:
        # shutil.make_archive adds .zip to the base_name, so we remove it from the argument
        base_name = zip_path[:-4] if zip_path.endswith('.zip') else zip_path
        
        # We want the contents of the chat to be inside a folder named <chat_id> in the zip
        shutil.make_archive(base_name, 'zip', root_dir=os.path.dirname(chat_path), base_dir=os.path.basename(chat_path))
        return True, f"Packaged successfully at {zip_path}"
    except Exception as e:
        return False, f"Failed to package chat: {e}"

def restore_chat(zip_path, target_brain_path):
    """
    Restores a packaged chat (.zip) into the brain directory.
    Returns True if successful, False otherwise.
    """
    if not os.path.exists(zip_path):
        return False, "Zip file does not exist."
    
    if not zipfile.is_zipfile(zip_path):
        return False, "File is not a valid zip archive."

    try:
        shutil.unpack_archive(zip_path, extract_dir=target_brain_path, format='zip')
        return True, "Chat restored successfully."
    except Exception as e:
        return False, f"Failed to restore chat: {e}"
