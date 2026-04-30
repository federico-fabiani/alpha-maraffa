@echo off
setlocal enabledelayedexpansion

set "PROJECT_ID=le-idee-di-feffo"
set "REGION=europe-west1"
set "SERVICE_NAME=aimaraffa"
set "AR_REPO=%SERVICE_NAME%"
set "IMAGE_URI=%REGION%-docker.pkg.dev/%PROJECT_ID%/%AR_REPO%/%SERVICE_NAME%:latest"

set "ROOT_DIR=%~dp0"
set "FRONTEND_DIR=%ROOT_DIR%game\frontend"
set "BACKEND_DIR=%ROOT_DIR%game\backend"
set "STATIC_DIR=%BACKEND_DIR%\src\aimaraffa\static"

where gcloud >nul 2>&1
if errorlevel 1 (
    echo Errore: gcloud non trovato nel PATH. Installa Google Cloud CLI o riapri il terminale.
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo Errore: npm non trovato nel PATH. Installa Node.js o riapri il terminale.
    exit /b 1
)

where docker >nul 2>&1
if errorlevel 1 (
    echo Errore: docker non trovato nel PATH. Avvia Docker Desktop e verifica il PATH.
    exit /b 1
)

echo [1/5] Build frontend...
pushd "%FRONTEND_DIR%" || goto :error
if not exist "node_modules" (
    call npm ci
    if errorlevel 1 goto :error
)
set "VITE_DEBUG_MODE=false"
call npm run build
if errorlevel 1 goto :error

echo [2/5] Copio il frontend in game\backend\src\aimaraffa\static...
if exist "%STATIC_DIR%" rmdir /s /q "%STATIC_DIR%"
mkdir "%STATIC_DIR%"
xcopy "%FRONTEND_DIR%\dist\*" "%STATIC_DIR%\" /e /i /y >nul
if errorlevel 1 goto :error
popd

echo [3/5] Build immagine Docker...
pushd "%BACKEND_DIR%" || goto :error
echo Assicuro che la repository Artifact Registry "%AR_REPO%" esista...
call gcloud artifacts repositories describe "%AR_REPO%" --project "%PROJECT_ID%" --location "%REGION%" >nul 2>&1
if errorlevel 1 (
    call gcloud artifacts repositories create "%AR_REPO%" --repository-format=docker --location "%REGION%" --project "%PROJECT_ID%" --description "Docker images for %SERVICE_NAME%"
    if errorlevel 1 goto :error
)
call gcloud auth configure-docker %REGION%-docker.pkg.dev --quiet
if errorlevel 1 goto :error
docker build -t "%IMAGE_URI%" .
if errorlevel 1 goto :error

echo [4/5] Push immagine Docker...
docker push "%IMAGE_URI%"
if errorlevel 1 goto :error

echo [5/5] Deploy su Cloud Run...
call gcloud run deploy "%SERVICE_NAME%" ^
    --image "%IMAGE_URI%" ^
    --project "%PROJECT_ID%" ^
    --region "%REGION%" ^
    --platform managed ^
    --allow-unauthenticated ^
    --memory 1Gi ^
    --quiet
if errorlevel 1 goto :error

popd
echo.
echo Completato. Immagine pubblicata: %IMAGE_URI%
exit /b 0

:error
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul 2>&1
popd >nul 2>&1
echo.
echo Errore durante il deploy. Exit code: %EXIT_CODE%
exit /b %EXIT_CODE%