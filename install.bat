@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
echo Edit .env, then run start.bat.
docker compose build
