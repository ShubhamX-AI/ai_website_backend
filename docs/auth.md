# Auth System

FastAPI handles all auth logic. Next.js handles UI and cookie storage.

---

## Overview

Two login methods:

| Method | Who uses it | Role assigned |
|---|---|---|
| Email + password | Pre-created users (admin or client) | Stored in MongoDB `users` collection |
| Google OAuth | Company employees or external visitors | Based on email domain (see below) |

---

## Roles

| Role | Token expiry | `expires_at` returned | Access window |
|---|---|---|---|
| `admin` | 30 days (JWT) | `null` / `""` — frontend never auto-logs out | No window restriction |
| `client` | 4 hours (JWT) | ms epoch timestamp | First-login window enforced (see below) |

---

## Client Access Window

Clients get a fixed window from their **first login**, controlled by `CLIENT_ACCESS_WINDOW_HOURS` in `.env`.

```
Client created in DB  →  no timer yet
        ↓
First POST /auth/login  →  first_login_at stamped in MongoDB  →  window starts
        ↓
Re-login within window  →  allowed, fresh 4h JWT each time
        ↓
Login after window expires  →  403 "Access window expired"
```

To reset a client's window (give fresh access):
```js
db.users.updateOne({ email: "client@x.com" }, { $unset: { first_login_at: "" } })
```

---

## Endpoints

### `POST /auth/login`

**Request:**
```json
{ "email": "user@example.com", "password": "secret" }
```

**Responses:**
| Status | Meaning |
|---|---|
| `200` | `{ token, role, expires_at }` |
| `401` | Wrong email or password |
| `403` | Client's access window has expired |

**200 Response:**
```json
{
  "token": "<jwt>",
  "role": "admin" | "client",
  "expires_at": 1234567890000   // ms epoch for client, null for admin
}
```

Next.js receives this and sets `auth_session` httpOnly cookie as:
```json
{ "token": "<jwt>" }
```

---

### `GET /auth/google`

Redirects browser to Google consent screen. No request body needed.

Frontend just links to: `${BACKEND_URL}/auth/google`

---

### `GET /auth/google/callback`

Google calls this on FastAPI (NOT Next.js). FastAPI exchanges the code, finds/creates user, issues JWT, then redirects to Next.js:

```
http://localhost:3000/api/auth/google/callback
  ?token=<jwt>
  &role=admin|client
  &expires_at=<ms_epoch_or_empty_string>
```

Note: `expires_at` is an empty string `""` for admin (not `null` — can't send null in URL).

**Google domain-based role assignment:**
- Email domain == `ADMIN_DOMAIN` env var → `role = "admin"`
- Any other domain → `role = "client"`
- Returning user → keeps their existing role from DB (not reassigned)

---

### `POST /auth/logout`

Returns `{ "success": true }`. Cookie deletion is handled by Next.js.

---

## Protecting Routes (FastAPI)

```python
from src.auth.dependencies import get_current_user, require_admin

@app.get("/some-protected-route")
def protected(user=Depends(get_current_user)):
    # user = {"sub": "email@example.com", "role": "client"}
    ...

@app.get("/admin-only")
def admin_only(user=Depends(require_admin)):
    ...
```

FastAPI reads `auth_session` cookie → parses `{ "token": "..." }` → validates JWT.

---

## MongoDB Schema

Collection: `users`

| Field | Type | Notes |
|---|---|---|
| `email` | string | unique, indexed |
| `hashed_password` | string or null | null for Google-only users |
| `role` | string | `"admin"` or `"client"` |
| `google_id` | string or null | Google `sub` claim |
| `created_at` | datetime | UTC |
| `first_login_at` | datetime or null | stamped on first password login; used for client access window |

---

## Creating Users Manually

No register endpoint. Insert directly into MongoDB:

```python
from passlib.hash import bcrypt
from datetime import datetime, timezone

user = {
    "email": "admin@yourcompany.com",
    "hashed_password": bcrypt.hash("yourpassword"),
    "role": "admin",
    "created_at": datetime.now(timezone.utc),
    "first_login_at": None,
}
db["users"].insert_one(user)
```

Or via mongosh:
```js
db.users.insertOne({
  email: "client@example.com",
  hashed_password: "<bcrypt hash>",  // use python to generate
  role: "client",
  created_at: new Date(),
  first_login_at: null
})
```

---

## Environment Variables

```env
SECRET_KEY=<openssl rand -hex 32>
CLIENT_SESSION_HOURS=4              # JWT lifespan for client tokens
CLIENT_ACCESS_WINDOW_HOURS=4        # Total window from first login (increase to extend access)

GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
NEXTJS_CALLBACK_URL=http://localhost:3000/api/auth/google/callback
ADMIN_DOMAIN=yourcompany.com        # @this domain → admin on Google login

MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ai_website
```

---

## Full Auth Flow Diagram

```
Password Login:
  Frontend → POST /auth/login → FastAPI validates → returns {token, role, expires_at}
  Next.js sets auth_session cookie → user is logged in

Google Login:
  Frontend → GET /auth/google → FastAPI → Google consent screen
  Google → GET /auth/google/callback (FastAPI)
  FastAPI issues JWT → redirects to Next.js /api/auth/google/callback?token=...
  Next.js sets auth_session cookie → redirects to /landing

Protected Request:
  Frontend sends request with auth_session cookie
  FastAPI get_current_user() reads cookie → verifies JWT
  Expired/missing → 401 → Next.js redirects to login
```

---

## Frontend Integration Checklist

- [ ] `POST /auth/login` — handle `401` (bad creds) and `403` (window expired)
- [ ] Google login button → link/redirect to `${BACKEND_URL}/auth/google`
- [ ] `GET /api/auth/google/callback` on Next.js — parse `?token=...&role=...&expires_at=...`, treat `expires_at=""` as null
- [ ] Set `auth_session` cookie as JSON string `{ "token": "<jwt>" }`
- [ ] On any `401` response from protected routes → redirect to login
