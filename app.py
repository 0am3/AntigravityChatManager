import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading

import scanner
import manager

# Set Appearance
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

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

        self.btn_purge = ctk.CTkButton(self.top_frame, text="Purge Ghosts", fg_color="#C62828", hover_color="#8E0000", command=self.on_purge_ghosts_clicked)
        self.btn_purge.grid(row=0, column=2, sticky="e", padx=10)

        self.btn_restore = ctk.CTkButton(self.top_frame, text="Restore Session (.zip)", fg_color="#2A8C55", hover_color="#206A40", command=self.on_restore_clicked)
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

    def on_purge_ghosts_clicked(self):
        confirm = messagebox.askyesno("Confirm Purge", "This will scan your AntiGravity indexes and permanently remove any ghost chat profiles that no longer have data on disk.\n\nContinue?")
        if confirm:
            success, msg = manager.purge_ghost_profiles()
            if success:
                messagebox.showinfo("Success", msg)
            else:
                messagebox.showinfo("Info", msg)

if __name__ == "__main__":
    app = ChatManagerApp()
    app.mainloop()
