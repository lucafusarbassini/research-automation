# Mobile Access

ricet includes a full mobile access system that lets you monitor and control research projects from your phone. The implementation uses only Python standard library modules -- no Flask, Django, or other web framework is required.

---

## Overview

The mobile system (`core/mobile.py` and `core/mobile_pwa.py`) provides:

- An HTTPS API server with self-signed TLS certificates
- A Progressive Web App (PWA) that works as a native-like phone app
- Bearer token authentication with SHA-256 hash storage
- Rate limiting per client IP (10 failures triggers a 15-minute lockout)
- QR code generation for easy phone pairing
- Multi-project management from a single server
- Voice command submission via the Web Speech API

---

## Quick Start

### Enable During Project Init

When running `ricet init`, answer "yes" to the mobile access question:

```
Do you need mobile access? (yes/no) [no]: yes
```

This stores the preference in `config/settings.yml`. When you run `ricet start`, the mobile server launches automatically alongside your Claude session.

### Manual Server Management

```bash
# Start the HTTPS server (port 8777)
ricet mobile serve

# Pair a device (generates a bearer token and QR code)
ricet mobile pair

# View connection methods (direct, SSH tunnel, WireGuard)
ricet mobile connect-info

# List active tokens
ricet mobile tokens

# Regenerate TLS certificates
ricet mobile cert-regen

# Check server status
ricet mobile status

# Stop the server
ricet mobile stop
```

---

## Architecture

### Components

| Component | Module | Purpose |
|-----------|--------|---------|
| `TLSManager` | `core/mobile.py` | Self-signed certificate generation via OpenSSL CLI |
| `MobileAuth` | `core/mobile.py` | Bearer token generation, validation, revocation, rate limiting |
| `MobileServer` | `core/mobile.py` | Route-based HTTP dispatch with auth and mobile-formatted responses |
| `ProjectRegistry` | `core/mobile.py` | Multi-project status and task management |
| PWA assets | `core/mobile_pwa.py` | HTML, CSS, JS, manifest, service worker, icon |

### Security Model

The mobile server uses a defense-in-depth approach:

1. **TLS encryption** -- Self-signed certificates generated via OpenSSL. The SHA-256 fingerprint is displayed for manual verification (SSH trust-on-first-use model).
2. **Bearer tokens** -- Only SHA-256 hashes are stored on disk (`~/.ricet/mobile_tokens.json`). The plaintext token is shown exactly once when generated.
3. **Rate limiting** -- 10 failed authentication attempts from a single IP triggers a 15-minute lockout.
4. **Minimal surface** -- PWA asset routes (`/`, `/manifest.json`, `/sw.js`, `/icon.svg`) bypass auth; all API routes require a valid token.

---

## API Endpoints

All API responses are JSON with a `_ts` timestamp and string values truncated to 280 characters for mobile readability.

### Core Endpoints

| Method | Path | Purpose | Auth Required |
|--------|------|---------|---------------|
| `GET` | `/` | PWA HTML page (installable app) | No |
| `GET` | `/manifest.json` | PWA manifest | No |
| `GET` | `/sw.js` | Service worker for offline support | No |
| `GET` | `/icon.svg` | App icon | No |
| `GET` | `/status` | Server status (running tasks, queue size) | Yes |
| `GET` | `/sessions` | List project sessions | Yes |
| `GET` | `/progress` | Recent task entries (last 10) | Yes |
| `POST` | `/task` | Submit a new task | Yes |
| `POST` | `/voice` | Submit voice-transcribed text as a task | Yes |
| `GET` | `/connect-info` | TLS fingerprint and connection methods | Yes |

### Multi-Project Endpoints

| Method | Path | Purpose | Auth Required |
|--------|------|---------|---------------|
| `GET` | `/projects` | List all registered ricet projects | Yes |
| `GET` | `/project/status?name=X` | Get a specific project's progress and sessions | Yes |
| `POST` | `/project/task?name=X` | Submit a task to a specific project | Yes |

### Example Requests

**Submit a task:**

```bash
curl -k -X POST https://192.168.1.100:8777/task \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate a confusion matrix for the test set"}'
```

Response:

```json
{
  "ok": true,
  "task_id": "a1b2c3d4e5f6",
  "status": "queued",
  "_ts": "2026-02-02T10:30:00+00:00"
}
```

**Check project status:**

```bash
curl -k https://192.168.1.100:8777/project/status?name=my-project \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:

```json
{
  "ok": true,
  "name": "my-project",
  "progress": "## Week 1\n- Completed literature review...",
  "sessions": [
    {"name": "20260201_143000", "status": "completed"},
    {"name": "20260202_091500", "status": "active"}
  ],
  "_ts": "2026-02-02T10:31:00+00:00"
}
```

---

## Progressive Web App (PWA)

When you open the server URL in your phone's browser, you get a full mobile-optimized app with four tabs:

### Dashboard

Lists all registered ricet projects with their status, description, and progress bar. Auto-refreshes every 30 seconds.

### Tasks

Select a project from the dropdown, type a task description, and submit it. The task is queued for execution by the agent system.

### Voice

Tap the microphone button to dictate a command using your phone's speech recognition (Web Speech API). The transcribed text can be sent as a task to any project.

### Settings

Displays connection information (server address, TLS fingerprint, TLS status) and stored token info. Includes a button to clear the local token.

### Installing as a Home Screen App

The PWA manifest enables "Add to Home Screen":

- **iOS**: Open in Safari, tap Share, then "Add to Home Screen".
- **Android**: Chrome shows an "Install" banner automatically, or use the menu.

The app works in standalone mode (no browser chrome) and includes a service worker for offline graceful degradation.

---

## Connection Methods

The `ricet mobile connect-info` command shows three ways to reach your server:

### 1. Direct HTTPS (Same Network)

If your phone and computer are on the same Wi-Fi:

```
https://192.168.1.100:8777
```

Your phone will show a certificate warning because the certificate is self-signed. Accept it after verifying the SHA-256 fingerprint matches.

### 2. SSH Tunnel (Remote Access)

For accessing a remote lab server:

```bash
# On your laptop or phone (Termux, etc.)
ssh -L 8777:localhost:8777 user@lab-server.example.com

# Then open
https://localhost:8777
```

### 3. WireGuard VPN (Peer-to-Peer)

If you have a WireGuard VPN between your phone and server:

```
https://<wireguard-ip>:8777
```

### 4. Cloudflare Tunnel or ngrok (Public Access)

For internet-facing access without opening ports:

```bash
# Cloudflare Tunnel (free)
cloudflared tunnel --url https://localhost:8777

# ngrok
ngrok http https://localhost:8777
```

!!! warning
    Always enable bearer token authentication when exposing the server to the internet.

---

## Token Management

### Generating Tokens

```bash
# Via CLI
ricet mobile pair

# Programmatically
from core.mobile import MobileAuth
auth = MobileAuth()
token = auth.generate_token(label="my-phone")
```

Tokens are 48-character URL-safe strings. The plaintext is displayed once; only the SHA-256 hash is persisted to `~/.ricet/mobile_tokens.json`.

### Using Tokens

Include in every API request via the `Authorization` header:

```
Authorization: Bearer YOUR_TOKEN_HERE
```

Or pass as a URL parameter when first opening the PWA (the app stores it in `localStorage`):

```
https://192.168.1.100:8777?token=YOUR_TOKEN_HERE
```

### Listing and Revoking

```bash
# List all tokens (shows hash prefix, label, creation date)
ricet mobile tokens

# Revoke by hash prefix
from core.mobile import MobileAuth
auth = MobileAuth()
auth.revoke("a1b2c3d4e5f6")
```

---

## TLS Certificate Management

The server generates self-signed RSA 2048-bit certificates on first start:

```
~/.ricet/certs/server.crt
~/.ricet/certs/server.key
```

Key file permissions are restricted to `0600`. Certificates are valid for 365 days.

### Regenerating Certificates

```bash
ricet mobile cert-regen
```

This generates new certificates and displays the new SHA-256 fingerprint. Existing phone connections will need to accept the new certificate.

### Viewing the Fingerprint

```bash
ricet mobile connect-info
```

Compare the displayed fingerprint with what your phone shows when accepting the certificate.

---

## Running Alongside Overnight Mode

The mobile server runs in a daemon thread, so it coexists with other ricet commands:

```bash
# Terminal 1: Start mobile server
ricet mobile serve

# Terminal 2: Run overnight
ricet overnight --iterations 20
```

If mobile access is enabled in `config/settings.yml`, `ricet start` launches the mobile server automatically. Check progress from your phone while overnight mode runs.

---

## Troubleshooting

### Cannot connect from phone

- Verify both devices are on the same network
- Check firewall: `sudo ufw allow 8777/tcp`
- Test locally first: `curl -k https://localhost:8777/status`

### Certificate warning on phone

This is expected with self-signed certificates. Verify the SHA-256 fingerprint matches `ricet mobile connect-info` output, then accept.

### "unauthorized" response

- Ensure the `Authorization: Bearer TOKEN` header is included
- Tokens are case-sensitive
- Check if your IP is rate-limited (15-minute lockout after 10 failures)

### Voice tab says "Speech not supported"

The Web Speech API requires a secure context (HTTPS) and is supported in Chrome and Safari. Firefox does not support it. Use Chrome on Android or Safari on iOS.

### PWA not installable

- Must be served over HTTPS (the self-signed cert counts)
- Must have a valid `/manifest.json` (served automatically)
- Try clearing browser cache and reloading
