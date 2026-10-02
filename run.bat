@echo off
REM Launches the Nuke Raider ROM in Emulicious.
REM Builds first if the ROM doesn't exist yet.

setlocal
set "ROM=%~dp0build\nuke-raider.gb"
set "EMULICIOUS=C:\Tools\Emulicious\Emulicious.jar"

if not exist "%ROM%" (
    echo ROM not found, building first...
    set "GBDK_HOME=C:/gbdk"
    set "PATH=C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;C:\Users\mathd\Documents\mingw64\bin;C:\gbdk\bin;%PATH%"
    call make
    if errorlevel 1 (
        echo Build failed.
        exit /b 1
    )
)

start "" java -jar "%EMULICIOUS%" "%ROM%"
endlocal
