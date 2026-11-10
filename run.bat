@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\KaggleScout\versions\0.10.2\KaggleScout.exe" (
  start "" "%LOCALAPPDATA%\Programs\KaggleScout\versions\0.10.2\KaggleScout.exe"
  exit /b
)
if exist "dist\KaggleScout\KaggleScout.exe" (
  start "" "dist\KaggleScout\KaggleScout.exe"
) else (
  python app.py
)
