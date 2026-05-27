import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading

import scanner
import manager

# Set Appearance
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"


# ---------------------------------------------------------------------------
# Index Manager Window
# ---------------------------------------------------------------------------

class IndexManagerWindow(ctk.CTkToplevel):
    """
    A dedicated window that shows the full profile of the .pb sidebar index
    and allows the user to selectively remove individual entries.
    """

    # Status → display config
    STATUS_STYLES = {
        "valid":  {"text": "Valid",   "color": "#4CAF50"},
        "ghost":  {"text": "Ghost",  "color": "#FF9800"},
        "zeroed": {"text": "Zeroed", "color": "#F44336"},
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Sidebar Index Manager")
        self.geometry("860x560")
        self.minsize(780, 480)
        self.transient(parent)
        self.grab_set()

        # Track checkboxes for selective removal
        self._check_vars = []  # list of (ctk.BooleanVar, chat_id, status)

        # --- Layout ---
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(18, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="Sidebar Index Profile",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.btn_refresh = ctk.CTkButton(
            header, text="Refresh", width=90, command=self._load,
        )
        self.btn_refresh.grid(row=0, column=1, sticky="e")

        # Status summary bar
        self.summary_frame = ctk.CTkFrame(self, corner_radius=8)
        self.summary_frame.grid(row=1, column=0, padx=20, pady=(12, 0), sticky="ew")

        # Scrollable entry list
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=2, column=0, padx=20, pady=(12, 0), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        # Bottom action bar
        self.action_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.action_bar.grid(row=3, column=0, padx=20, pady=(10, 16), sticky="ew")
        self.action_bar.grid_columnconfigure(0, weight=1)

        self.btn_remove = ctk.CTkButton(
            self.action_bar,
            text="Remove Selected Entries",
            fg_color="#C62828",
            hover_color="#8E0000",
            state="disabled",
            command=self._on_remove,
        )
        self.btn_remove.grid(row=0, column=1, sticky="e")

        self.select_label = ctk.CTkLabel(
            self.action_bar, text="",
            font=ctk.CTkFont(size=12), text_color="gray",
        )
        self.select_label.grid(row=0, column=0, sticky="w")

        # Initial load
        self._load()

    # ----- data loading -----

    def _load(self):
        """Read the index and rebuild the entire UI."""
        self._check_vars.clear()
        for w in self.scroll.winfo_children():
            w.destroy()
        for w in self.summary_frame.winfo_children():
            w.destroy()

        status = manager.get_index_status()

        # --- summary bar ---
        if not status['exists']:
            ctk.CTkLabel(
                self.summary_frame,
                text="  Index file not found. AntiGravity has not created one yet.",
                text_color="#F44336",
                font=ctk.CTkFont(size=13),
            ).pack(padx=12, pady=8, anchor="w")
            self.btn_remove.configure(state="disabled")
            self._update_select_label()
            return

        size_kb = status['size_bytes'] / 1024
        summary_parts = [
            f"Entries: {status['total_entries']}",
            f"Valid: {status['valid_count']}",
            f"Ghosts: {status['ghost_count']}",
            f"Zeroed: {status['zeroed_count']}",
            f"Size: {size_kb:.1f} KB",
        ]

        row = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        row.pack(padx=12, pady=8, fill="x")

        for i, part in enumerate(summary_parts):
            # Color-code ghosts and zeroed counts
            color = "#E0E0E0"
            if "Ghosts" in part and status['ghost_count'] > 0:
                color = self.STATUS_STYLES["ghost"]["color"]
            elif "Zeroed" in part and status['zeroed_count'] > 0:
                color = self.STATUS_STYLES["zeroed"]["color"]
            elif "Valid" in part:
                color = self.STATUS_STYLES["valid"]["color"]

            lbl = ctk.CTkLabel(
                row, text=part, font=ctk.CTkFont(size=13, weight="bold"),
                text_color=color,
            )
            lbl.pack(side="left", padx=(0, 18))

        # Health indicator
        if status['ghost_count'] == 0 and status['zeroed_count'] == 0:
            health_text = "  Index is healthy"
            health_color = "#4CAF50"
        else:
            problems = []
            if status['ghost_count'] > 0:
                problems.append(f"{status['ghost_count']} ghost(s)")
            if status['zeroed_count'] > 0:
                problems.append(f"{status['zeroed_count']} corrupted")
            health_text = f"  Issues found: {', '.join(problems)}"
            health_color = "#FF9800"

        ctk.CTkLabel(
            self.summary_frame,
            text=health_text,
            font=ctk.CTkFont(size=12),
            text_color=health_color,
        ).pack(padx=12, pady=(0, 6), anchor="w")

        # --- entry cards ---
        if not status['entries']:
            ctk.CTkLabel(
                self.scroll, text="Index file is empty — no entries.",
                text_color="gray",
            ).pack(pady=20)
            self.btn_remove.configure(state="disabled")
            self._update_select_label()
            return

        for entry in status['entries']:
            self._create_entry_card(entry)

        self._update_select_label()

    # ----- per-entry card -----

    def _create_entry_card(self, entry):
        style = self.STATUS_STYLES.get(entry['status'], self.STATUS_STYLES["ghost"])

        card = ctk.CTkFrame(self.scroll, corner_radius=8)
        card.pack(fill="x", pady=3, padx=2)
        card.grid_columnconfigure(1, weight=1)

        # Checkbox
        var = ctk.BooleanVar(value=False)
        var.trace_add("write", lambda *_: self._update_select_label())
        self._check_vars.append((var, entry['chat_id'], entry['status']))

        chk = ctk.CTkCheckBox(
            card, text="", variable=var, width=24,
            checkbox_width=20, checkbox_height=20,
        )
        chk.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=8, sticky="n")

        # Info area
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=1, padx=(0, 8), pady=(8, 2), sticky="ew")
        info.grid_columnconfigure(0, weight=1)

        title_text = entry['title']
        if len(title_text) > 70:
            title_text = title_text[:67] + "..."

        ctk.CTkLabel(
            info, text=title_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E0E0E0",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        # Status badge
        badge = ctk.CTkLabel(
            info, text=f" {style['text']} ",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            fg_color=style['color'],
            corner_radius=4,
        )
        badge.grid(row=0, column=1, sticky="e", padx=(6, 0))

        # Subtitle row
        sub = ctk.CTkFrame(card, fg_color="transparent")
        sub.grid(row=1, column=1, padx=(0, 8), pady=(0, 8), sticky="ew")

        entry_kb = entry['entry_size'] / 1024
        ctk.CTkLabel(
            sub,
            text=f"ID: {entry['chat_id']}   |   Entry: {entry_kb:.1f} KB",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).pack(anchor="w")

    # ----- selection tracking -----

    def _get_selected(self):
        """Return list of (chat_id, status) for checked entries."""
        return [
            (cid, st)
            for var, cid, st in self._check_vars
            if var.get()
        ]

    def _update_select_label(self):
        selected = self._get_selected()
        n = len(selected)
        if n == 0:
            self.select_label.configure(text="No entries selected")
            self.btn_remove.configure(state="disabled")
        else:
            self.select_label.configure(text=f"{n} entry/entries selected")
            self.btn_remove.configure(state="normal")

    # ----- remove action -----

    def _on_remove(self):
        selected = self._get_selected()
        if not selected:
            return

        # Build confirmation message
        lines = []
        for cid, st in selected:
            # Find title
            title = "?"
            for var, vcid, vst in self._check_vars:
                if vcid == cid:
                    # Look up from entries
                    break
            lines.append(f"  [{st.upper()}]  {cid[:24]}...")

        msg = (
            f"You are about to remove {len(selected)} entry/entries from the "
            f"AntiGravity sidebar index.\n\n"
            f"A backup will be created automatically before modifying.\n\n"
            f"Selected entries:\n" + "\n".join(lines) + "\n\n"
            f"Continue?"
        )
        if not messagebox.askyesno("Confirm Removal", msg, parent=self):
            return

        ids = [cid for cid, _ in selected]
        success, result_msg = manager.remove_index_entries(ids)

        if success:
            messagebox.showinfo("Success", result_msg, parent=self)
            self._load()  # Refresh
        else:
            messagebox.showerror("Error", result_msg, parent=self)


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------

class ChatManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AntiGravity Chat Manager")
        self.geometry("800x600")
        self.minsize(800, 600)

        # Configure grid layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top Frame for Header and Global Actions
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(self.top_frame, text="AntiGravity Chat Manager", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        self.btn_refresh = ctk.CTkButton(self.top_frame, text="Refresh", width=100, command=self.load_chats)
        self.btn_refresh.grid(row=0, column=1, sticky="e", padx=10)

        self.btn_index = ctk.CTkButton(
            self.top_frame, text="Index Manager",
            fg_color="#5C6BC0", hover_color="#3949AB",
            command=self.on_index_manager_clicked,
        )
        self.btn_index.grid(row=0, column=2, sticky="e", padx=10)

        self.btn_restore = ctk.CTkButton(self.top_frame, text="Restore Session (.zip)", fg_color="#2A8C55", hover_color="##206A40", command=self.on_restore_clicked)
        self.btn_restore.grid(row=0, column=3, sticky="e")

        # Scrollable Frame for Chat List
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # Initial Load
        self.load_chats()

    def load_chats(self):
        # Clear existing
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.chats = scanner.scan_chats()
        
        if not self.chats:
            lbl = ctk.CTkLabel(self.scroll_frame, text="No chat sessions found in the brain directory.", text_color="gray")
            lbl.pack(pady=20)
            return

        for i, chat in enumerate(self.chats):
            self.create_chat_card(chat, i)

    def create_chat_card(self, chat, row):
        card = ctk.CTkFrame(self.scroll_frame, corner_radius=10)
        card.pack(fill="x", pady=5, padx=5)
        
        # Grid inside card
        card.grid_columnconfigure(0, weight=1)
        
        # Left side: Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        title_text = chat.get('title', 'Unknown Chat')
        title_lbl = ctk.CTkLabel(info_frame, text=title_text, font=ctk.CTkFont(weight="bold", size=16), text_color="#E0E0E0")
        title_lbl.pack(anchor="w")
        
        id_lbl = ctk.CTkLabel(info_frame, text=f"ID: {chat['id']}", font=ctk.CTkFont(size=11), text_color="gray")
        id_lbl.pack(anchor="w")
        
        mod_str = chat['modified_at'].strftime("%Y-%m-%d %H:%M:%S")
        meta_lbl = ctk.CTkLabel(info_frame, text=f"Size: {chat['size_formatted']}  |  Last Active: {mod_str}", text_color="gray")
        meta_lbl.pack(anchor="w")

        # Right side: Actions
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.grid(row=0, column=1, padx=15, pady=10, sticky="e")

        btn_package = ctk.CTkButton(actions_frame, text="Package", width=80, command=lambda c=chat: self.on_package_clicked(c))
        btn_package.pack(side="left", padx=5)

        btn_clean = ctk.CTkButton(actions_frame, text="Clean", width=80, fg_color="#C62828", hover_color="#8E0000", command=lambda c=chat: self.on_clean_clicked(c))
        btn_clean.pack(side="left", padx=5)

    def on_package_clicked(self, chat):
        output_dir = filedialog.askdirectory(title="Select Output Directory for Backup")
        if not output_dir:
            return
        
        success, msg = manager.package_chat(chat['id'], output_dir)
        if success:
            messagebox.showinfo("Success", msg)
        else:
            messagebox.showerror("Error", msg)

    def on_clean_clicked(self, chat):
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete session:\n{chat['id']}?\n\nThis action cannot be undone unless you have a backup.")
        if confirm:
            success, msg = manager.clean_chat(chat['id'])
            if success:
                messagebox.showinfo("Success", msg)
                self.load_chats()
            else:
                messagebox.showerror("Error", msg)

    def on_restore_clicked(self):
        zip_path = filedialog.askopenfilename(title="Select Chat Backup (.zip)", filetypes=[("Zip Files", "*.zip")])
        if not zip_path:
            return
        
        success, msg = manager.restore_chat(zip_path)
        if success:
            messagebox.showinfo("Success", msg)
            self.load_chats()
        else:
            messagebox.showerror("Error", msg)

    def on_index_manager_clicked(self):
        IndexManagerWindow(self)


if __name__ == "__main__":
    app = ChatManagerApp()
    app.mainloop()
