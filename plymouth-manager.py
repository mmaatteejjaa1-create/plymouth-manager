#!/usr/bin/env python3
"""
Plymouth Theme Manager
- Drag & drop any archive (ZIP, tar.gz, tar.bz2, tar.xz, tar)
- Auto-detects install.sh or falls back to manual install
- Remembers installed themes (JSON database)
- One-click activation
- Disable boot splash entirely
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import json
import zipfile
import tarfile
import shutil
import tempfile
import threading

DB_FILE = os.path.expanduser("~/.plymouth-manager.json")
THEMES_DIR = "/usr/share/plymouth/themes"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"themes": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def get_current_theme():
    try:
        r = subprocess.run(["plymouth-set-default-theme"], capture_output=True, text=True)
        return r.stdout.strip()
    except:
        return ""

def get_installed_plymouth_themes():
    themes = []
    if os.path.isdir(THEMES_DIR):
        for name in os.listdir(THEMES_DIR):
            path = os.path.join(THEMES_DIR, name)
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.endswith(".plymouth"):
                        themes.append(name)
                        break
    return themes

def find_install_sh(extract_dir):
    for root, dirs, files in os.walk(extract_dir):
        for f in files:
            if f == "install.sh":
                return os.path.join(root, f)
    return None

def find_plymouth_file(extract_dir):
    for root, dirs, files in os.walk(extract_dir):
        for f in files:
            if f.endswith(".plymouth"):
                return root, f[:-len(".plymouth")]
    return None, None

def extract_archive(path, dest, log_cb):
    name_lower = path.lower()
    try:
        if name_lower.endswith(".zip"):
            log_cb("📦 Extracting ZIP...")
            with zipfile.ZipFile(path, 'r') as z:
                z.extractall(dest)
            return True
        elif any(name_lower.endswith(e) for e in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
            log_cb("📦 Extracting TAR archive...")
            with tarfile.open(path, 'r:*') as t:
                t.extractall(dest)
            return True
        else:
            # Auto-detect
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    z.extractall(dest)
                log_cb("📦 Detected and extracted as ZIP...")
                return True
            except zipfile.BadZipFile:
                pass
            if tarfile.is_tarfile(path):
                with tarfile.open(path, 'r:*') as t:
                    t.extractall(dest)
                log_cb("📦 Detected and extracted as TAR...")
                return True
            return False
    except Exception as e:
        log_cb(f"❌ Extraction error: {e}")
        return False

def install_theme(file_path, log_cb):
    extract_dir = tempfile.mkdtemp(prefix="plymouth-")
    try:
        ok = extract_archive(file_path, extract_dir, log_cb)
        if not ok:
            return None, False, "Unsupported format! Use ZIP, tar.gz, tar.bz2 or tar.xz"

        install_sh = find_install_sh(extract_dir)
        theme_dir_path, theme_name = find_plymouth_file(extract_dir)

        if not theme_name:
            return None, False, "No .plymouth file found in archive!"

        dest = os.path.join(THEMES_DIR, theme_name)
        if os.path.isdir(dest):
            log_cb(f"✅ Theme '{theme_name}' already installed, skipping copy.")
            return theme_name, True, "already_installed"

        if install_sh:
            log_cb("🔧 Found install.sh, using it...")
            install_dir = os.path.dirname(install_sh)
            result = subprocess.run(
                ["pkexec", "bash", install_sh, "install"],
                capture_output=True, text=True,
                cwd=install_dir
            )
            if result.returncode == 0:
                log_cb("✅ Installed via install.sh")
                return theme_name, True, "installed"
            else:
                log_cb("⚠️  install.sh failed, trying manual install...")

        log_cb(f"📁 Copying files to {THEMES_DIR}/{theme_name} ...")
        copy_script = f"""
import shutil, os
src = '{theme_dir_path}'
dst = '{dest}'
shutil.copytree(src, dst)
for root, dirs, files in os.walk(dst):
    for d in dirs:
        os.chmod(os.path.join(root, d), 0o755)
    for f in files:
        os.chmod(os.path.join(root, f), 0o644)
"""
        result = subprocess.run(
            ["pkexec", "python3", "-c", copy_script],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return theme_name, False, f"Copy error: {result.stderr}"

        log_cb(f"✅ Theme '{theme_name}' installed!")
        return theme_name, True, "installed"

    except Exception as e:
        return None, False, str(e)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

def activate_theme(theme_name, log_cb):
    log_cb(f"🚀 Activating '{theme_name}' and rebuilding initramfs...")
    result = subprocess.run(
        ["pkexec", "plymouth-set-default-theme", "-R", theme_name],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log_cb("✅ Theme activated! Reboot to see it.")
        return True
    else:
        log_cb(f"❌ Error: {result.stderr or result.stdout}")
        return False

def remove_theme(theme_name, log_cb):
    result = subprocess.run(
        ["pkexec", "rm", "-rf", os.path.join(THEMES_DIR, theme_name)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log_cb(f"🗑️  Theme '{theme_name}' removed.")
        return True
    else:
        log_cb(f"❌ Error: {result.stderr}")
        return False

def disable_splash(log_cb):
    log_cb("🔇 Disabling boot splash (switching to text theme)...")
    result = subprocess.run(
        ["pkexec", "plymouth-set-default-theme", "-R", "text"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log_cb("✅ Boot splash disabled. Reboot to apply.")
        return True
    else:
        log_cb(f"❌ Error: {result.stderr or result.stdout}")
        return False

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Plymouth Theme Manager")
        self.configure(bg="#0d1117")
        self.geometry("700x600")
        self.resizable(True, True)
        self.db = load_db()
        self._build_ui()
        self._sync_with_system()
        self._refresh_list()

    def _build_ui(self):
        hdr = tk.Frame(self, bg="#0d1117")
        hdr.pack(fill="x", padx=20, pady=(18, 0))
        tk.Label(hdr, text="Plymouth Theme Manager",
                 bg="#0d1117", fg="#e6edf3",
                 font=("monospace", 17, "bold")).pack(side="left")

        drop_frame = tk.Frame(self, bg="#161b22", bd=0,
                              highlightbackground="#30363d", highlightthickness=1)
        drop_frame.pack(fill="x", padx=20, pady=14)

        self.drop_label = tk.Label(
            drop_frame,
            text="⬇  Drop theme archive here  or  click to browse",
            bg="#161b22", fg="#8b949e",
            font=("monospace", 10),
            pady=22, cursor="hand2"
        )
        self.drop_label.pack(fill="x")
        self.drop_label.bind("<Button-1>", self._browse_file)
        self.drop_label.bind("<Enter>", lambda e: self.drop_label.config(fg="#1793d1"))
        self.drop_label.bind("<Leave>", lambda e: self.drop_label.config(fg="#8b949e"))

        try:
            self.drop_label.drop_target_register("DND_Files")  # type: ignore
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore
        except:
            pass

        tk.Frame(self, bg="#30363d", height=1).pack(fill="x", padx=20)

        list_frame = tk.Frame(self, bg="#0d1117")
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        tk.Label(list_frame, text="Installed themes",
                 bg="#0d1117", fg="#8b949e",
                 font=("monospace", 9, "bold")).pack(anchor="w", pady=(0, 6))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#161b22", foreground="#e6edf3",
                        rowheight=36, fieldbackground="#161b22",
                        bordercolor="#30363d", font=("monospace", 10))
        style.configure("Treeview.Heading",
                        background="#21262d", foreground="#8b949e",
                        font=("monospace", 9, "bold"))
        style.map("Treeview", background=[("selected", "#1793d1")],
                  foreground=[("selected", "#ffffff")])

        cols = ("status", "name", "source")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("status", text="")
        self.tree.heading("name", text="Theme name")
        self.tree.heading("source", text="Source")
        self.tree.column("status", width=36, anchor="center", stretch=False)
        self.tree.column("name", width=300)
        self.tree.column("source", width=220)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btn_frame = tk.Frame(self, bg="#0d1117")
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.btn_activate = tk.Button(
            btn_frame, text="⚡ Activate", bg="#1793d1", fg="#ffffff",
            font=("monospace", 10, "bold"), relief="flat", padx=14, pady=8,
            cursor="hand2", activebackground="#2aa8f0",
            command=self._activate_selected
        )
        self.btn_activate.pack(side="left", padx=(0, 6))

        self.btn_remove = tk.Button(
            btn_frame, text="🗑  Remove", bg="#21262d", fg="#ff6b6b",
            font=("monospace", 10), relief="flat", padx=14, pady=8,
            cursor="hand2", activebackground="#30363d",
            command=self._remove_selected
        )
        self.btn_remove.pack(side="left", padx=(0, 6))

        self.btn_disable = tk.Button(
            btn_frame, text="🔇 Disable splash", bg="#21262d", fg="#f0a500",
            font=("monospace", 10), relief="flat", padx=14, pady=8,
            cursor="hand2", activebackground="#30363d",
            command=self._disable_splash
        )
        self.btn_disable.pack(side="left")

        self.btn_refresh = tk.Button(
            btn_frame, text="↻ Refresh", bg="#21262d", fg="#8b949e",
            font=("monospace", 10), relief="flat", padx=14, pady=8,
            cursor="hand2", activebackground="#30363d",
            command=self._sync_and_refresh
        )
        self.btn_refresh.pack(side="right")

        tk.Frame(self, bg="#30363d", height=1).pack(fill="x", padx=20)

        log_frame = tk.Frame(self, bg="#0d1117")
        log_frame.pack(fill="x", padx=20, pady=(6, 14))

        self.log_var = tk.StringVar(value="Ready.")
        tk.Label(log_frame, textvariable=self.log_var,
                 bg="#0d1117", fg="#3fb950",
                 font=("monospace", 9),
                 anchor="w", wraplength=660).pack(fill="x")

    def _log(self, msg):
        self.log_var.set(msg)
        self.update_idletasks()

    def _sync_with_system(self):
        installed = get_installed_plymouth_themes()
        db_themes = self.db.get("themes", {})
        for t in installed:
            if t not in db_themes:
                db_themes[t] = {"source": "system", "zip": None}
        to_remove = [k for k in db_themes if k not in installed]
        for k in to_remove:
            del db_themes[k]
        self.db["themes"] = db_themes
        save_db(self.db)

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        current = get_current_theme()
        for name, info in self.db.get("themes", {}).items():
            status = "★" if name == current else ""
            source = info.get("source", "system")
            self.tree.insert("", "end", iid=name, values=(status, name, source))
        self._log(f"Active theme: {current or 'none / splash disabled'}")

    def _sync_and_refresh(self):
        self._sync_with_system()
        self._refresh_list()

    def _browse_file(self, event=None):
        path = filedialog.askopenfilename(
            title="Select theme archive",
            filetypes=[
                ("All archives", "*.zip *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.tar"),
                ("ZIP files", "*.zip"),
                ("TAR archives", "*.tar.gz *.tgz *.tar.bz2 *.tar.xz *.tar"),
                ("All files", "*.*")
            ]
        )
        if path:
            self._process_file(path)

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        self._process_file(path)

    def _process_file(self, file_path):
        file_name = os.path.basename(file_path)
        self._log(f"📂 Processing: {file_name}")
        self._set_buttons_state("disabled")

        def worker():
            theme_name, ok, msg = install_theme(file_path, self._log)
            if not ok:
                self._log(f"❌ {msg}")
                self._set_buttons_state("normal")
                return

            db_themes = self.db.get("themes", {})
            if theme_name not in db_themes:
                db_themes[theme_name] = {"source": file_name, "zip": file_path}
            self.db["themes"] = db_themes
            save_db(self.db)

            activated = activate_theme(theme_name, self._log)
            if activated:
                db_themes[theme_name]["active"] = True
                save_db(self.db)

            self._sync_with_system()
            self._refresh_list()
            self._set_buttons_state("normal")

        threading.Thread(target=worker, daemon=True).start()

    def _activate_selected(self):
        sel = self.tree.selection()
        if not sel:
            self._log("⚠️  Select a theme from the list.")
            return
        theme_name = sel[0]
        self._set_buttons_state("disabled")

        def worker():
            activate_theme(theme_name, self._log)
            self._refresh_list()
            self._set_buttons_state("normal")

        threading.Thread(target=worker, daemon=True).start()

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            self._log("⚠️  Select a theme from the list.")
            return
        theme_name = sel[0]
        if theme_name == get_current_theme():
            self._log("❌ Cannot remove the currently active theme!")
            return
        if not messagebox.askyesno("Confirm", f"Remove theme '{theme_name}'?"):
            return
        self._set_buttons_state("disabled")

        def worker():
            ok = remove_theme(theme_name, self._log)
            if ok:
                db_themes = self.db.get("themes", {})
                db_themes.pop(theme_name, None)
                self.db["themes"] = db_themes
                save_db(self.db)
            self._sync_with_system()
            self._refresh_list()
            self._set_buttons_state("normal")

        threading.Thread(target=worker, daemon=True).start()

    def _disable_splash(self):
        if not messagebox.askyesno(
            "Disable boot splash",
            "This will disable the graphical boot splash entirely.\n"
            "The system will boot with plain text output.\n\n"
            "Continue?"
        ):
            return
        self._set_buttons_state("disabled")

        def worker():
            disable_splash(self._log)
            self._refresh_list()
            self._set_buttons_state("normal")

        threading.Thread(target=worker, daemon=True).start()

    def _set_buttons_state(self, state):
        for btn in [self.btn_activate, self.btn_remove, self.btn_disable, self.btn_refresh]:
            btn.config(state=state)
        self.update_idletasks()


if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore
        class AppDnD(App, TkinterDnD.Tk):
            def __init__(self):
                TkinterDnD.Tk.__init__(self)
                self.title("Plymouth Theme Manager")
                self.configure(bg="#0d1117")
                self.geometry("700x600")
                self.resizable(True, True)
                self.db = load_db()
                self._build_ui()
                self._sync_with_system()
                self._refresh_list()
        app = AppDnD()
    except ImportError:
        app = App()

    app.mainloop()
