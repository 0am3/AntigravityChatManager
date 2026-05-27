"""
pb_utils.py — Safe protobuf wire format utilities for agyhub_summaries_proto.pb

This module provides entry-aware parsing of the AntiGravity summaries protobuf file.
It treats each top-level field-1 message as an atomic "entry" and never modifies
individual bytes within an entry. Operations are always: parse → filter → reassemble.

Wire format reference:
  - The .pb file is a sequence of top-level field-1 (wire type 2 / length-delimited) messages.
  - Each entry has the structure:
      field 1 (string): chat_id (UUID)
      field 2 (message): metadata containing:
          field 1 (string): title
          field 2 (varint): message count
          field 3 (message): timestamp
          field 4 (string): parent/project UUID
          ... other fields ...
"""

import os
import re
import shutil
from datetime import datetime


# ---------------------------------------------------------------------------
# Low-level wire format helpers
# ---------------------------------------------------------------------------

def _read_varint(data, pos):
    """Read a protobuf varint starting at *pos*. Returns (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _skip_field(data, pos, wire_type):
    """Advance *pos* past one field value of the given *wire_type*."""
    if wire_type == 0:          # varint
        _, pos = _read_varint(data, pos)
    elif wire_type == 1:        # 64-bit fixed
        pos += 8
    elif wire_type == 2:        # length-delimited
        length, pos = _read_varint(data, pos)
        pos += length
    elif wire_type == 5:        # 32-bit fixed
        pos += 4
    else:
        raise ValueError(f"Unknown wire type {wire_type} at pos {pos}")
    return pos


# ---------------------------------------------------------------------------
# Entry-level parsing
# ---------------------------------------------------------------------------

def parse_pb_entries(data):
    """
    Parse the raw bytes of agyhub_summaries_proto.pb into a list of entries.

    Each entry is returned as a dict:
        {
            "raw":      bytes,   # the complete raw bytes of the inner message
            "offset":   int,     # byte offset of the tag in the original data
            "end":      int,     # byte offset just past this entry
        }

    Only top-level field-1 (length-delimited) messages are considered entries.
    Any other top-level fields are preserved as-is in a separate "preamble" list.

    Returns (entries, other_chunks) where other_chunks is a list of raw byte
    segments for any non-field-1 top-level data (there usually are none).
    """
    entries = []
    other_chunks = []
    pos = 0

    while pos < len(data):
        start = pos
        try:
            tag, pos = _read_varint(data, pos)
        except Exception:
            # Trailing garbage — keep it as-is
            other_chunks.append(data[start:])
            break

        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, pos = _read_varint(data, pos)
            end = pos + length
            if end > len(data):
                # Truncated — preserve raw bytes
                other_chunks.append(data[start:])
                break
            inner = data[pos:end]
            pos = end

            if field_num == 1:
                entries.append({
                    "raw": inner,
                    "offset": start,
                    "end": end,
                    "full_raw": data[start:end],  # includes tag + length prefix
                })
            else:
                other_chunks.append(data[start:end])
        else:
            try:
                pos = _skip_field(data, pos, wire_type)
                other_chunks.append(data[start:pos])
            except Exception:
                other_chunks.append(data[start:])
                break

    return entries, other_chunks


def get_entry_chat_id(entry_raw):
    """
    Extract the chat UUID string from field 1 of an entry's inner message.

    The entry structure is:
        field 1 (string): chat_id
        field 2 (message): metadata
        ...

    Returns the UUID string, or None if it cannot be parsed.
    """
    pos = 0
    while pos < len(entry_raw):
        try:
            tag, pos = _read_varint(entry_raw, pos)
        except Exception:
            return None

        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, pos = _read_varint(entry_raw, pos)
            if field_num == 1:
                try:
                    return entry_raw[pos:pos + length].decode("utf-8")
                except Exception:
                    return None
            pos += length
        else:
            try:
                pos = _skip_field(entry_raw, pos, wire_type)
            except Exception:
                return None

    return None


def get_entry_title(entry_raw):
    """
    Extract the title string from field 2 → field 1 of an entry.

    Returns the title string, or "Unknown" if it cannot be parsed.
    """
    pos = 0
    while pos < len(entry_raw):
        try:
            tag, pos = _read_varint(entry_raw, pos)
        except Exception:
            return "Unknown"

        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, pos = _read_varint(entry_raw, pos)
            if field_num == 2:
                # Parse the inner metadata message for its field 1
                inner = entry_raw[pos:pos + length]
                return _extract_first_string(inner)
            pos += length
        else:
            try:
                pos = _skip_field(entry_raw, pos, wire_type)
            except Exception:
                return "Unknown"

    return "Unknown"


def _extract_first_string(data):
    """Extract field 1 (string) from a sub-message."""
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _read_varint(data, pos)
        except Exception:
            return "Unknown"

        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, pos = _read_varint(data, pos)
            if field_num == 1:
                try:
                    return data[pos:pos + length].decode("utf-8")
                except Exception:
                    return "Unknown"
            pos += length
        else:
            try:
                pos = _skip_field(data, pos, wire_type)
            except Exception:
                return "Unknown"

    return "Unknown"


# ---------------------------------------------------------------------------
# Safe modification operations
# ---------------------------------------------------------------------------

def _encode_varint(value):
    """Encode an integer as a protobuf varint."""
    parts = []
    while value > 0x7F:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.append(value & 0x7F)
    return bytes(parts)


def _wrap_as_field1(inner_bytes):
    """Wrap raw inner bytes as a top-level field-1 length-delimited message."""
    tag = _encode_varint((1 << 3) | 2)  # field 1, wire type 2
    length = _encode_varint(len(inner_bytes))
    return tag + length + inner_bytes


def rebuild_pb_without_entries(data, chat_ids_to_remove):
    """
    Parse *data*, remove all entries whose chat_id is in *chat_ids_to_remove*,
    and return the reassembled bytes.

    This is the SAFE way to remove a chat from the index — it removes the
    complete entry as an atomic unit, never touching individual UUID bytes.

    Returns (new_data, removed_entries) where removed_entries is a list of
    dicts with 'chat_id' and 'title' for logging.
    """
    if isinstance(chat_ids_to_remove, str):
        chat_ids_to_remove = {chat_ids_to_remove}
    else:
        chat_ids_to_remove = set(chat_ids_to_remove)

    entries, other_chunks = parse_pb_entries(data)
    kept = []
    removed = []

    for entry in entries:
        cid = get_entry_chat_id(entry["raw"])
        if cid in chat_ids_to_remove:
            removed.append({
                "chat_id": cid,
                "title": get_entry_title(entry["raw"]),
            })
        else:
            kept.append(entry)

    # Reassemble: other_chunks first (usually empty), then kept entries
    parts = list(other_chunks)
    for entry in kept:
        parts.append(entry["full_raw"])

    return b"".join(parts), removed


def list_pb_entries(data):
    """
    Return a list of (chat_id, title) for every entry in the .pb file.
    Useful for diagnostics and UI display.
    """
    entries, _ = parse_pb_entries(data)
    result = []
    for entry in entries:
        cid = get_entry_chat_id(entry["raw"])
        title = get_entry_title(entry["raw"])
        result.append((cid, title))
    return result


# ---------------------------------------------------------------------------
# Safe file I/O with backup
# ---------------------------------------------------------------------------

def backup_pb_file(pb_path):
    """
    Create a timestamped backup of the .pb file before any modification.
    Returns the backup path, or None if the source doesn't exist.
    """
    if not os.path.isfile(pb_path):
        return None

    backup_dir = os.path.join(os.path.dirname(pb_path), ".pb_backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"agyhub_summaries_proto_{timestamp}.pb.bak"
    backup_path = os.path.join(backup_dir, backup_name)

    shutil.copy2(pb_path, backup_path)
    return backup_path


def safe_write_pb(pb_path, new_data):
    """
    Safely write new .pb data:
    1. Create a timestamped backup of the existing file
    2. Write new data to a temp file
    3. Atomically replace the original

    Returns the backup path.
    """
    backup_path = backup_pb_file(pb_path)

    tmp_path = pb_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(new_data)

    # On Windows, os.replace is atomic if on the same volume
    os.replace(tmp_path, pb_path)

    return backup_path
