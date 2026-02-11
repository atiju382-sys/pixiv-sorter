import PyInstaller.__main__
import os
import customtkinter

# Get customtkinter path for bundling assets
ctk_path = os.path.dirname(customtkinter.__file__)

PyInstaller.__main__.run([
    'gui.py',
    '--name=PixivSorter',
    '--onefile',
    '--noconsole',
    f'--add-data={ctk_path}{os.pathsep}customtkinter',
    f'--add-data=style.css{os.pathsep}.',
    '--clean',
])

print("\n[+] Build complete! Check the 'dist' folder for PixivSorter.exe")
