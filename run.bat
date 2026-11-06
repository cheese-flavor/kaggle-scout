@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\KaggleScout\versions\0.4.0\KaggleScout.exe" (
  start "" "%LOCALAPPDATA%\Programs\KaggleScout\versions\0.4.0\KaggleScout.exe"
  exit /b
)
if exist "dist\KaggleScout\KaggleScout.exe" (
  start "" "dist\KaggleScout\KaggleScout.exe"
) else (
  python app.py
)
