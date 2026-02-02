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
4. [Google / Gemini API Key (optional)](#4-google--gemini-api-key-optional)
5. [HuggingFace Token (optional)](#5-huggingface-token-optional)
6. [Weights & Biases API Key (optional)](#6-weights--biases-api-key-optional)
7. [Slack Webhook (optional)](#7-slack-incoming-webhook-optional)
8. [Medium API Token (optional)](#8-medium-api-token-optional)
9. [LinkedIn API Token (optional)](#9-linkedin-api-token-optional)
10. [Notion API Key (optional)](#10-notion-api-key-optional)
11. [AWS Credentials (optional)](#11-aws-credentials-optional)
12. [Email / SMTP (optional)](#12-email--smtp-optional)
13. [Storing Your Keys Safely](#13-storing-your-keys-safely)

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

## 4. Google / Gemini API Key (optional)

Used for Google Gemini models, Google Search, and various Google Cloud MCPs.

### Steps

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Log in with your Google account.
3. Click **Create API key**.
4. Select or create a Google Cloud project.
5. Copy the key.

```bash
$ export GOOGLE_API_KEY="AIza..."
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "API key not valid" | Ensure the key is for the correct project. Regenerate if needed. |
| Quota errors | Check quotas at console.cloud.google.com. |

---

## 5. HuggingFace Token (optional)

Used by the ML pipeline (tier 3 MCP) for downloading models, datasets, and
pushing results to HuggingFace Hub.

### Steps

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
2. Log in or sign up.
3. Click **New token**.
4. Name it `ricet`, select **Read** access (or Write if you plan to push models).
5. Copy the token.

```bash
$ export HUGGINGFACE_TOKEN="hf_..."
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Unauthorized" when downloading | Verify token has Read access. Some models require accepting a license on the model page first. |
| Push fails | Regenerate with Write access. |

---

## 6. Weights & Biases API Key (optional)

Used for experiment tracking, run logging, and hyperparameter sweep dashboards.

### Steps

1. Go to [wandb.ai/authorize](https://wandb.ai/authorize).
2. Log in or sign up.
3. Copy the API key shown on the page.

```bash
$ export WANDB_API_KEY="..."
```

Alternatively, run `wandb login` interactively.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid API key" | Go to wandb.ai/authorize and copy the key again. |
| Wrong project/entity | Set `WANDB_PROJECT` and `WANDB_ENTITY` environment variables. |

---

## 7. Slack Incoming Webhook (optional)

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

## 8. Medium API Token (optional)

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

## 9. LinkedIn API Token (optional)

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

## 10. Notion API Key (optional)

Used by the Notion MCP (tier 8) for project boards, documentation sync, and
knowledge base integration.

### Steps

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations).
2. Click **New integration**.
3. Name it `ricet`, select your workspace.
4. Copy the **Internal Integration Secret**.
5. In Notion, share the pages you want accessible with your integration.

```bash
$ export NOTION_API_KEY="ntn_..."
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Object not found" | Share the target page with your integration in Notion. |
| "Unauthorized" | Check the secret is correct and the integration is active. |

---

## 11. AWS Credentials (optional)

Used by the AWS MCP (tier 7) for cloud compute, S3 storage, and SageMaker
training jobs.

### Steps

1. Go to [console.aws.amazon.com/iam](https://console.aws.amazon.com/iam/).
2. Navigate to **Users** → your user → **Security credentials**.
3. Click **Create access key**.
4. Select "Command Line Interface (CLI)".
5. Copy both the Access Key ID and Secret Access Key.

```bash
$ export AWS_ACCESS_KEY_ID="AKIA..."
$ export AWS_SECRET_ACCESS_KEY="..."
```

Alternatively, run `aws configure` if you have the AWS CLI installed.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "InvalidClientTokenId" | Verify the access key is active in IAM console. |
| Permission denied | Attach appropriate IAM policies to your user. |

---

## 12. Email / SMTP (optional)

Used by the notification system for email alerts on task completion, errors,
and overnight run summaries.

### Steps (Gmail example)

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. Select **Mail** and your device, then click **Generate**.
3. Copy the 16-character app password.

```bash
$ export SMTP_HOST="smtp.gmail.com"
$ export SMTP_PORT="587"
$ export SMTP_USER="you@gmail.com"
$ export SMTP_PASSWORD="xxxx xxxx xxxx xxxx"
```

For other providers, check their SMTP settings documentation.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Authentication failed" | Use an app password, not your regular password. Enable 2FA first. |
| "Connection refused" | Check host and port. Common: smtp.gmail.com:587, smtp.outlook.com:587. |

---

## 13. Storing Your Keys Safely

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
| GitHub Token | For API features | github.com/settings/tokens | `GITHUB_PERSONAL_ACCESS_TOKEN` |
| OpenAI API Key | No | platform.openai.com | `OPENAI_API_KEY` |
| Google / Gemini API Key | No | aistudio.google.com/apikey | `GOOGLE_API_KEY` |
| HuggingFace Token | No | huggingface.co/settings/tokens | `HUGGINGFACE_TOKEN` |
| Weights & Biases Key | No | wandb.ai/authorize | `WANDB_API_KEY` |
| Slack Webhook | No | api.slack.com/apps | `SLACK_WEBHOOK_URL` |
| Slack Bot Token | No | api.slack.com/apps | `SLACK_BOT_TOKEN` |
| Medium Token | No | medium.com settings | `MEDIUM_TOKEN` |
| LinkedIn Credentials | No | linkedin.com/developers | `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN` |
| Notion API Key | No | notion.so/my-integrations | `NOTION_API_KEY` |
| AWS Credentials | No | console.aws.amazon.com/iam | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| SMTP (Email) | No | Your email provider | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |

---

**Next:** [Tutorial 2: Docker Setup](docker-setup.md)
