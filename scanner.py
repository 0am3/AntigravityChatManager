import os
import json
import re
from datetime import datetime

def get_antigravity_root():
    """Returns the path to the AntiGravity root directory."""
    user_profile = os.environ.get('USERPROFILE')
    if not user_profile:
        user_profile = os.path.expanduser('~')
    return os.path.join(user_profile, '.gemini', 'antigravity')

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
    Scans the antigravity root directory dynamically and returns a list of dictionaries 
    containing metadata and globally aggregated sizes for each chat session.
    """
    ag_root = get_antigravity_root()
    brain_path = os.path.join(ag_root, 'brain')
    chats = {}

    if not os.path.exists(brain_path):
        return []

    # Initialize known chats from the brain directory (the core of every session)
    for item in os.listdir(brain_path):
        item_path = os.path.join(brain_path, item)
        if os.path.isdir(item_path):
            chats[item] = {
                'id': item,
                'path': item_path,
                'title': 'Unknown Chat',
                'created_at': datetime.fromtimestamp(os.stat(item_path).st_ctime),
                'modified_at': datetime.fromtimestamp(os.stat(item_path).st_mtime),
                'size_bytes': 0,
                'has_transcript': False
            }

            transcript_path = os.path.join(item_path, '.system_generated', 'logs', 'transcript.jsonl')
            if os.path.exists(transcript_path):
                chats[item]['has_transcript'] = True
                chats[item]['modified_at'] = datetime.fromtimestamp(os.stat(transcript_path).st_mtime)
                chats[item]['title'] = get_chat_title(transcript_path)

    # Single global walk across all AntiGravity subdirectories to aggregate exact file sizes
    for root, dirs, files in os.walk(ag_root):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.islink(fp):
                continue
            
            try:
                size = os.path.getsize(fp)
            except Exception:
                continue
            
            # Check if this file belongs to any known chat
            for cid in chats:
                # If the cid is in the file name OR in the directory path
                if cid in f or cid in root:
                    chats[cid]['size_bytes'] += size
                    break # A file can only belong to one cid
                    
    chat_list = list(chats.values())
    for c in chat_list:
        c['size_formatted'] = format_size(c['size_bytes'])

    # Sort chats by modification time, newest first
    chat_list.sort(key=lambda x: x['modified_at'], reverse=True)
    return chat_list

if __name__ == "__main__":
    # Test the scanner
    chats = scan_chats()
    print(f"Found {len(chats)} chats.")
    for c in chats:
        print(f"[{c['id']}] {c['title']} | Global Size: {c['size_formatted']} | Modified: {c['modified_at']}")
