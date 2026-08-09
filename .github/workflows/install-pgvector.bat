set "PGROOT=C:\Program Files\PostgreSQL\14"
cd $RUNNER_TEMP
git clone --branch v0.6.2 https://github.com/pgvector/pgvector.git
cd pgvector

for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VSINSTALLPATH=%%i
call "%VSINSTALLPATH%\VC\Auxiliary\Build\vcvars64.bat"
nmake /NOLOGO /F Makefile.win
nmake /NOLOGO /F Makefile.win install