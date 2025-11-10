@echo off
rem run.bat - launches main.py with pythonw via start, hidden using temporary VBS
rem Place this file next to main.py. It will create a small VBS helper and run it invisibly.

setlocal
set "SCRIPT=%~dp0main.py"
set "PYTHONW=pythonw"
set "VBS=%TEMP%\main.vbs"

> "%VBS%" echo Set WshShell = CreateObject("WScript.Shell")
>> "%VBS%" echo cmd = "cmd /c start """" %PYTHONW% ""%SCRIPT%"""
>> "%VBS%" echo WshShell.Run cmd, 0, False

rem Run the VBS (wscript runs without a visible console). The VBS will start pythonw via start and return immediately.
wscript "%VBS%"

rem cleanup
del "%VBS%" >nul 2>&1
endlocal

exit /b 0