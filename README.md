# Plymouth Theme Manager

A simple GUI tool for managing Plymouth boot splash themes on Arch Linux.

## What it does

You drop a theme archive into the window and it handles everything — extracting, installing, setting the theme as default and rebuilding the initramfs. It remembers which themes you have installed so it never installs the same thing twice. You can switch between themes with one click, remove ones you don't want, or disable the boot splash entirely if you prefer a clean text boot.

## Requirements

Python 3 and Tkinter need to be installed:

```
sudo pacman -S python tk
```

For drag and drop support install tkinterdnd2:

```
pip install tkinterdnd2 --break-system-packages
```

Without tkinterdnd2 the app still works, you just use the browse button instead of drag and drop.

Plymouth also needs to be installed and configured:

```
sudo pacman -S plymouth
```

Make sure plymouth is in your mkinitcpio HOOKS and that your kernel cmdline includes `quiet splash`. Check the Arch Wiki for full Plymouth setup instructions.

## Supported formats

ZIP, tar.gz, tar.bz2, tar.xz, tar

## Usage

```
python3 plymouth-manager.py
```

Drop a theme archive onto the drop zone or click it to open a file browser. The app will install the theme and activate it automatically. To switch to a different already installed theme, select it from the list and click Activate. The star symbol shows which theme is currently active.

The Disable splash button switches to the built-in text theme which gives you a plain text boot with no graphics.

## Where to find themes

https://www.gnome-look.org/browse?cat=108

https://github.com/adi1090x/plymouth-themes

## License

GNU General Public License v3.0
