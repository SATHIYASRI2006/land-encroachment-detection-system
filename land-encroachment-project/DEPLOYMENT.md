# Deployment Guide

This project can be deployed as:

- `frontend` -> static site
- `backend` -> Python web service

Suggested hosting:

- Frontend: Render Static Site
- Backend: Render Web Service

## 1. Backend deployment

Backend folder:

- `land-encroachment-project/backend`

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn --worker-class eventlet -w 1 app:app
```

Important environment variables:

- `JWT_SECRET`
- `ALLOW_LEGACY_ANONYMOUS=true`
- `AUTO_MONITOR_INTERVAL_MINUTES=10`
- `ALERT_EMAIL_COOLDOWN_MINUTES=120`
- `REALTIME_INGEST_ENABLED=true`
- `REALTIME_INGEST_INTERVAL_SECONDS=30`
- `EMAIL_USER`
- `EMAIL_PASS`
- `EMAIL_TO`

## 2. Frontend deployment

Frontend folder:

- `land-encroachment-project/frontend`

Build command:

```bash
npm install && npm run build
```

Publish directory:

```bash
build
```

Frontend environment variables:

- `REACT_APP_API_BASE_URL=https://your-backend-service.onrender.com`
- `REACT_APP_SOCKET_URL=https://your-backend-service.onrender.com`

## 3. SPA routing

The file below is added so React routes work after refresh:

- `frontend/public/_redirects`

## 4. Mobile support

This project now includes:

- mobile menu drawer
- responsive cards and tables
- mobile-safe map height
- responsive evidence viewer
- stacked topbar actions on small screens

## 5. Realtime workflow after deployment

1. backend service starts
2. realtime inbox folders are created automatically
3. image manifests can be dropped into backend live feed folders
4. backend processes them automatically
5. frontend updates through API and socket refresh

## 6. Important note

For production, SQLite works for demo and academic deployment, but PostgreSQL is better for a larger real system.
