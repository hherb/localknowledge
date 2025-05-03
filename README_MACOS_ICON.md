# Setting up the macOS Application Icon

This README explains how to properly set up the application icon for macOS.

## Running with the Icon in Development

To run the application with the proper icon in the macOS Dock:

1. Use the provided `run_rwb.py` script:
   ```
   ./run_rwb.py
   ```

   This script sets up the necessary environment variables to use the Info.plist file.

## How It Works

The application icon is set in three ways:

1. **Window Icon**: The application's main window and dialog windows have their icons set using `setWindowIcon(QIcon(icon_path))`.

2. **Application Icon**: The QApplication instance has its icon set using `app.setWindowIcon(QIcon(icon_path))`.

3. **macOS Dock Icon**: For the macOS Dock, we use an Info.plist file that specifies the icon file to use.

## Creating a macOS Application Bundle

To create a proper macOS application bundle (.app) with the icon:

1. Install PyInstaller:
   ```
   pip install pyinstaller
   ```

2. Create the application bundle:
   ```
   pyinstaller --windowed --name="RWB" --icon=localknowledge/ui/icons/enthusiasticrobo_icon.png --add-data="localknowledge/ui/icons:localknowledge/ui/icons" run_rwb.py
   ```

3. The application bundle will be created in the `dist` directory.

## Troubleshooting

If the icon doesn't appear in the Dock:

1. Make sure the Info.plist file is being used by the application.
2. Try clearing the macOS icon cache:
   ```
   sudo rm -rfv /Library/Caches/com.apple.iconservices.store
   sudo find /private/var/folders/ -name com.apple.dock.iconcache -exec rm {} \;
   sudo find /private/var/folders/ -name com.apple.iconservices -exec rm -rf {} \;
   killall Dock
   ```
3. Restart the Dock:
   ```
   killall Dock
   ```
