@echo off
:: Ensure Pillow is installed
python -c "import PIL" 2>nul || python -m pip install Pillow --quiet
:: Ensure pystray is installed
python -c "import pystray" 2>nul || python -m pip install pystray --quiet

start pythonw "%~dp0clock.py"
exit
