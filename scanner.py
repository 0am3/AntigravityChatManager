import os
import json
import re
from pathlib import Path
from datetime import datetime

def get_brain_path():
    """Returns the path to the AntiGravity brain directory."""
    user_profile = os.environ.get('USERPROFILE')
    if not user_profile:
        # Fallback if USERPROFILE is not set for some reason
        user_profile = os.path.expanduser('~')
    return os.path.join(user_profile, '.gemini', 'antigravity', 'brain')

def get_dir_size(path):
    """Calculates the total size of a directory in bytes."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def format_size(size_bytes):
    """Formats bytes into a human-readable string."""
    if size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_names[i]}"

def get_chat_title(transcript_path):
    """Extracts a short title from the first user request in the transcript."""
    if not os.path.exists(transcript_path):
        return "Unknown Chat"
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get('type') == 'USER_INPUT':
                        content = data.get('content', '')
                        match = re.search(r'<USER_REQUEST>(.*?)</USER_REQUEST>', content, re.DOTALL)
                        if match:
                            text = match.group(1).strip()
                        else:
                            text = content.strip()
                        
                        text = " ".join(text.split())
                        if not text:
                            return "Empty Chat"
                        
                        if len(text) > 60:
                            return text[:57] + "..."
                        return text
                except Exception:
                    continue
    except Exception:
        pass
    return "Unknown Chat"

def scan_chats():
    """
    Scans the brain directory and returns a list of dictionaries 
    containing metadata for each chat session.
    """
    brain_path = get_brain_path()
    chats = []

    if not os.path.exists(brain_path):
        return chats

    # Iterate through folders in the brain path
    for item in os.listdir(brain_path):
        item_path = os.path.join(brain_path, item)
        
        # We only care about directories (each directory is a conversation-id)
        if os.path.isdir(item_path):
            try:
                # Basic stats
                stat = os.stat(item_path)
                created_time = datetime.fromtimestamp(stat.st_ctime)
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                
                # Check for transcript.jsonl to get more accurate modification time
                transcript_path = os.path.join(item_path, '.system_generated', 'logs', 'transcript.jsonl')
                has_transcript = os.path.exists(transcript_path)
                
                title = "Unknown Chat"
                if has_transcript:
                    transcript_stat = os.stat(transcript_path)
                    modified_time = datetime.fromtimestamp(transcript_stat.st_mtime)
                    title = get_chat_title(transcript_path)

                # Get directory size
                total_size_bytes = get_dir_size(item_path)
                
                chats.append({
                    'id': item,
                    'title': title,
                    'path': item_path,
                    'created_at': created_time,
                    'modified_at': modified_time,
                    'size_bytes': total_size_bytes,
                    'size_formatted': format_size(total_size_bytes),
                    'has_transcript': has_transcript
                })
            except Exception as e:
                print(f"Error reading {item}: {e}")
                continue

    # Sort chats by modification time, newest first
    chats.sort(key=lambda x: x['modified_at'], reverse=True)
    return chats

if __name__ == "__main__":
    # Test the scanner
    chats = scan_chats()
    print(f"Found {len(chats)} chats.")
    for c in chats:
        print(f"[{c['id']}] {c['title']} | Size: {c['size_formatted']} | Modified: {c['modified_at']}")
