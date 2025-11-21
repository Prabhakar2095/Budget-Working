# Fresh Full-Stack App (New working)

Backend: FastAPI (Python)
Frontend: React (Vite)

## Quick Start

### 1. Backend
```
python -m venv .venv
.venv\\Scripts\\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8001
```
API base: http://localhost:8001

### 2. Frontend
```
cd frontend
npm install
npm run dev
```
Frontend dev server: http://localhost:5174

Create a `.env` in `frontend` if you change backend port:
```
VITE_API_BASE=http://localhost:8001
```

## Endpoints
- GET /api/health -> health status
- GET /api/sample/budget -> mock budget summary
- POST /api/budget/calculate -> placeholder for future calculation

## Structure
```
New working/
  backend/
    main.py
    requirements.txt
  frontend/
    index.html
    package.json
    vite.config.js
    src/
      main.jsx
      App.jsx
      api.js
```
