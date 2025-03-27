# SIMS-4-DLC-Save-and-Mod-Manager

A user-friendly graphical tool built with Python and Tkinter to help manage The Sims 4 installation on Windows. Easily enable or disable official DLC packs and custom content (mods/CC), install new mods without overwriting existing ones, and create/restore backups of your vital Saves and Mods folders.
Don't forget to enable mods in the SIMS 4 Menu after installing mods with this tool. 

## Features

*   **DLC Management:**
*   ![image](https://github.com/user-attachments/assets/4bbbd29c-016a-48b1-a351-1492ff744caa)
    *   Scans your Sims 4 game directory for official DLC folders (EP, GP, SP, FP, KP).
    *   Displays DLCs with their status (Enabled/Disabled) and full names (requires `dlc_mapping.json`).
    *   Enable or disable selected DLCs by renaming their folders (adds/removes `_disabled` suffix).
*   **Mod Management:**
*   ![image](https://github.com/user-attachments/assets/bcb34548-bb41-408e-b871-66743c92fd4b)
    *   Scans your Sims 4 `Mods` folder (usually in `Documents\Electronic Arts\The Sims 4\Mods`).
    *   Lists top-level `.package`, `.ts4script` files and sub-folders.
    *   Enable or disable selected mods/folders by renaming them (adds/removes `_disabled` suffix or changes file extension).
*   **Safe Mod Installation:**
    *   Install new mods from `.zip` archives, `.package` files, or `.ts4script` files.
    *   Extracts zip contents directly into the `Mods` folder.
    *   **Crucially, it checks if a file or folder already exists before extracting/copying and skips existing items to prevent accidental overwrites.**
*   **Save File Management:**
*   ![image](https://github.com/user-attachments/assets/b29c57da-a624-4677-bae0-e12ee72d5863)
    *   Backup your entire `saves` folder to a timestamped `.zip` archive.
    *   Restore your `saves` folder from a chosen `.zip` backup (automatically backs up the current saves folder before restoring).
    *   Displays key information about your saves folder: path, total `.save` file count, timestamp of the most recent save, and total folder size.
*   **Mods Folder Backup/Restore:**
    *   Backup your entire `Mods` folder (including subdirectories) to a timestamped `.zip` archive.
    *   Restore your `Mods` folder from a chosen `.zip` backup (automatically backs up the current Mods folder before restoring).
*   **Path Detection & Configuration:**
    *   Attempts to auto-detect the Sims 4 installation path for Steam versions via the registry and common library locations.
    *   Allows manual browsing to select the game installation folder (necessary for EA App/Origin installs or non-standard locations).
    *   Saves the selected game path in `dlc_manager_config.json` for future use.
*   **User Interface:**
    *   Simple and clean GUI built with Python's standard Tkinter library.
    *   Status bar provides feedback on operations.
    *   Uses color-coding in lists for Enabled/Disabled status.


## Installation and Usage

**Option 1: Executable (`.exe`)**

1.  Download the latest `.exe` file from the [Releases](link/to/releases) page.
2.  **Important:** Download the `dlc_mapping.json` file and place it in the **same folder** as the `.exe` file.
3.  Run the executable. 

**Option 2: Running from Source (`.py`)**

1.  Ensure you have Python 3 installed on your Windows system.
2.  Download or clone this repository:
    ```bash
    git clone https://github.com/1angstrom/SIMS-4-DLC-Save-and-Mod-Manager.git
    cd SIMS-4-DLC-Save-and-Mod-Manager
    ```
    Or download the ZIP file from GitHub and extract it.
3.  **Important:** Download the `dlc_mapping.json` file and place it in the **same folder** as the Python script.
4.  Open a command prompt or PowerShell in that folder and run the script

## Configuration Files

*   **`dlc_mapping.json` (Required, User-Provided):**
    *   Maps internal DLC folder names to human-readable names.
    *   Must be present in the application's directory.
    *   Example format:
        ```json
        {
          "EP01": "Get to Work",
          "GP01": "Outdoor Retreat",
          "SP01": "Luxury Party Stuff",
          "FP01": "Holiday Celebration Pack",
          "...": "..."
        }
        ```
*   **`dlc_manager_config.json` (Auto-Generated):**
    *   Stores the detected or manually selected Sims 4 game installation path.
    *   Created automatically by the application. Do not edit manually unless necessary.

## Important Notes

*   **Windows Only:** This tool relies on Windows-specific libraries and registry access for game path detection and admin checks. It will not work on macOS or Linux.
*   **Administrator Privileges:** If your Sims 4 game is installed in a protected location (like `C:\Program Files`), you may need to run this manager **as Administrator** for DLC enabling/disabling to work correctly (due to folder renaming permissions). Operations on the `saves` and `Mods` folders in your Documents directory usually do *not* require administrator rights.
*   **Backups:** While the tool provides backup functionality, always maintain your own separate backup strategy for important files. Test restoring backups occasionally to ensure they are valid. The tool creates a `_pre_restore_` backup of the existing folder before overwriting during a restore.
*   **Mod Installation:** The "Install New Mod" feature extracts zip files or copies package/script files. It *skips* any file or folder within the zip that *already exists* in your Mods folder. It does not merge content or intelligently handle complex mod structures – it's a straightforward extraction/copy that avoids overwriting.
*   **Error Handling:** Pay attention to messages in the status bar and any pop-up error dialogs. They often provide clues if something goes wrong (e.g., permission errors, file not found).

For my lovely wife :)
