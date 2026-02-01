# Tutorial 1: Getting API Keys

This tutorial walks you through authenticating with Claude and obtaining every
credential that ricet can use. Browser login via `claude auth login`
is the recommended method. API keys are available as a fallback for CI/headless
environments. Everything else is optional and can be added later.

**Time:** ~10 minutes

---

## Table of Contents

1. [Claude Authentication (required)](#1-claude-authentication-required)
2. [GitHub SSH Key (required for git push)](#2-github-ssh-key-required-for-git-push)
3. [OpenAI API Key (optional)](#3-openai-api-key-optional)
4. [Slack Webhook (optional)](#4-slack-incoming-webhook-optional)
5. [Medium API Token (optional)](#5-medium-api-token-optional)
6. [LinkedIn API Token (optional)](#6-linkedin-api-token-optional)
7. [Storing Your Keys Safely](#7-storing-your-keys-safely)

---

## 1. Claude Authentication (required)

Claude Code is the engine behind every agent in ricet. The
recommended way to authenticate is browser login -- no API key needed.

### Recommended: Browser Login

Run the following command and follow the prompts in your browser:

```bash
$ claude auth login
```

This stores credentials in `~/.claude/` and keeps them refreshed automatically.
No API key management required.

### Verify

```bash
$ claude --version
```

If the command succeeds without authentication errors, you are ready to go.

### Alternative: API Key (for CI/headless environments)

If you are running in a CI pipeline, headless server, or environment where
browser login is not possible, use an API key instead.

1. Go to [console.anthropic.com](https://console.anthropic.com/).
2. Sign up or log in.
3. Navigate to **Settings > API Keys** in the left sidebar.
4. Click **Create Key**.
5. Give it a name like `ricet`.
6. Copy the key immediately -- it will not be shown again.

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
$ export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

Reload your shell:

```bash
$ source ~/.bashrc   # or ~/.zshrc
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `claude auth login` fails | Ensure you have a working browser. On headless systems, use an API key instead. |
| "Invalid API key" errors | Make sure there are no extra spaces or newlines. Copy the key again from the console. |
| Key stops working | Check your billing at console.anthropic.com. Free-tier credits may have expired. |
| Accidentally committed a key | Revoke it immediately in the console, generate a new one, and add `*.env` to `.gitignore`. |

---

## 2. GitHub SSH Key (required for git push)

ricet commits to git frequently. An SSH key lets it push to GitHub
without entering your password every time.

### Steps

1. Check for an existing key:

```bash
$ ls ~/.ssh/id_ed25519.pub
```

If the file exists, skip to step 4.

2. Generate a new key:

```bash
$ ssh-keygen -t ed25519 -C "your_email@example.com"
```

Press **Enter** three times to accept the defaults (or set a passphrase if you
prefer).

3. Start the SSH agent and add the key:

```bash
$ eval "$(ssh-agent -s)"
$ ssh-add ~/.ssh/id_ed25519
```

4. Copy the public key:

```bash
$ cat ~/.ssh/id_ed25519.pub
```

5. Go to [github.com/settings/keys](https://github.com/settings/keys).
6. Click **New SSH key**.
7. Paste the key, give it a title like `research-machine`, and click **Add SSH key**.

> **Screenshot:** GitHub SSH key settings page with the "New SSH key" form open,
> showing the Title field and the Key textarea.

### Verify

```bash
$ ssh -T git@github.com
Hi <your-username>! You've successfully authenticated, but GitHub does not provide shell access.
```

### Optional: GitHub Token for API access

Some features (issues, pull requests, Actions monitoring) use the GitHub REST
API, which requires a Personal Access Token.

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens?type=beta).
2. Click **Generate new token** (fine-grained).
3. Give it `repo` and `workflow` permissions.
4. Copy the token and set it:

```bash
$ export GITHUB_TOKEN="github_pat_..."
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `Permission denied (publickey)` | Run `ssh-add -l` to check if the agent has your key. If empty, run `ssh-add ~/.ssh/id_ed25519`. |
| Multiple GitHub accounts | Use `~/.ssh/config` to map hosts to keys. Search "SSH config multiple GitHub accounts". |
| Token permission errors | Regenerate the token with the correct scopes (`repo`, `workflow`). |

---

## 3. OpenAI API Key (optional)

An OpenAI key is only needed if you want to use GPT models as a fallback or for
embedding generation via certain MCP servers.

### Steps

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
2. Log in or sign up.
3. Click **Create new secret key**.
4. Copy the key.

```bash
$ export OPENAI_API_KEY="sk-..."
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Insufficient quota" | Add a payment method at platform.openai.com/account/billing. |
| Key not recognized | Double-check there is no trailing whitespace. |

---

## 4. Slack Incoming Webhook (optional)

A Slack webhook lets ricet send you notifications (task complete,
errors, overnight run summary) to a Slack channel.

### Steps

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App > From scratch**.
2. Name it `Research Notifications` and pick your workspace.
3. In the left sidebar, click **Incoming Webhooks** and toggle it **On**.
4. Click **Add New Webhook to Workspace**.
5. Select the channel where you want notifications.
6. Copy the webhook URL.

> **Screenshot:** Slack app settings page showing the Incoming Webhooks section
> with the toggle turned on and a webhook URL displayed.

```bash
$ export NOTIFICATION_WEBHOOK="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX"
```

### Verify

```bash
$ curl -s -X POST "$NOTIFICATION_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d '{"text": "ricet test notification"}'
ok
```

Check your Slack channel -- you should see the test message.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `invalid_token` error | The webhook URL may be revoked. Create a new one. |
| Messages not appearing | Verify you selected the correct channel in step 5. |

---

## 5. Medium API Token (optional)

Used by the social media module (`core/social_media.py`) to publish blog posts
about your research directly to Medium.

### Steps

1. Go to [medium.com/me/settings/security](https://medium.com/me/settings/security).
2. Scroll to **Integration tokens**.
3. Enter a description (`ricet`) and click **Get token**.
4. Copy the token.

```bash
$ export MEDIUM_TOKEN="..."
```

> **Screenshot:** Medium settings page with the Integration tokens section showing
> a text field for the token description and a "Get token" button.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| No "Integration tokens" section | You need a Medium account first. Sign up at medium.com. |
| 401 errors when posting | Regenerate the token; old ones expire. |

---

## 6. LinkedIn API Token (optional)

Used by the social media module to share research updates on LinkedIn.
LinkedIn's API requires an OAuth2 application.

### Steps

1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and click **Create App**.
2. Fill in app name, company page, and logo.
3. Under **Products**, request access to **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
4. Go to the **Auth** tab.
5. Note your **Client ID** and **Client Secret**.
6. Generate an access token using the OAuth2 flow (LinkedIn provides a token generator in the developer portal for testing).

```bash
$ export LINKEDIN_CLIENT_ID="..."
$ export LINKEDIN_CLIENT_SECRET="..."
$ export LINKEDIN_ACCESS_TOKEN="..."
```

> **Screenshot:** LinkedIn developer app dashboard showing the Auth tab with
> Client ID and Client Secret fields.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Application not approved" | Some API products require manual review. Wait 24-48 hours. |
| Token expired | LinkedIn tokens expire after 60 days. Re-run the OAuth flow or use a refresh token. |
| 403 on posting | Ensure your app has the `w_member_social` scope. |

---

## 7. Storing Your Keys Safely

Never commit API keys to git. ricet uses two mechanisms for safe
key storage.

### Option A: Environment variables in your shell profile

Add exports to `~/.bashrc` or `~/.zshrc`:

```bash
# ~/.bashrc (or ~/.zshrc)
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="github_pat_..."
export NOTIFICATION_WEBHOOK="https://hooks.slack.com/..."
# Add other keys as needed
```

### Option B: `.env` file in your project

Create a `.env` file in your project root:

```bash
$ cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=github_pat_...
NOTIFICATION_WEBHOOK=https://hooks.slack.com/...
EOF
```

Make sure `.env` is in your `.gitignore`:

```bash
$ echo ".env" >> .gitignore
```

### Option C: Docker secrets (for containerized usage)

When using Docker, mount a secrets directory read-only:

```bash
$ mkdir -p ~/research-secrets
$ echo "sk-ant-..." > ~/research-secrets/anthropic_key
$ chmod 600 ~/research-secrets/*
```

Then set `SECRETS_PATH=~/research-secrets` in your `docker-compose.yml`
environment.

### Verify none of your keys are committed

```bash
$ git log --all -p | grep -i "sk-ant\|github_pat\|hooks.slack.com" | head -5
```

If this produces output, you have leaked keys in your history. Revoke and
rotate them immediately.

---

## Summary

| Key | Required | Where to Get It | Environment Variable |
|-----|----------|----------------|---------------------|
| Claude Auth (browser login) | Yes | `claude auth login` | `~/.claude/` |
| Anthropic API Key (fallback) | CI/headless only | console.anthropic.com | `ANTHROPIC_API_KEY` |
| GitHub SSH Key | For git push | ssh-keygen locally | N/A (file-based) |
| GitHub Token | For API features | github.com/settings/tokens | `GITHUB_TOKEN` |
| OpenAI API Key | No | platform.openai.com | `OPENAI_API_KEY` |
| Slack Webhook | No | api.slack.com/apps | `NOTIFICATION_WEBHOOK` |
| Medium Token | No | medium.com settings | `MEDIUM_TOKEN` |
| LinkedIn Token | No | linkedin.com/developers | `LINKEDIN_ACCESS_TOKEN` |

---

**Next:** [Tutorial 2: Docker Setup](docker-setup.md)
