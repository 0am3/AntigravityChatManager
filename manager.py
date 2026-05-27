import os
import shutil
import zipfile
import scanner
import pb_utils


def _get_pb_path():
    """Return the path to the agyhub_summaries_proto.pb index file."""
    return os.path.join(scanner.get_antigravity_root(), "agyhub_summaries_proto.pb")


def get_index_status():
    """
    Reads the .pb sidebar index and returns a full profile of its contents.

    Returns a dict with:
        'exists':       bool    — whether the .pb file exists
        'path':         str     — absolute path to the .pb file
        'size_bytes':   int     — file size in bytes
        'total_entries': int    — number of entries in the index
        'valid_count':  int     — entries with a matching brain directory
        'ghost_count':  int     — entries with no matching brain directory
        'zeroed_count': int     — entries whose chat_id is all-zeros (corrupted)
        'entries':      list    — per-entry details, each a dict:
            'chat_id':  str
            'title':    str
            'status':   str     — one of 'valid', 'ghost', 'zeroed'
            'entry_size': int   — byte size of this entry in the .pb file
    """
    pb_path = _get_pb_path()

    result = {
        'exists': False,
        'path': pb_path,
        'size_bytes': 0,
        'total_entries': 0,
        'valid_count': 0,
        'ghost_count': 0,
        'zeroed_count': 0,
        'entries': [],
    }

    if not os.path.isfile(pb_path):
        return result

    result['exists'] = True
    result['size_bytes'] = os.path.getsize(pb_path)

    # Collect valid chat IDs from the brain directory
    valid_chats = {chat['id'] for chat in scanner.scan_chats()}

    with open(pb_path, 'rb') as f:
        data = f.read()

    entries, _ = pb_utils.parse_pb_entries(data)
    result['total_entries'] = len(entries)

    zero_uuid = "00000000-0000-0000-0000-000000000000"

    for entry in entries:
        cid = pb_utils.get_entry_chat_id(entry["raw"])
        title = pb_utils.get_entry_title(entry["raw"])
        entry_size = len(entry["full_raw"])

        if cid == zero_uuid or cid is None:
            status = "zeroed"
            result['zeroed_count'] += 1
        elif cid in valid_chats:
            status = "valid"
            result['valid_count'] += 1
        else:
            status = "ghost"
            result['ghost_count'] += 1

        result['entries'].append({
            'chat_id': cid or zero_uuid,
            'title': title,
            'status': status,
            'entry_size': entry_size,
        })

    return result


def remove_index_entries(chat_ids_to_remove):
    """
    Selectively remove specific entries from the .pb sidebar index.

    This is user-driven — only the entries explicitly selected by the user
    are removed. A backup is always created before writing.

    Returns (success, message).
    """
    pb_path = _get_pb_path()
    if not os.path.isfile(pb_path):
        return False, "No index file found."

    with open(pb_path, 'rb') as f:
        data = f.read()

    new_data, removed = pb_utils.rebuild_pb_without_entries(data, chat_ids_to_remove)

    if not removed:
        return False, "None of the selected entries were found in the index."

    backup_path = pb_utils.safe_write_pb(pb_path, new_data)

    titles = [f'"{r["title"]}"' for r in removed]
    return True, (
        f"Removed {len(removed)} entry/entries from sidebar index:\n"
        + "\n".join(f"  - {t}" for t in titles)
        + f"\n\nBackup saved to:\n{backup_path}"
    )


def clean_chat(chat_id):
    """
    Deletes all files/folders belonging to a chat session AND removes its
    entry from the .pb index file.

    This is SAFE because:
    - The .pb modification uses entry-aware parsing (pb_utils)
    - It removes only the ONE entry matching the target chat_id
    - A backup is created before any .pb write
    - File/folder deletion only targets paths containing the chat_id
    """
    ag_root = scanner.get_antigravity_root()
    deleted_count = 0
    removed_title = None

    # --- Step 1: Surgically remove the entry from the .pb index ---
    pb_path = _get_pb_path()
    if os.path.isfile(pb_path):
        with open(pb_path, 'rb') as f:
            data = f.read()

        new_data, removed = pb_utils.rebuild_pb_without_entries(data, chat_id)

        if removed:
            pb_utils.safe_write_pb(pb_path, new_data)
            removed_title = removed[0]["title"]
            deleted_count += 1

    # --- Step 2: Delete files and directories containing the chat_id ---
    # Walk bottom-up so we can safely delete directories
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
        msg = f"Session cleaned. {deleted_count} item(s) removed."
        if removed_title:
            msg += f'\nRemoved "{removed_title}" from sidebar index.'
        return True, msg
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
