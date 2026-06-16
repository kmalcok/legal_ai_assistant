# How To Run Locally

This frontend supports host-based behavior in local development without nginx.

## Local hostnames

Use these hostnames while running the Vite dev server:

- `http://localhost:5173` for the fallback/local mixed mode
- `http://app.localhost:5173` for the app experience
- `http://admin.localhost:5173` for the admin panel

`app.localhost` and `admin.localhost` are handled directly in the frontend router, so developers do not need to add custom host entries for normal local usage.

## Start the frontend

Run the dev server with host binding enabled:

```bash
npm run dev -- --host
```

This makes the app reachable from `localhost`, `app.localhost`, and `admin.localhost` on the same port.

## Backend notes

Local backend config currently allows all origins in `backend/config-dev/api_config.json`, so no extra CORS change is required for:

- `http://app.localhost:5173`
- `http://admin.localhost:5173`

## Routing behavior

- `app.localhost:5173` behaves like `app.yargucu.com.tr`
- `admin.localhost:5173` behaves like `admin.yargucu.com.tr`
- `localhost:5173` remains the general local fallback mode

## Quick checks

1. Open `http://app.localhost:5173` and confirm `/` redirects into the app flow.
2. Open `http://admin.localhost:5173` and confirm the admin dashboard loads.
3. Open `http://localhost:5173` and confirm the general local fallback still works.
