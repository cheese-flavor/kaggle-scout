@echo off
cd /d "%~dp0"
if exist "dist\KaggleScout\KaggleScout.exe" (
  start "" "dist\KaggleScout\KaggleScout.exe"
) else (
  python app.py
)
