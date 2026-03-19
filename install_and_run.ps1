# Beta Video Dubbing Version
Write-Host "Setting up Beta Version..." -ForegroundColor Cyan

# Check for Python
python --version
if ($?) {
    Write-Host "Python found." -ForegroundColor Green
}
else {
    Write-Host "Please install Python." -ForegroundColor Red
    exit
}

# Setup Backend
Write-Host "Setting up Backend..." -ForegroundColor Yellow
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cd ..

# Setup Frontend
Write-Host "Setting up Frontend..." -ForegroundColor Yellow
cd frontend
npm install
cd ..

Write-Host "Setup Complete! Running App..." -ForegroundColor Green

# Launch App
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\activate; uvicorn main:app --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
