# Research AI Agent -- Architecture & Security Guide

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Service Communication Flow](#service-communication-flow)
- [Authentication: Sessions vs JWT](#authentication-sessions-vs-jwt)
- [SESSION_SECRET Explained](#session_secret-explained)
- [How Login Works (Step by Step)](#how-login-works-step-by-step)
- [All Secrets & Credentials Explained](#all-secrets--credentials-explained)
- [How to Generate Secrets](#how-to-generate-secrets)
- [Database Schemas](#database-schemas)
- [Docker Architecture](#docker-architecture)
- [CI/CD Pipeline](#cicd-pipeline)

---

## Architecture Overview

```
                    ┌─────────────────────────┐
                    │       User Browser       │
                    └────────────┬─────────────┘
                                 │ HTTP (port 80/5173)
                    ┌────────────▼─────────────┐
                    │   Frontend (React/Nginx)  │
                    │   Vite + TypeScript       │
                    │   shadcn/ui + Tailwind    │
                    └────────────┬─────────────┘
                                 │ /api/* proxied
                    ┌────────────▼─────────────┐
                    │   Go Backend (Chi Router) │◄──── Only public API
                    │   Port 8080               │
                    └──┬────┬────┬────┬────┬───┘
                       │    │    │    │    │
          ┌────────────┘    │    │    │    └────────────┐
          ▼                 ▼    │    ▼                  ▼
   ┌─────────────┐  ┌──────────┐│ ┌──────────┐  ┌─────────────┐
   │ PostgreSQL  │  │  Redis   ││ │  MongoDB  │  │    MinIO     │
   │ Users/Auth  │  │ Sessions ││ │ Research  │  │  PDF / .tex  │
   │ Port 5432   │  │ Port 6379││ │ Port 27017│  │  Port 9000   │
   └─────────────┘  └──────────┘│ └──────────┘  └─────────────┘
                                │
                   ┌────────────▼─────────────┐
                   │  Python AI Service       │◄──── Internal only
                   │  FastAPI + Mistral AI    │      (not exposed)
                   │  DuckDuckGo + TeX Live   │
                   │  Port 8000               │
                   └──────────────────────────┘
```

**Key design rule**: The Go backend is the **only** service exposed to the internet. The Python AI service is internal-only (Docker network only). The frontend proxies all `/api/*` requests to the Go backend.

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19 | UI framework |
| Vite | 6 | Build tool & dev server |
| TypeScript | 5.7 | Type safety |
| Tailwind CSS | 4 | Utility-first styling |
| shadcn/ui | latest | Pre-built UI components (Button, Card, Input, etc.) |
| React Router | 7 | Client-side routing |
| KaTeX | 0.16 | Render LaTeX math in the browser |
| DOMPurify | 3.x | Sanitize HTML to prevent XSS |

### Backend (Go)
| Technology | Purpose |
|---|---|
| Go 1.22+ | Language |
| chi/v5 | HTTP router |
| pgx/v5 | PostgreSQL driver (connection pool) |
| mongo-driver | MongoDB driver |
| go-redis/v9 | Redis client |
| minio-go/v7 | MinIO (S3-compatible) client |
| bcrypt | Password hashing |
| google/uuid | Session ID generation |

### AI Service (Python)
| Technology | Purpose |
|---|---|
| FastAPI | HTTP framework |
| uvicorn | ASGI server |
| mistralai | Mistral AI SDK |
| duckduckgo-search | Web search |
| tenacity | Retry with exponential backoff |
| xhtml2pdf | Fallback PDF generation |
| TeX Live | Native LaTeX-to-PDF compilation |

### Infrastructure
| Service | Image | Purpose |
|---|---|---|
| PostgreSQL 16 | `postgres:16-alpine` | User accounts (id, username, email, hashed password) |
| MongoDB 7 | `mongo:7` | Research documents (topic, LaTeX, sources, metadata) |
| Redis 7 | `redis:7-alpine` | Session storage (session_id -> user_id mapping with TTL) |
| MinIO | `minio/minio` | Object storage for PDF and .tex files |

---

## Service Communication Flow

When a user submits a research topic, here's exactly what happens:

```
1. Browser → Frontend:    User types topic, clicks "Start Research"
2. Frontend → Go Backend: POST /api/research/ {topic, model, depth, api_key}
3. Go Backend → Redis:    Validate session cookie → get user_id
4. Go Backend → AI Svc:   POST /api/generate-queries {topic, model, api_key}
5. AI Service → Mistral:  "Generate 5 search queries for this topic"
6. AI Svc → Go Backend:   {queries: ["query1", "query2", ...]}
7. Go Backend → AI Svc:   POST /api/search {queries, results_per_query}
8. AI Service → DDG:      Run each query on DuckDuckGo
9. AI Svc → Go Backend:   {results: [{title, body, href}, ...]}
10. Go Backend → AI Svc:  POST /api/generate-report {topic, context, sources}
11. AI Service → Mistral: "Write a LaTeX research report using these sources"
12. AI Svc → Go Backend:  {latex_body: "\\section{...} ..."}
13. Go Backend → AI Svc:  POST /api/compile-pdf {latex_body, title}
14. AI Svc → pdflatex:    Compile LaTeX → PDF bytes
15. AI Svc → Go Backend:  PDF binary data
16. Go Backend → MinIO:   Upload PDF and .tex files
17. Go Backend → MongoDB: Save research document (topic, LaTeX, sources, keys)
18. Go Backend → Browser: JSON response with the full research document
19. Frontend:             Navigate to /report/:id, render LaTeX as HTML with KaTeX
```

---

## Authentication: Sessions vs JWT

### This project uses SESSION-BASED auth, NOT JWT.

Here's the difference and why:

### JWT (JSON Web Token)
```
How it works:
  1. User logs in → server creates a signed token containing {user_id, expiry}
  2. Token is sent to browser → stored in localStorage or cookie
  3. Every request includes the token
  4. Server verifies the signature using a secret key
  5. Server does NOT need to store anything — the token IS the proof

Pros: Stateless, no server-side storage needed
Cons: Can't revoke a token (user stays "logged in" until it expires),
      token size grows with claims, XSS risk if stored in localStorage
```

### Session-Based (what we use)
```
How it works:
  1. User logs in → server generates a random UUID (session ID)
  2. Server stores "session:UUID → user_id" in Redis with 24h TTL
  3. Session ID is sent to browser as an HttpOnly cookie
  4. Every request includes the cookie automatically
  5. Server looks up the session ID in Redis to get the user_id
  6. On logout → server deletes the session from Redis immediately

Pros: Can revoke instantly (delete from Redis), small cookie size,
      HttpOnly cookie prevents XSS, server has full control
Cons: Requires Redis (or similar) for server-side storage
```

### Why sessions over JWT for this project?
- We already have Redis for caching, so the "extra storage" cost is zero
- Instant logout (delete the Redis key = session gone immediately)
- HttpOnly cookies are more secure than localStorage tokens
- Simpler implementation, fewer attack vectors

---

## SESSION_SECRET Explained

### What is it?
`SESSION_SECRET` is a **random string** stored in your `.env` file. In the current implementation, it's available as a config field but the actual session security comes from Redis-backed opaque session IDs.

### How sessions actually work in this codebase:

```go
// backend/internal/auth/session.go

// When user logs in:
func (s *SessionStore) Create(ctx context.Context, userID string) (string, error) {
    sid := uuid.New().String()   // Generate random UUID like "a1b2c3d4-e5f6-..."
    // Store in Redis: key="session:a1b2c3d4-e5f6-..." value="user-uuid" TTL=24h
    err := s.rdb.Set(ctx, "session:"+sid, userID, SessionTTL).Err()
    return sid, err
}

// When checking auth on each request:
func (s *SessionStore) Get(ctx context.Context, sessionID string) (string, error) {
    // Look up "session:a1b2c3d4-e5f6-..." in Redis → returns user_id or nil
    val, err := s.rdb.Get(ctx, "session:"+sessionID).Result()
    if err == redis.Nil {
        return "", nil  // Session expired or doesn't exist
    }
    return val, err
}
```

### The cookie sent to the browser:

```go
// backend/internal/auth/handler.go (Login function)

http.SetCookie(w, &http.Cookie{
    Name:     "session_id",           // Cookie name
    Value:    sid,                     // The random UUID
    Path:     "/",
    HttpOnly: true,                   // JavaScript CANNOT read this cookie
    SameSite: http.SameSiteLaxMode,   // CSRF protection
    MaxAge:   86400,                  // 24 hours in seconds
})
```

### What HttpOnly means:
- The browser sends the cookie automatically with every request
- JavaScript (`document.cookie`) **cannot** access it — this prevents XSS attacks
- Only the server can read and validate it

### What SESSION_SECRET is for:
The `SESSION_SECRET` env var is reserved for future use (e.g., if you add signed cookies or HMAC session validation). Currently, security comes from:
1. The session ID is a **cryptographically random UUID** (unguessable)
2. The mapping lives only in **Redis** (server-side, not in the cookie)
3. The cookie is **HttpOnly** (can't be stolen by JS)
4. Sessions **auto-expire** after 24 hours

### How to generate it:
It's just a long random string. Generate with any of these:

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(48))"

# OpenSSL
openssl rand -base64 48

# PowerShell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Max 256 }) -as [byte[]])

# Node.js
node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"
```

---

## How Login Works (Step by Step)

```
┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
│ Browser  │         │ Frontend │         │ Go Backend│         │  Redis   │
└────┬─────┘         └────┬─────┘         └────┬─────┘         └────┬─────┘
     │                     │                    │                     │
     │ 1. Type email+pass  │                    │                     │
     │ click "Sign In"     │                    │                     │
     │────────────────────>│                    │                     │
     │                     │                    │                     │
     │                     │ 2. POST /api/auth/login                  │
     │                     │  {email, password} │                     │
     │                     │───────────────────>│                     │
     │                     │                    │                     │
     │                     │            3. Query PostgreSQL            │
     │                     │               SELECT * FROM users        │
     │                     │               WHERE email = ?            │
     │                     │                    │                     │
     │                     │            4. bcrypt.Compare              │
     │                     │               (stored_hash, password)     │
     │                     │               ✓ Match!                   │
     │                     │                    │                     │
     │                     │                    │ 5. SET session:uuid  │
     │                     │                    │    = user_id         │
     │                     │                    │    EX 86400          │
     │                     │                    │───────────────────>  │
     │                     │                    │                     │
     │                     │ 6. Response + Set-Cookie header           │
     │                     │    Set-Cookie: session_id=uuid;           │
     │                     │                HttpOnly; SameSite=Lax    │
     │                     │<───────────────────│                     │
     │                     │                    │                     │
     │ 7. Browser stores   │                    │                     │
     │    cookie auto-     │                    │                     │
     │    matically         │                    │                     │
     │<────────────────────│                    │                     │
     │                     │                    │                     │
     │ 8. Next request: GET /api/research/      │                     │
     │    Cookie: session_id=uuid (auto-sent)   │                     │
     │────────────────────────────────────────>  │                     │
     │                     │                    │ 9. GET session:uuid  │
     │                     │                    │───────────────────>  │
     │                     │                    │    returns user_id   │
     │                     │                    │<───────────────────  │
     │                     │                    │                     │
     │                     │           10. ✓ Authenticated!           │
     │                     │               Process request             │
```

---

## All Secrets & Credentials Explained

| Variable | Where Used | What It Does | Who Needs It |
|---|---|---|---|
| `MISTRAL_API_KEY` | Passed per-request from frontend → backend → AI service | Authenticates with Mistral AI API to generate search queries and reports | You get this from [console.mistral.ai](https://console.mistral.ai) |
| `POSTGRES_USER` | PostgreSQL + Go backend | Username to connect to PostgreSQL | Auto-created by PostgreSQL container on first start |
| `POSTGRES_PASSWORD` | PostgreSQL + Go backend | Password to connect to PostgreSQL | Auto-created by PostgreSQL container on first start |
| `POSTGRES_DB` | PostgreSQL + Go backend | Database name | Auto-created by PostgreSQL container on first start |
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB + Go backend | Root username for MongoDB | Auto-created by MongoDB container on first start |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB + Go backend | Root password for MongoDB | Auto-created by MongoDB container on first start |
| `MONGO_DB` | Go backend | Which MongoDB database to use for research docs | Just a name, created automatically |
| `REDIS_PASSWORD` | Redis + Go backend | Password to connect to Redis | Set via `--requirepass` on Redis startup |
| `MINIO_ACCESS_KEY` | MinIO + Go backend | MinIO "username" (like AWS Access Key ID) | Auto-created by MinIO container on first start |
| `MINIO_SECRET_KEY` | MinIO + Go backend | MinIO "password" (like AWS Secret Access Key) | Auto-created by MinIO container on first start |
| `MINIO_BUCKET` | Go backend | S3 bucket name for PDF/tex storage | Created automatically by Go backend on startup |
| `SESSION_SECRET` | Go backend | Reserved for session signing (security key) | You generate it — just a random string |

### Where do secrets come from?

```
┌─────────────────────────────────────────────────────────────┐
│                     .env file                                │
│                                                              │
│  Secrets you generate yourself (random strings):             │
│    POSTGRES_PASSWORD ──── random, you pick it                │
│    MONGO_INITDB_ROOT_PASSWORD ── random, you pick it         │
│    REDIS_PASSWORD ──────── random, you pick it               │
│    MINIO_ACCESS_KEY ────── random, you pick it               │
│    MINIO_SECRET_KEY ────── random, you pick it               │
│    SESSION_SECRET ──────── random, you pick it               │
│                                                              │
│  Secrets from external services:                             │
│    MISTRAL_API_KEY ────── from console.mistral.ai            │
│                                                              │
│  Names you choose (not secrets):                             │
│    POSTGRES_USER ──────── "postgres" is fine                 │
│    POSTGRES_DB ─────────── "research" is fine                │
│    MONGO_INITDB_ROOT_USERNAME ── "mongoadmin" is fine        │
│    MONGO_DB ────────────── "research_agent" is fine          │
│    MINIO_BUCKET ────────── "research-pdfs" is fine           │
└─────────────────────────────────────────────────────────────┘
```

**None of these secrets come from an external service** (except `MISTRAL_API_KEY`). You generate all the passwords yourself. The Docker containers read them on first startup and use them to initialize their authentication.

---

## How to Generate Secrets

Run this single command to generate all passwords at once:

```bash
python -c "
import secrets
print(f'POSTGRES_PASSWORD={secrets.token_urlsafe(24)}')
print(f'MONGO_INITDB_ROOT_PASSWORD={secrets.token_urlsafe(24)}')
print(f'REDIS_PASSWORD={secrets.token_urlsafe(24)}')
print(f'MINIO_ACCESS_KEY={secrets.token_urlsafe(16)}')
print(f'MINIO_SECRET_KEY={secrets.token_urlsafe(32)}')
print(f'SESSION_SECRET={secrets.token_urlsafe(48)}')
"
```

Copy the output into your `.env` file.

---

## Database Schemas

### PostgreSQL -- Users Table

```sql
CREATE TABLE users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username   VARCHAR(50) UNIQUE NOT NULL,
    email      VARCHAR(255) UNIQUE NOT NULL,
    password   VARCHAR(255) NOT NULL,     -- bcrypt hash, never plaintext
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Passwords are **never stored in plaintext**. They are hashed with bcrypt (cost factor 10):
```
Input:  "mypassword123"
Stored: "$2a$10$N9qo8uLOickgx2ZMRZoMye..."  (60 chars, irreversible)
```

### MongoDB -- Research Collection

```json
{
  "_id": "ObjectId('...')",
  "user_id": "uuid-from-postgres",
  "topic": "Impact of LLMs on scientific research",
  "latex_content": "\\section{Introduction} ...",
  "sources": [
    {"title": "Source Title", "body": "Description...", "href": "https://..."}
  ],
  "model_used": "mistral-medium-latest",
  "search_queries": ["LLM scientific research", "AI papers 2025", ...],
  "pdf_object_key": "user-uuid/Impact of LLMs on.pdf",
  "tex_object_key": "user-uuid/Impact of LLMs on.tex",
  "created_at": "2025-02-11T10:30:00Z"
}
```

### Redis -- Session Storage

```
Key:   "session:a1b2c3d4-e5f6-7890-abcd-ef1234567890"
Value: "550e8400-e29b-41d4-a716-446655440000"   (user UUID)
TTL:   86400 seconds (24 hours)
```

---

## Docker Architecture

### Development (`docker-compose.dev.yml`)

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Network                          │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ postgres │  │ mongodb  │  │  redis   │  │  minio  │ │
│  │  :5432   │  │  :27017  │  │  :6379   │  │ :9000/1 │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                                          │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │ ai-service   │  │  backend   │  │    frontend      │ │
│  │ Python+TeX   │  │  Go binary │  │  Vite dev server │ │
│  │ :8000        │  │  :8080     │  │  :5173           │ │
│  │ HOT RELOAD   │  │            │  │  HOT RELOAD      │ │
│  │ (volume mnt) │  │            │  │  (volume mnt)    │ │
│  └──────────────┘  └────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Production (`docker-compose.yml`)

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Network                          │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ postgres │  │ mongodb  │  │  redis   │  │  minio  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                                          │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │ ai-service   │  │  backend   │  │    frontend      │ │
│  │ ghcr.io/...  │  │ ghcr.io/.. │  │  ghcr.io/...    │ │
│  │ (pre-built)  │  │ (pre-built)│  │  Nginx + static  │ │
│  │ NO mounts    │  │ NO mounts  │  │  :80 ──► public  │ │
│  └──────────────┘  └────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## CI/CD Pipeline

```
Developer clicks "Run workflow" in GitHub Actions
            │
            ▼  (inputs: version = "1.0.0")
    ┌───────────────────────────────┐
    │   build-and-push (matrix)     │
    │                               │
    │   ┌─────────┐ ┌───────────┐ ┌──────────┐
    │   │ backend │ │ ai-service│ │ frontend │  (parallel)
    │   └────┬────┘ └─────┬─────┘ └────┬─────┘
    │        │             │            │
    │   Docker build  Docker build  Docker build
    │        │             │            │
    │   Push to ghcr  Push to ghcr Push to ghcr
    │   :1.0.0         :1.0.0       :1.0.0
    │   :latest        :latest      :latest
    └───────────────────┬───────────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │   create-release    │
              │                     │
              │   git tag v1.0.0    │
              │   GitHub Release    │
              └─────────────────────┘
```

Images are pushed to:
- `ghcr.io/xeze-org/research-ai-agent-backend:1.0.0`
- `ghcr.io/xeze-org/research-ai-agent-ai-service:1.0.0`
- `ghcr.io/xeze-org/research-ai-agent-frontend:1.0.0`

To deploy a new version on your server:
```bash
VERSION=1.0.0 docker compose up -d
```

---

## Security Summary

| Layer | Mechanism | Details |
|---|---|---|
| Password storage | bcrypt | Passwords are hashed with cost factor 10, never stored in plaintext |
| Session management | Redis + UUID | Random UUID session IDs stored in Redis with 24h TTL |
| Cookie security | HttpOnly + SameSite | Cookies can't be read by JavaScript, CSRF-protected |
| API protection | Session middleware | Every `/api/research/*` route requires a valid session |
| Internal services | Docker network | AI service is not exposed to the internet |
| Credentials | `.env` file | All passwords in one file, never committed to git |
| Container registry | ghcr.io + GITHUB_TOKEN | Images pushed with GitHub's built-in auth |
