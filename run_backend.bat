@echo off
cd /d "%~dp0"
if not exist backend\.env (echo Missing backend\.env - copy backend\.env.example and edit it. & exit /b 1)
python backend\app.py
