# Playto KYC Challenge

This repository contains a working KYC onboarding service for Playto Pay.

## Structure

- `backend/` - Django + DRF backend
- `frontend/` - React + Tailwind frontend

## Setup

### Backend

1. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend/requirements.txt
   ```
2. Run migrations:
   ```powershell
   python backend\manage.py migrate
   ```
3. Load seed data:
   ```powershell
   python backend\manage.py seed_data
   ```
4. Start backend server:
   ```powershell
   python backend\manage.py runserver
   ```

### Frontend

1. Install dependencies:
   ```powershell
   cd frontend
   npm install
   ```
2. Create a local env file:
   ```powershell
   copy .env.example .env.local
   ```
3. Start the frontend:
   ```powershell
   npm run dev
   ```

### Environment

The frontend uses `VITE_API_BASE` to call the backend.
- Local dev can use the Vite proxy configuration
- Production deploys must set `VITE_API_BASE` to the deployed backend URL

### Seed accounts

- Reviewer: `reviewer` / `password`
- Merchant draft: `merchant_draft` / `password`
- Merchant under review: `merchant_under_review` / `password`

You can also register new accounts using the registration form in the frontend.

## Notes

- API base path: `/api/v1/`
- File upload rules: only PDF/JPG/PNG, max 5 MB
- State machine is enforced in `backend/kyc/models.py`
- Notifications are stored in `backend/kyc/models.py` using the `Notification` model

## Tests

Run backend tests with:
```powershell
python backend\manage.py test
```

## Deployment

### Frontend (Vercel)

1. Push changes to GitHub (already done).
2. Go to [Vercel Dashboard](https://vercel.com/dashboard).
3. Select your project (playto-frontend).
4. Go to Settings > Environment Variables.
5. Add `VITE_API_BASE` with your deployed backend URL (e.g., `https://your-backend.herokuapp.com/api/v1`).
6. Redeploy: Go to Deployments tab and trigger a new deploy, or push to GitHub to auto-deploy.

### Backend (Railway/Render)

1. Create an account on [Railway](https://railway.app) or [Render](https://render.com).
2. Connect your GitHub repo.
3. Set build command: `pip install -r requirements.txt && python manage.py migrate && python manage.py seed_data`
4. Set start command: `gunicorn playtopay.wsgi --bind 0.0.0.0:$PORT`
5. Add environment variables:
   - `SECRET_KEY`: Generate a new secret key
   - `DEBUG`: False
   - `ALLOWED_HOSTS`: Your domain (e.g., your-app.railway.app)
   - `DATABASE_URL`: Provided by Railway/Render
6. Deploy and get the URL (e.g., https://your-app.railway.app).
7. Update frontend's `VITE_API_BASE` with this URL + `/api/v1`.
