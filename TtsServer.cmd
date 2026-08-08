@echo off
rem ---------------------------------------------------------------------------
rem GPT-SoVITS TTS server launcher. Double-click this file.
rem
rem This file must sit next to tts_server.py, inside the GPT-SoVITS checkout.
rem
rem It does NOT install GPT-SoVITS, voice weights, or tts_config.yaml - it
rem cannot: the weights are yours and the config needs a reference recording
rem plus its exact transcript. It checks what is missing, says exactly what to
rem do about it, and starts the server once everything is in place.
rem
rem KEEP THIS FILE ASCII-ONLY. cmd.exe reads batch files in the console code
rem page (cp949 on Korean Windows); UTF-8 Korean here renders as mojibake. All
rem Korean UI lives in tts_launcher.ps1, which PowerShell reads as UTF-8.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "tts_launcher.ps1" %*
