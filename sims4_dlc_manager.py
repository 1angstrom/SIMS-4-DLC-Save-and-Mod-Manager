import os
import sys
import json
import winreg  # Windows-specific registry access
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ctypes  # For checking admin privileges
import zipfile  # For zip operations
import shutil  # For folder operations (e.g., renaming, copying)
from datetime import datetime  # For timestamping backups
import time # For formatting timestamps

# --- Determine Base Directory ---
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# --- Constants and Configuration ---
DLC_MAPPING_FILE = os.path.join(base_dir, "dlc_mapping.json")   # File mapping DLC codes to names
CONFIG_FILE = os.path.join(base_dir, "dlc_manager_config.json")   # File to store user config (e.g., game path)
DISABLED_SUFFIX = "_disabled"           # Suffix to disable DLC/mods by renaming
SIMS4_STEAM_APPID = "1222670"          # Steam App ID for The Sims 4
DLC_PREFIXES = ("EP", "GP", "SP", "FP", "KP")  # Prefixes identifying DLC folders

# --- Helper Functions ---

def get_sims4_user_data_path():
    """Attempts to find the Sims 4 user data path (containing saves, mods, etc.)."""
    try:
        documents_path = os.path.join(os.path.expanduser("~"), "Documents")
        ea_path = os.path.join(documents_path, "Electronic Arts")
        sims4_user_path = os.path.join(ea_path, "The Sims 4")
        # Basic check - does 'The Sims 4' folder exist?
        if os.path.isdir(sims4_user_path):
            return sims4_user_path
        else:
            # Check alternative location sometimes used by EA App/Origin
            alt_sims4_user_path = os.path.join(documents_path, "The Sims 4")
            if os.path.isdir(alt_sims4_user_path):
                update_status("Using alternative user data path in Documents.")
                return alt_sims4_user_path
            update_status("Could not reliably find Sims 4 user data path.")
            return None # Return None if neither common path exists
    except Exception as e:
        update_status(f"Error finding user data path: {e}")
        return None

# --- Core Logic Functions ---

def load_config():
    """Loads configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            update_status(f"Warning: Error reading config: {e}")
    return {}

def save_config(config):
    """Saves configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        update_status(f"Error: Could not save config: {e}")

def load_dlc_mapping():
    """Loads DLC code-to-name mapping from JSON file."""
    if not os.path.exists(DLC_MAPPING_FILE):
        messagebox.showerror("Error", f"DLC mapping file '{DLC_MAPPING_FILE}' not found.\nPlace it in the script's directory.")
        return None
    try:
        with open(DLC_MAPPING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        messagebox.showerror("Error", f"Could not parse '{DLC_MAPPING_FILE}'.\nEnsure it's valid JSON.")
        return None
    except Exception as e:
        messagebox.showerror("Error", f"Could not read '{DLC_MAPPING_FILE}'.\nError: {e}")
        return None

def find_steam_game_path(app_id):
    """Tries to find the Steam game installation path via Windows Registry."""
    try:
        potential_hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
        potential_views = [winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY]
        uninstall_key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {app_id}"
        for hive in potential_hives:
            for view in potential_views:
                try:
                    with winreg.OpenKey(hive, uninstall_key_path, 0, winreg.KEY_READ | view) as key:
                        install_location, _ = winreg.QueryValueEx(key, "InstallLocation")
                        if install_location and os.path.isdir(install_location):
                            update_status(f"Found path via Registry: {install_location}")
                            return install_location
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"Registry access warning: {e}")
        # Fallback: Check common Steam library locations via libraryfolders.vdf
        steam_path_guesses = [
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Steam"),
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Steam")
        ]
        for steam_path in steam_path_guesses:
            library_folders_vdf = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
            if os.path.exists(library_folders_vdf):
                try:
                    with open(library_folders_vdf, 'r') as f:
                        content = f.read()
                        import re
                        paths = re.findall(r'"path"\s+"([^"]+)"', content)
                        # Add the main steamapps folder as well
                        possible_paths = [steam_path] + [p.replace('\\\\', '\\') for p in paths]
                        for lib_path in possible_paths:
                            game_path_guess = os.path.join(lib_path, "steamapps", "common", "The Sims 4")
                            if os.path.isdir(game_path_guess):
                                update_status(f"Found path via libraryfolders.vdf: {game_path_guess}")
                                return game_path_guess
                except Exception as e:
                    print(f"Could not read/parse libraryfolders.vdf: {e}")
    except Exception as e:
        update_status(f"Registry/Auto-detect error: {e}")
    return None

def scan_dlc(game_path):
    """Scans the game directory for DLC folders and determines their status."""
    if not game_path or not os.path.isdir(game_path):
        update_status("Cannot scan: Invalid game path.")
        return []
    dlc_list = []
    update_status("Scanning DLC folders...")
    root.update_idletasks() # Ensure UI updates
    try:
        for item in os.listdir(game_path):
            full_path = os.path.join(game_path, item)
            if os.path.isdir(full_path):
                folder_name = item
                status = "Enabled"
                original_name = folder_name
                if folder_name.endswith(DISABLED_SUFFIX):
                    original_name = folder_name[:-len(DISABLED_SUFFIX)]
                    status = "Disabled"
                # Check if it looks like a DLC folder
                if any(original_name.startswith(prefix) for prefix in DLC_PREFIXES):
                    # Basic check if folder seems non-empty (avoids listing empty placeholders)
                    is_empty = not any(os.scandir(full_path))
                    if not is_empty:
                        dlc_list.append({
                            "folder": folder_name,
                            "original_name": original_name,
                            "status": status
                        })
        # Sort DLCs: FP, EP, GP, SP, KP, then alphabetically
        dlc_list.sort(key=lambda x: (x["original_name"].startswith('FP'),
                                     x["original_name"].startswith('EP'),
                                     x["original_name"].startswith('GP'),
                                     x["original_name"].startswith('SP'),
                                     x["original_name"].startswith('KP'),
                                     x["original_name"]))
        update_status(f"Scan complete. Found {len(dlc_list)} DLC items.")
        return dlc_list
    except FileNotFoundError:
        update_status(f"Error: Game path not found during scan: {game_path}")
        return []
    except PermissionError:
        update_status(f"Error: Permission denied scanning path: {game_path}")
        messagebox.showwarning("Permission Error", f"Could not read contents of:\n{game_path}\nTry running as Administrator if issues persist.")
        return []
    except Exception as e:
        update_status(f"Error scanning DLC folders: {e}")
        return []

def toggle_dlc_status_backend(game_path, dlc_info):
    """Renames the DLC folder to toggle its status. Returns True on success."""
    current_path = os.path.join(game_path, dlc_info["folder"])
    target_name = dlc_info["original_name"] + DISABLED_SUFFIX if dlc_info["status"] == "Enabled" else dlc_info["original_name"]
    action = "Disabling" if dlc_info["status"] == "Enabled" else "Enabling"
    new_status = "Disabled" if dlc_info["status"] == "Enabled" else "Enabled"
    target_path = os.path.join(game_path, target_name)

    update_status(f"{action} '{dlc_info['original_name']}'...")
    root.update_idletasks() # UI update

    try:
        os.rename(current_path, target_path)
        update_status(f"Success: '{dlc_info['original_name']}' is now {new_status}.")
        return True
    except PermissionError:
        update_status(f"Error: Permission denied renaming in {game_path}")
        messagebox.showerror("Permission Error", f"Could not rename folder:\n{current_path}\nTry running as Administrator.")
        return False
    except FileExistsError:
        update_status(f"Error: '{target_name}' already exists.")
        messagebox.showerror("File Exists Error", f"Cannot rename because '{target_name}' exists.\nCheck your Sims 4 directory.")
        return False
    except Exception as e:
        update_status(f"Error renaming folder: {e}")
        messagebox.showerror("Error", f"Failed to rename folder.\nError: {e}")
        return False

def scan_mods(mods_path):
    """Scans the Mods folder for .package/.ts4script files and subfolders, determining their status."""
    if not os.path.isdir(mods_path):
        update_status("Mods folder not found.")
        return []

    mods_list = []
    update_status("Scanning Mods folder...")
    root.update_idletasks()
    try:
        # List only top-level items for management
        for item in os.listdir(mods_path):
            full_path = os.path.join(mods_path, item)
            # Ignore the Resource.cfg file
            if item.lower() == 'resource.cfg':
                continue

            if os.path.isfile(full_path) and (item.lower().endswith(".package") or item.lower().endswith(".ts4script")):
                disabled_package_suffix = "_disabled.package"
                disabled_script_suffix = "_disabled.ts4script"
                status = "Enabled"
                original_name = item

                if item.lower().endswith(disabled_package_suffix):
                    original_name = item[:-len(disabled_package_suffix)] + ".package"
                    status = "Disabled"
                elif item.lower().endswith(disabled_script_suffix):
                    original_name = item[:-len(disabled_script_suffix)] + ".ts4script"
                    status = "Disabled"

                mods_list.append({
                    "type": "file",
                    "name": item,
                    "original_name": original_name,
                    "status": status,
                    "path": full_path
                })
            elif os.path.isdir(full_path):
                status = "Enabled"
                original_name = item
                if item.endswith(DISABLED_SUFFIX):
                    original_name = item[:-len(DISABLED_SUFFIX)]
                    status = "Disabled"

                mods_list.append({
                    "type": "folder",
                    "name": item,
                    "original_name": original_name,
                    "status": status,
                    "path": full_path
                })
        mods_list.sort(key=lambda x: x["name"].lower())
        update_status(f"Mods scan complete. Found {len(mods_list)} top-level items.")
        return mods_list
    except Exception as e:
        update_status(f"Error scanning mods: {e}")
        return []

def toggle_mod_status_backend(mod_info):
    """Renames the mod file or folder to toggle its status. Returns True on success."""
    current_path = mod_info["path"]
    target_name = ""

    if mod_info["type"] == "file":
        if mod_info["status"] == "Enabled":
            if mod_info["original_name"].lower().endswith(".package"):
                target_name = mod_info["original_name"][:-len(".package")] + "_disabled.package"
            elif mod_info["original_name"].lower().endswith(".ts4script"):
                target_name = mod_info["original_name"][:-len(".ts4script")] + "_disabled.ts4script"
            else: # Should not happen based on scan, but safety check
                target_name = mod_info["original_name"] + DISABLED_SUFFIX
        else: # Currently disabled, enable it
             target_name = mod_info["original_name"]

    elif mod_info["type"] == "folder":
        target_name = mod_info["original_name"] + DISABLED_SUFFIX if mod_info["status"] == "Enabled" else mod_info["original_name"]

    if not target_name:
        update_status(f"Error: Could not determine target name for '{mod_info['name']}'")
        return False

    target_path = os.path.join(os.path.dirname(current_path), target_name)
    action = "Disabling" if mod_info["status"] == "Enabled" else "Enabling"
    new_status = "Disabled" if mod_info["status"] == "Enabled" else "Enabled"

    update_status(f"{action} '{mod_info['name']}'...")
    root.update_idletasks()

    try:
        os.rename(current_path, target_path)
        update_status(f"Success: '{mod_info['original_name']}' is now {new_status}.")
        return True
    except PermissionError:
        update_status(f"Error: Permission denied renaming {mod_info['name']}")
        messagebox.showerror("Permission Error", f"Could not rename:\n{current_path}\nTry running as Administrator if issues persist.")
        return False
    except FileExistsError:
        update_status(f"Error: '{target_name}' already exists.")
        messagebox.showerror("File Exists Error", f"Cannot rename because '{target_name}' exists.\nCheck your Mods folder.")
        return False
    except Exception as e:
        update_status(f"Error renaming: {e}")
        messagebox.showerror("Error", f"Failed to rename.\nError: {e}")
        return False

# --- NEW: Install Mod Function ---
def install_new_mod():
    """Installs a new mod from a zip or package file without overwriting."""
    sims4_user_path = get_sims4_user_data_path()
    if not sims4_user_path:
        messagebox.showerror("Error", "Could not determine Sims 4 user data directory.")
        return
    mods_path = os.path.join(sims4_user_path, "Mods")

    # Ensure Mods folder exists
    try:
        os.makedirs(mods_path, exist_ok=True)
    except Exception as e:
        messagebox.showerror("Error", f"Could not create Mods directory:\n{mods_path}\nError: {e}")
        return

    mod_file_path = filedialog.askopenfilename(
        title="Select Mod File to Install",
        filetypes=[("Mod Archives", "*.zip"), ("Package Files", "*.package"), ("Script Files", "*.ts4script"), ("All files", "*.*")]
    )

    if not mod_file_path:
        update_status("Mod installation cancelled.")
        return

    filename = os.path.basename(mod_file_path)
    skipped_files = []
    installed_count = 0

    update_status(f"Installing '{filename}'...")
    root.update_idletasks()

    try:
        if mod_file_path.lower().endswith(".zip"):
            if not zipfile.is_zipfile(mod_file_path):
                messagebox.showerror("Error", f"'{filename}' is not a valid ZIP file.")
                update_status("Installation failed: Invalid ZIP.")
                return

            with zipfile.ZipFile(mod_file_path, 'r') as zipf:
                members = zipf.infolist()
                for member in members:
                    target_path = os.path.join(mods_path, member.filename)

                    # Prevent path traversal exploits (though zipfile usually handles this)
                    if not os.path.abspath(target_path).startswith(os.path.abspath(mods_path)):
                        update_status(f"Skipping potentially unsafe path: {member.filename}")
                        skipped_files.append(f"{member.filename} (unsafe path)")
                        continue

                    # Check for existence before extraction
                    if os.path.exists(target_path):
                        skipped_files.append(member.filename)
                        continue # Skip extraction

                    # Extract if it doesn't exist
                    zipf.extract(member, mods_path)
                    installed_count += 1

        elif mod_file_path.lower().endswith((".package", ".ts4script")):
            target_path = os.path.join(mods_path, filename)
            if os.path.exists(target_path):
                skipped_files.append(filename)
            else:
                shutil.copy2(mod_file_path, target_path) # copy2 preserves metadata
                installed_count += 1
        else:
            messagebox.showwarning("Unsupported File", f"Don't know how to install '{filename}'. Only .zip, .package, and .ts4script supported.")
            update_status("Installation failed: Unsupported file type.")
            return

        # --- Report results ---
        if installed_count > 0 and not skipped_files:
            update_status(f"Successfully installed '{filename}'.")
            messagebox.showinfo("Install Complete", f"Mod '{filename}' installed successfully.")
        elif installed_count > 0 and skipped_files:
            update_status(f"Installed '{filename}' with skips.")
            messagebox.showwarning("Install Partially Complete",
                                   f"Mod '{filename}' installed, but the following items already existed and were SKIPPED:\n\n" + "\n".join(skipped_files))
        elif installed_count == 0 and skipped_files:
             update_status(f"Installation skipped: '{filename}' contents already exist.")
             messagebox.showinfo("Install Skipped",
                                 f"Installation of '{filename}' skipped. All contained files/folders already exist in the Mods directory.")
        else: # installed_count == 0 and not skipped_files (e.g., empty zip?)
             update_status(f"No new files installed from '{filename}'.")
             messagebox.showinfo("Install Complete", f"No new files were installed from '{filename}'. It might be empty or contain only existing items.")

        refresh_mods_list() # Update the mod list view

    except zipfile.BadZipFile:
         messagebox.showerror("Error", f"'{filename}' is corrupted or not a valid ZIP file.")
         update_status("Installation failed: Bad ZIP file.")
    except PermissionError:
        messagebox.showerror("Permission Error", f"Permission denied during installation.\nCheck permissions for:\n{mods_path}")
        update_status("Installation failed: Permission denied.")
    except Exception as e:
        update_status(f"Installation failed: {e}")
        messagebox.showerror("Installation Error", f"Could not install mod '{filename}'.\nError: {e}")


# --- GUI Functions ---

def update_status(message):
    """Updates the status bar with a message."""
    status_var.set(message)
    # print(message) # Optional: print to console for debugging

def browse_game_path():
    """Opens a dialog to select the game installation path."""
    initial_dir = os.path.dirname(game_path_var.get()) if game_path_var.get() and os.path.isdir(os.path.dirname(game_path_var.get())) else "C:\\"
    new_path = filedialog.askdirectory(title="Select 'The Sims 4' Installation Folder", initialdir=initial_dir)
    if new_path and os.path.isdir(new_path):
        # Basic validation: Check for 'Game' subdirectory as a hint
        is_likely_sims4_folder = os.path.isdir(os.path.join(new_path, "Game"))
        if not is_likely_sims4_folder:
            confirm = messagebox.askyesno("Confirm Path", f"The selected folder is:\n{new_path}\n\nIt doesn't seem to contain the 'Game' subfolder. Is this correct?")
            if not confirm:
                return

        game_path_var.set(new_path)
        config = load_config()
        config["game_path"] = new_path
        save_config(config)
        update_status(f"Game path set to: {new_path}")
        refresh_dlc_list() # Refresh DLC list since path changed
    elif new_path: # User selected something, but it wasn't a valid directory after selection
        messagebox.showwarning("Invalid Path", "The selected path is not a valid directory.")

def populate_dlc_listbox():
    """Populates the DLC listbox with current DLC status."""
    dlc_listbox.delete(0, tk.END)
    current_dlc_list.clear() # Clear the backend list too
    game_path = game_path_var.get()

    if not game_path or not os.path.isdir(game_path):
        update_status("Set a valid game path to scan for DLC.")
        toggle_dlc_button.config(state=tk.DISABLED)
        dlc_listbox.insert(tk.END, " Please set the Sims 4 game path above.")
        dlc_listbox.itemconfig(0, {"fg": "grey"})
        return

    dlcs = scan_dlc(game_path) # This function now updates status internally
    current_dlc_list.extend(dlcs) # Store the scanned list

    if not dlcs:
        dlc_listbox.insert(tk.END, " No DLCs found (or path inaccessible/permission error).")
        dlc_listbox.itemconfig(0, {"fg": "grey"})
    else:
        # Determine padding based on longest code and name for alignment
        max_code = 0
        max_name = 0
        for dlc in dlcs:
             max_code = max(max_code, len(dlc['original_name']))
             name = dlc_mapping.get(dlc['original_name'], f"Unknown ({dlc['original_name']})")
             max_name = max(max_name, len(name))

        for i, dlc in enumerate(dlcs):
            status = dlc["status"]
            code = dlc['original_name']
            name = dlc_mapping.get(code, f"Unknown ({code})")
            # Use f-string formatting for alignment
            display_text = f"[{status:<8}] {code:<{max_code+2}} {name}"
            dlc_listbox.insert(tk.END, display_text)
            dlc_listbox.itemconfig(i, {"fg": "darkgreen" if status == "Enabled" else "darkred"})

    # Update button state after population
    on_dlc_select(None) # Pass None as event isn't needed here

def refresh_dlc_list():
    """Refreshes the DLC listbox."""
    populate_dlc_listbox()

def on_dlc_select(event):
    """Enables the toggle button when a DLC is selected."""
    toggle_dlc_button.config(state=tk.NORMAL if dlc_listbox.curselection() else tk.DISABLED)

def toggle_selected_dlc():
    """Toggles the status of the selected DLC."""
    selected_indices = dlc_listbox.curselection()
    if not selected_indices:
        update_status("No DLC selected.")
        return

    index = selected_indices[0]
    if index >= len(current_dlc_list): # Safety check
        update_status("Selection index out of bounds. Please refresh.")
        messagebox.showwarning("Selection Error", "Selected item doesn't match list.\nRefresh and try again.")
        return

    dlc_to_toggle = current_dlc_list[index]
    game_path = game_path_var.get()
    success = toggle_dlc_status_backend(game_path, dlc_to_toggle)

    if success:
        # Refresh the entire list to reflect the change
        populate_dlc_listbox()
        # Try to re-select the item
        try:
            dlc_listbox.selection_set(index)
            dlc_listbox.activate(index)
            dlc_listbox.see(index) # Ensure it's visible
            on_dlc_select(None) # Update button state
        except tk.TclError: # Handle cases where index might become invalid (though unlikely with refresh)
             toggle_dlc_button.config(state=tk.DISABLED)
    else:
        # Ensure button is disabled if toggle failed (e.g., permission error)
        on_dlc_select(None)

def populate_mods_listbox():
    """Populates the mods listbox with current mod status."""
    mods_listbox.delete(0, tk.END)
    current_mod_list.clear()
    sims4_user_path = get_sims4_user_data_path()
    mods_path = ""
    if sims4_user_path:
        mods_path = os.path.join(sims4_user_path, "Mods")

    if not mods_path or not os.path.isdir(mods_path):
        update_status("Sims 4 user data path or Mods folder not found.")
        mods_listbox.insert(tk.END, " Mods folder not found.")
        mods_listbox.itemconfig(0, {"fg": "grey"})
        toggle_mod_button.config(state=tk.DISABLED)
        # Disable backup/restore/install if path invalid
        backup_mods_button.config(state=tk.DISABLED)
        restore_mods_button.config(state=tk.DISABLED)
        install_mod_button.config(state=tk.DISABLED) # NEW
        return

    # Path exists, enable buttons dependent on it
    backup_mods_button.config(state=tk.NORMAL)
    restore_mods_button.config(state=tk.NORMAL)
    install_mod_button.config(state=tk.NORMAL) # NEW

    mods = scan_mods(mods_path) # Status updated inside scan_mods
    current_mod_list.extend(mods)

    if not mods:
        mods_listbox.insert(tk.END, " No mods found (or only Resource.cfg).")
        mods_listbox.itemconfig(0, {"fg": "grey"})
    else:
        # Determine padding
        max_name = 0
        for mod in mods:
            max_name = max(max_name, len(mod["name"]))

        for i, mod in enumerate(mods):
            status = mod["status"]
            name = mod["name"]
            type_indicator = "[F]" if mod["type"] == "folder" else "[P]" # P for package/script
            # Format for alignment
            display_text = f"{type_indicator} [{status:<8}] {name}"
            mods_listbox.insert(tk.END, display_text)
            color = "darkgreen" if status == "Enabled" else "darkred"
            mods_listbox.itemconfig(i, {"fg": color})

    # Update toggle button state
    on_mod_select(None)

def refresh_mods_list():
    """Refreshes the mods listbox."""
    populate_mods_listbox()

def on_mod_select(event):
    """Enables the toggle button when a mod is selected."""
    toggle_mod_button.config(state=tk.NORMAL if mods_listbox.curselection() else tk.DISABLED)

def toggle_selected_mod():
    """Toggles the status of the selected mod."""
    selected_indices = mods_listbox.curselection()
    if not selected_indices:
        update_status("No mod selected.")
        return

    index = selected_indices[0]
    if index >= len(current_mod_list): # Safety check
        update_status("Selection index out of bounds. Please refresh.")
        messagebox.showwarning("Selection Error", "Selected item doesn't match list.\nRefresh and try again.")
        return

    mod_to_toggle = current_mod_list[index]
    success = toggle_mod_status_backend(mod_to_toggle)

    if success:
        # Refresh list and try re-selecting
        populate_mods_listbox()
        try:
            mods_listbox.selection_set(index)
            mods_listbox.activate(index)
            mods_listbox.see(index)
            on_mod_select(None)
        except tk.TclError:
            toggle_mod_button.config(state=tk.DISABLED)
    else:
        on_mod_select(None) # Ensure button state is correct if toggle failed

# --- Save/Restore Functions (Shared logic for backup/restore messages) ---

def _perform_backup_restore(action_type, item_type, source_path, dialog_title, initial_filename_prefix, file_extension):
    """Generic helper for backup/restore operations."""
    sims4_user_path = get_sims4_user_data_path()
    if not sims4_user_path:
        messagebox.showerror("Error", "Could not determine Sims 4 user data directory.")
        return

    target_path = os.path.join(sims4_user_path, source_path) # e.g., ".../The Sims 4/saves"

    if action_type == "backup":
        if not os.path.isdir(target_path):
            messagebox.showerror("Error", f"{item_type} folder not found at:\n{target_path}")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        initial_filename = f"{initial_filename_prefix}_{timestamp}.{file_extension}"
        archive_path = filedialog.asksaveasfilename(
            title=f"Save {item_type} Backup As",
            initialfile=initial_filename,
            defaultextension=f".{file_extension}",
            filetypes=[("Zip files", f"*.{file_extension}"), ("All files", "*.*")]
        )
        if not archive_path:
            update_status(f"{item_type} backup cancelled.")
            return

        update_status(f"Backing up {item_type.lower()} to {os.path.basename(archive_path)}...")
        root.update_idletasks()
        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root_dir, _, files in os.walk(target_path):
                    # Skip the pre-restore backup folders if they exist inside target_path (unlikely but possible)
                    if os.path.basename(root_dir).startswith(f"{source_path}_pre_restore_"):
                        continue
                    relative_path = os.path.relpath(root_dir, target_path)
                    for file in files:
                        full_path = os.path.join(root_dir, file)
                        arcname = os.path.join(relative_path, file) if relative_path != '.' else file
                        zipf.write(full_path, arcname=arcname)
            update_status(f"{item_type} backup completed successfully.")
            messagebox.showinfo("Backup Complete", f"{item_type} backed up to:\n{archive_path}")
        except Exception as e:
            update_status(f"{item_type} backup failed: {e}")
            messagebox.showerror("Backup Failed", f"Could not create {item_type.lower()} backup.\nError: {e}")

    elif action_type == "restore":
        archive_path = filedialog.askopenfilename(
            title=f"Select {item_type} Backup File to Restore",
            defaultextension=f".{file_extension}",
            filetypes=[("Zip files", f"*.{file_extension}"), ("All files", "*.*")]
        )
        if not archive_path:
            update_status(f"{item_type} restore cancelled.")
            return
        if not os.path.isfile(archive_path) or not zipfile.is_zipfile(archive_path):
            messagebox.showerror("Invalid File", f"Not a valid ZIP archive:\n{archive_path}")
            return

        confirm = messagebox.askyesno(
            "Confirm Restore",
            f"This will REPLACE your current Sims 4 {item_type} folder:\n{target_path}\n\n"
            f"Current {item_type.lower()} will be moved to a backup folder first.\n\n"
            f"Restore from:\n{os.path.basename(archive_path)}?"
        )
        if not confirm:
            update_status(f"{item_type} restore cancelled by confirmation.")
            return

        pre_restore_backup_path = ""
        if os.path.exists(target_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Place backup adjacent to target folder
            pre_restore_backup_path = os.path.join(sims4_user_path, f"{source_path}_pre_restore_{timestamp}")
            update_status(f"Moving current {item_type.lower()} to {os.path.basename(pre_restore_backup_path)}...")
            root.update_idletasks()
            try:
                shutil.move(target_path, pre_restore_backup_path)
                update_status(f"Current {item_type.lower()} moved successfully.")
            except Exception as e:
                update_status(f"Error moving current {item_type.lower()}: {e}")
                messagebox.showerror("Restore Error", f"Could not move current {item_type} folder:\n{target_path}\nRestore aborted. Error: {e}")
                return

        try:
            os.makedirs(target_path, exist_ok=True) # Ensure target dir exists
            update_status(f"Extracting backup to {target_path}...")
            root.update_idletasks()
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall(target_path)
            update_status(f"{item_type} restore completed successfully.")
            msg = f"{item_type} restored from:\n{os.path.basename(archive_path)}"
            if pre_restore_backup_path:
                msg += f"\n\nPrevious {item_type.lower()} backed up in:\n{pre_restore_backup_path}"
            messagebox.showinfo("Restore Complete", msg)
            # Refresh relevant list/info if needed
            if item_type == "Saves":
                update_save_info() # Update displayed save info
            elif item_type == "Mods":
                refresh_mods_list() # Update the mods listbox

        except Exception as e:
            update_status(f"Restore failed during extraction: {e}")
            messagebox.showerror("Restore Failed", f"Could not extract {item_type.lower()} backup.\nError: {e}\nAttempting rollback...")
            try:
                # Attempt rollback
                if os.path.isdir(target_path): # Remove potentially partially extracted folder
                    shutil.rmtree(target_path)
                if pre_restore_backup_path and os.path.isdir(pre_restore_backup_path):
                    shutil.move(pre_restore_backup_path, target_path)
                    update_status(f"Rolled back: Previous {item_type.lower()} restored.")
                    messagebox.showinfo("Rollback", f"Previous {item_type} folder restored.")
                else:
                    update_status(f"Rollback failed: No pre-restore backup found or it was already moved: {pre_restore_backup_path}")
                    messagebox.showwarning("Rollback Failed", f"Could not restore previous {item_type.lower()}. Check manually.")
            except Exception as rollback_e:
                update_status(f"CRITICAL: Rollback failed: {rollback_e}")
                messagebox.showerror("Critical Rollback Error", f"Rollback failed after extraction error.\nError: {rollback_e}\nCheck your '{source_path}' and backup folders manually!")

# --- Specific Backup/Restore Functions using the helper ---

def backup_saves():
    _perform_backup_restore("backup", "Saves", "saves", "Save Saves Backup As", "Sims4_Saves_Backup", "zip")

def restore_saves():
    _perform_backup_restore("restore", "Saves", "saves", "Select Saves Backup File", "", "zip")

def backup_mods():
    _perform_backup_restore("backup", "Mods", "Mods", "Save Mods Backup As", "Sims4_Mods_Backup", "zip")

def restore_mods():
     _perform_backup_restore("restore", "Mods", "Mods", "Select Mods Backup File", "", "zip")

# --- NEW: Update Save Info Function ---
def update_save_info():
    """Updates the labels on the Save Files tab with info about the saves folder."""
    sims4_user_path = get_sims4_user_data_path()
    saves_path = ""
    if sims4_user_path:
        saves_path = os.path.join(sims4_user_path, "saves")

    if not saves_path or not os.path.isdir(saves_path):
        save_path_var.set("Saves folder not found")
        save_count_var.set("N/A")
        save_latest_var.set("N/A")
        save_size_var.set("N/A")
        update_status("Could not find saves folder to get info.")
        # Disable buttons if path is invalid
        backup_saves_button.config(state=tk.DISABLED)
        restore_saves_button.config(state=tk.DISABLED)
        return

    # Path exists, enable buttons
    backup_saves_button.config(state=tk.NORMAL)
    restore_saves_button.config(state=tk.NORMAL)

    save_path_var.set(saves_path)
    update_status("Gathering save file information...")
    root.update_idletasks()

    total_size = 0
    save_files = []
    latest_mtime = 0

    try:
        for root_dir, dirs, files in os.walk(saves_path):
            # Skip the pre-restore backup folders if they somehow ended up inside 'saves'
            if os.path.basename(root_dir).startswith("saves_pre_restore_"):
                dirs[:] = [] # Don't recurse into these
                continue

            for file in files:
                full_path = os.path.join(root_dir, file)
                try:
                    stats = os.stat(full_path)
                    total_size += stats.st_size
                    if file.lower().endswith(".save"):
                        save_files.append(full_path)
                        if stats.st_mtime > latest_mtime:
                            latest_mtime = stats.st_mtime
                except OSError:
                    continue # Ignore files we can't access or stat

        save_count_var.set(str(len(save_files)))

        if latest_mtime > 0:
            latest_dt = datetime.fromtimestamp(latest_mtime)
            save_latest_var.set(latest_dt.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            save_latest_var.set("No .save files found")

        # Format size
        if total_size < 1024:
            size_str = f"{total_size} Bytes"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.2f} KB"
        elif total_size < 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
        save_size_var.set(size_str)

        update_status("Save file information updated.")

    except Exception as e:
        update_status(f"Error getting save info: {e}")
        save_path_var.set(saves_path) # Path might still be valid
        save_count_var.set("Error")
        save_latest_var.set("Error")
        save_size_var.set("Error")


# --- GUI Setup ---

root = tk.Tk()
root.title("SIMS 4 DLC, Save, and Mod Manager")
root.geometry("750x550") # Adjusted size slightly

# --- Variables ---
game_path_var = tk.StringVar()      # Stores the game installation path
status_var = tk.StringVar()         # Status bar message
current_dlc_list = []               # List of detected DLCs [{folder, original_name, status}, ...]
current_mod_list = []               # List of detected mods [{type, name, original_name, status, path}, ...]
dlc_mapping = {}                    # Mapping of DLC codes to names

# Save Info Variables (NEW)
save_path_var = tk.StringVar(value="N/A")
save_count_var = tk.StringVar(value="N/A")
save_latest_var = tk.StringVar(value="N/A")
save_size_var = tk.StringVar(value="N/A")

# --- Check Admin Privileges ---
is_admin = False
try:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
except AttributeError:
    # Handle systems where windll or shell32 might not be available (though unlikely on target Windows)
    update_status("Could not check admin status.")
except Exception as e:
    update_status(f"Error checking admin status: {e}")


# --- Top Frame (Path Selection) ---
path_frame = ttk.Frame(root, padding="10 10 10 5")
path_frame.pack(fill=tk.X, side=tk.TOP)
ttk.Label(path_frame, text="Sims 4 Game Path:").pack(side=tk.LEFT, padx=(0, 5))
path_entry = ttk.Entry(path_frame, textvariable=game_path_var, width=60)
path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
browse_button = ttk.Button(path_frame, text="Browse...", command=browse_game_path)
browse_button.pack(side=tk.LEFT, padx=(5, 0))

# --- Notebook (Tabs) ---
notebook = ttk.Notebook(root, padding="5 5 5 5")
notebook.pack(fill=tk.BOTH, expand=True)

# --- Save Files Tab (ENHANCED) ---
save_frame = ttk.Frame(notebook, padding="10")
notebook.add(save_frame, text="Save Files")

# Frame for Buttons
save_button_frame = ttk.Frame(save_frame)
save_button_frame.pack(pady=(5, 15), anchor='w') # Anchor west (left)

backup_saves_button = ttk.Button(save_button_frame, text="Backup Saves", command=backup_saves, state=tk.DISABLED)
backup_saves_button.pack(side=tk.LEFT, padx=5)
restore_saves_button = ttk.Button(save_button_frame, text="Restore Saves", command=restore_saves, state=tk.DISABLED)
restore_saves_button.pack(side=tk.LEFT, padx=5)
refresh_save_info_button = ttk.Button(save_button_frame, text="Refresh Info", command=update_save_info)
refresh_save_info_button.pack(side=tk.LEFT, padx=(15, 5))

# Frame for Information Labels (NEW)
save_info_frame = ttk.LabelFrame(save_frame, text="Save File Information", padding="10")
save_info_frame.pack(fill=tk.X, expand=False) # Fill horizontally, don't expand vertically

# Grid layout for labels inside the info frame
save_info_frame.columnconfigure(1, weight=1) # Allow value column to expand

ttk.Label(save_info_frame, text="Saves Folder:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
ttk.Label(save_info_frame, textvariable=save_path_var, relief=tk.SUNKEN, padding=2, anchor='w').grid(row=0, column=1, sticky='ew', padx=5, pady=2)

ttk.Label(save_info_frame, text="Save File Count (.save):").grid(row=1, column=0, sticky='w', padx=5, pady=2)
ttk.Label(save_info_frame, textvariable=save_count_var, anchor='w').grid(row=1, column=1, sticky='ew', padx=5, pady=2)

ttk.Label(save_info_frame, text="Most Recent Save:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
ttk.Label(save_info_frame, textvariable=save_latest_var, anchor='w').grid(row=2, column=1, sticky='ew', padx=5, pady=2)

ttk.Label(save_info_frame, text="Total Folder Size:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
ttk.Label(save_info_frame, textvariable=save_size_var, anchor='w').grid(row=3, column=1, sticky='ew', padx=5, pady=2)

# --- Official DLC Tab ---
dlc_frame = ttk.Frame(notebook)
notebook.add(dlc_frame, text="Official DLC")

# List Frame for DLC
dlc_list_frame = ttk.Frame(dlc_frame, padding="10 0 10 5")
dlc_list_frame.pack(fill=tk.BOTH, expand=True)

dlc_list_scrollbar_y = ttk.Scrollbar(dlc_list_frame, orient=tk.VERTICAL)
dlc_list_scrollbar_x = ttk.Scrollbar(dlc_list_frame, orient=tk.HORIZONTAL)
dlc_listbox = tk.Listbox(
    dlc_list_frame,
    selectmode=tk.SINGLE,
    yscrollcommand=dlc_list_scrollbar_y.set,
    xscrollcommand=dlc_list_scrollbar_x.set,
    font=("Courier New", 10), # Monospaced font for alignment
    height=15,
    width=70 # Give it a reasonable initial width
)
dlc_list_scrollbar_y.config(command=dlc_listbox.yview)
dlc_list_scrollbar_x.config(command=dlc_listbox.xview)
dlc_list_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
dlc_list_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
dlc_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
dlc_listbox.bind('<<ListboxSelect>>', on_dlc_select) # Event binding

# Button Frame for DLC
dlc_button_frame = ttk.Frame(dlc_frame, padding="10 5 10 10")
dlc_button_frame.pack(fill=tk.X)

toggle_dlc_button = ttk.Button(dlc_button_frame, text="Toggle Selected DLC", command=toggle_selected_dlc, state=tk.DISABLED)
toggle_dlc_button.pack(side=tk.LEFT, padx=(0, 5))
refresh_dlc_button = ttk.Button(dlc_button_frame, text="Refresh DLC List", command=refresh_dlc_list)
refresh_dlc_button.pack(side=tk.LEFT, padx=(0, 10))

# --- Mods Tab ---
mods_frame = ttk.Frame(notebook)
notebook.add(mods_frame, text="Mods")

# List Frame for Mods
mods_list_frame = ttk.Frame(mods_frame, padding="10 0 10 5")
mods_list_frame.pack(fill=tk.BOTH, expand=True)

mods_list_scrollbar_y = ttk.Scrollbar(mods_list_frame, orient=tk.VERTICAL)
mods_list_scrollbar_x = ttk.Scrollbar(mods_list_frame, orient=tk.HORIZONTAL)
mods_listbox = tk.Listbox(
    mods_list_frame,
    selectmode=tk.SINGLE,
    yscrollcommand=mods_list_scrollbar_y.set,
    xscrollcommand=mods_list_scrollbar_x.set,
    font=("Courier New", 10), # Monospaced font
    height=15,
    width=70
)
mods_list_scrollbar_y.config(command=mods_listbox.yview)
mods_list_scrollbar_x.config(command=mods_listbox.xview)
mods_list_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
mods_list_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
mods_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
mods_listbox.bind('<<ListboxSelect>>', on_mod_select) # Event binding

# Button Frame for Mods
mods_button_frame = ttk.Frame(mods_frame, padding="10 5 10 10")
mods_button_frame.pack(fill=tk.X)

toggle_mod_button = ttk.Button(mods_button_frame, text="Toggle Selected Mod", command=toggle_selected_mod, state=tk.DISABLED)
toggle_mod_button.pack(side=tk.LEFT, padx=(0, 5))
refresh_mod_button = ttk.Button(mods_button_frame, text="Refresh Mod List", command=refresh_mods_list)
refresh_mod_button.pack(side=tk.LEFT, padx=(0, 10))

ttk.Separator(mods_button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

# NEW Install Mod Button
install_mod_button = ttk.Button(mods_button_frame, text="Install New Mod...", command=install_new_mod, state=tk.DISABLED)
install_mod_button.pack(side=tk.LEFT, padx=(5, 5))

ttk.Separator(mods_button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

backup_mods_button = ttk.Button(mods_button_frame, text="Backup Mods", command=backup_mods, state=tk.DISABLED)
backup_mods_button.pack(side=tk.LEFT, padx=(5, 5))
restore_mods_button = ttk.Button(mods_button_frame, text="Restore Mods", command=restore_mods, state=tk.DISABLED)
restore_mods_button.pack(side=tk.LEFT, padx=(0, 10))

# --- Status Bar ---
status_frame = ttk.Frame(root, relief=tk.SUNKEN, padding="2 2 2 2")
status_frame.pack(fill=tk.X, side=tk.BOTTOM)
status_label = ttk.Label(status_frame, textvariable=status_var, anchor=tk.W)
status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

# --- Initialization Logic ---

def initialize_app():
    """Initializes the application by loading config and setting up the GUI."""
    global dlc_mapping, config
    update_status("Initializing...")

    # Load DLC Mapping first
    dlc_mapping = load_dlc_mapping()
    if dlc_mapping is None:
        # Error message shown in load_dlc_mapping
        root.quit() # Quit if mapping failed to load
        return

    # Load Config
    config = load_config()
    path = config.get("game_path")

    # Determine Game Path
    if path and os.path.isdir(path):
        update_status(f"Using path from config: {path}")
        game_path_var.set(path)
    else:
        update_status("Attempting game path auto-detection...")
        detected_path = find_steam_game_path(SIMS4_STEAM_APPID)
        if detected_path and os.path.isdir(detected_path):
            game_path_var.set(detected_path)
            config["game_path"] = detected_path # Save detected path
            save_config(config)
        else:
            update_status("Auto-detect failed. Please browse for the 'The Sims 4' game folder.")
            messagebox.showinfo("Path Needed", "Could not find The Sims 4 installation automatically.\nUse 'Browse...' to select the game folder (e.g., ...\\Steam\\steamapps\\common\\The Sims 4 or ...\\EA Games\\The Sims 4).\n\nThis tool primarily helps manage DLC and Mods. Save backups work independently of the game path.")

    # Populate Lists and Info
    populate_dlc_listbox()
    populate_mods_listbox()
    update_save_info() # NEW: Populate save info on start

    # Admin Warning
    if not is_admin and game_path_var.get() and ("program files" in game_path_var.get().lower() or "windows" in game_path_var.get().lower()):
        messagebox.showwarning("Admin Rights May Be Needed", "The Sims 4 game path is in a protected location.\nRun this manager as Administrator if DLC toggling fails due to permission errors.\n\nSave/Mod operations in your Documents folder usually don’t need admin rights.")
    elif not is_admin:
         update_status("Ready. Run as Admin if DLC toggling fails.")
    else:
         update_status("Ready. (Running as Administrator)")


# --- Run the Application ---
if __name__ == "__main__":
    # Use 'after' to ensure the main window is created before initialization runs
    root.after(100, initialize_app)
    root.mainloop()