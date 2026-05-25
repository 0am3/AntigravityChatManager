@echo off
echo Building AntiGravity Chat Manager...
pyinstaller --noconfirm --onefile --windowed --name "AntiGravityChatManager" app.py
echo.
echo Build complete! Check the dist/ folder for the executable.
