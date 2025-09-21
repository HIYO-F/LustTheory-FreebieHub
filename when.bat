@echo off
REM WHEN Language Command-Line Tool for Windows
REM This batch file allows you to run WHEN programs with just "when filename.when"

REM Get the directory where this batch file is located
SET WHEN_DIR=%~dp0

REM Run the WHEN interpreter with Python
python "%WHEN_DIR%when.py" %*