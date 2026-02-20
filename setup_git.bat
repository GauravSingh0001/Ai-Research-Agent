@echo off
cls
echo Fixing Git repository...

:: Check if .git exists and remove it if corrupted (which it appears to be)
if exist .git (
    echo Removing corrupted .git directory...
    rmdir /s /q .git
)

:: Initialize new repository
echo Initializing new Git repository...
git init

:: Add all files
echo Adding files...
git add .

:: Commit changes
echo Committing changes...
git commit -m "Milestone 4 - Updated AI Research Agent Code"

:: Ask for remote URL
echo.
echo Please enter your GitHub repository URL (e.g. https://github.com/username/repo-name.git)
echo If you don't have one, press Enter to skip pushing.
set /p remote_url="Remote URL: "

if "%remote_url%"=="" goto done

:: Add remote and push
echo Adding remote origin...
git remote add origin %remote_url%
git branch -M main
echo Pushing to GitHub...
git push -u origin main --force

:done
echo.
echo Done!
pause
