# Tutorial 5: Website Setup

This tutorial covers setting up and deploying a personal academic website using
ricet. You will create a site with your bio, publications list,
research interests, and blog -- then deploy it so it is accessible on the
internet.

**Time:** ~45 minutes

**Prerequisites:**
- A project created with `ricet init` ([Tutorial 3](first-project.md))
- A GitHub account (for GitHub Pages deployment)
- Optional: a custom domain name

---

## Table of Contents

1. [Choose a Framework](#1-choose-a-framework)
2. [Generate the Site with Claude](#2-generate-the-site-with-claude)
3. [Customize Your Content](#3-customize-your-content)
4. [Preview Locally](#4-preview-locally)
5. [Deploy to GitHub Pages](#5-deploy-to-github-pages)
6. [Set Up a Custom Domain](#6-set-up-a-custom-domain)
7. [Self-Hosted Alternative: Hetzner VPS + Namecheap Domain](#7-self-hosted-alternative-hetzner-vps--namecheap-domain)
8. [Automate Updates with ricet](#8-automate-updates-with-ricet)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Choose a Framework

ricet can generate a website using any static site framework.
For academic sites, we recommend these options:

| Framework | Best For | Complexity |
|-----------|----------|------------|
| Plain HTML/CSS | Maximum simplicity, full control | Low |
| Hugo + Academic theme | Feature-rich academic site | Medium |
| Jekyll (GitHub Pages native) | Easy GitHub integration | Medium |

This tutorial uses **plain HTML/CSS** for simplicity, but the same Claude-driven
workflow applies to any framework.

---

## 2. Generate the Site with Claude

Start an interactive session in your project:

```bash
$ cd ~/projects/my-first-project
$ ricet start --session-name "website"
```

Ask Claude to scaffold the site:

```
You: Create a personal academic website in a new directory called "website/".
     Include the following pages:
     - index.html: landing page with my name, title, photo placeholder, and
       a brief bio
     - publications.html: list of publications with links
     - research.html: description of research interests
     - blog.html: a blog index page
     - style.css: clean, professional styling
     - Make it responsive for mobile devices.
     - Use a minimal, clean design suitable for academia.

     My info:
     Name: Dr. Jane Smith
     Title: Assistant Professor of Computer Science
     University: Example University
     Research: Machine learning for scientific discovery
     Email: jane.smith@example.edu
```

> **Screenshot:** Terminal showing Claude generating the website files, with a
> tree view of the created directory structure.

Claude will create something like:

```
website/
├── index.html
├── publications.html
├── research.html
├── blog.html
├── style.css
├── js/
│   └── main.js
└── images/
    └── .gitkeep          # placeholder for your photo
```

---

## 3. Customize Your Content

### Add your photo

Place your headshot in the `website/images/` directory:

```bash
$ cp ~/photos/headshot.jpg website/images/profile.jpg
```

Update the image reference in `index.html`:

```html
<img src="images/profile.jpg" alt="Dr. Jane Smith" class="profile-photo">
```

### Add publications

Edit `publications.html` to add your papers. A clean format:

```html
<div class="publication">
  <h3>Contrastive Learning for Single-Cell Classification</h3>
  <p class="authors">J. Smith, A. Johnson, B. Williams</p>
  <p class="venue">Nature Methods, 2026</p>
  <p class="links">
    <a href="https://doi.org/10.xxxx">Paper</a> |
    <a href="https://github.com/jsmith/scRNA-contrastive">Code</a> |
    <a href="files/smith2026.bib">BibTeX</a>
  </p>
</div>
```

### Generate publication list from BibTeX

You can ask Claude to convert your existing `paper/references.bib` into HTML:

```
You: Read paper/references.bib and generate an HTML publication list for
     website/publications.html. Format each entry with title, authors, venue,
     year, and DOI link.
```

### Write blog posts

For each blog post, create a new HTML file:

```
You: Write a blog post about our latest paper on contrastive learning for
     single-cell RNA-seq. Target a general scientific audience. Save it as
     website/blog/2026-02-01-contrastive-learning.html.
```

### Social media integration

The social media module can also draft posts about your research for Medium and
LinkedIn. After writing a blog post:

```
You: Draft a Medium post and a LinkedIn update based on the blog post we just
     wrote. Save the drafts so I can review before publishing.
```

---

## 4. Preview Locally

### Using Python's built-in server

```bash
$ cd website
$ python3 -m http.server 8000
Serving HTTP on 0.0.0.0 port 8000 ...
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

> **Screenshot:** Browser showing the academic website preview with a clean
> layout, navigation bar, profile photo placeholder, and bio text.

### Using the Docker container

If you are using Docker, the container exposes port 4000 for previews:

```bash
# Inside the container
$ cd /workspace/website
$ python3 -m http.server 4000
```

Access it at [http://localhost:4000](http://localhost:4000) from your host
browser.

### Check on mobile

While the local server is running, find your machine's IP:

```bash
$ hostname -I | awk '{print $1}'
192.168.1.100
```

Open `http://192.168.1.100:8000` on your phone to check the responsive layout.

---

## 5. Deploy to GitHub Pages

### Step 1: Create a GitHub repository

```bash
$ cd website
$ git init
$ git add -A
$ git commit -m "Initial website"
```

Create a new repository on GitHub named `<your-username>.github.io` for a user
site, or any name for a project site.

```bash
$ git remote add origin git@github.com:YOUR_USERNAME/YOUR_USERNAME.github.io.git
$ git branch -M main
$ git push -u origin main
```

### Step 2: Enable GitHub Pages

1. Go to your repository on GitHub.
2. Click **Settings > Pages**.
3. Under **Source**, select **Deploy from a branch**.
4. Select `main` branch and `/ (root)` directory.
5. Click **Save**.

> **Screenshot:** GitHub repository Settings page showing the Pages configuration
> with branch set to main and directory set to root.

### Step 3: Wait for deployment

GitHub Actions will build and deploy your site. This takes 1-2 minutes.

```bash
$ gh run list --limit 3
STATUS  TITLE                    BRANCH  EVENT  ID
*       pages build and deploy   main    push   12345678
```

### Step 4: Visit your site

Your site is live at:
- User site: `https://YOUR_USERNAME.github.io`
- Project site: `https://YOUR_USERNAME.github.io/REPO_NAME`

---

## 6. Set Up a Custom Domain

### Step 1: Buy a domain

Use any domain registrar (Namecheap, Google Domains, Cloudflare, etc.).

### Step 2: Configure DNS

Add these DNS records at your registrar:

| Type | Name | Value |
|------|------|-------|
| A | @ | `185.199.108.153` |
| A | @ | `185.199.109.153` |
| A | @ | `185.199.110.153` |
| A | @ | `185.199.111.153` |
| CNAME | www | `YOUR_USERNAME.github.io` |

### Step 3: Add the domain in GitHub

1. Go to **Settings > Pages**.
2. Under **Custom domain**, enter your domain (e.g., `janesmith.com`).
3. Click **Save**.
4. Check **Enforce HTTPS** once the certificate is issued (can take up to 24
   hours).

### Step 4: Add a CNAME file

Create a `CNAME` file in the root of your repository:

```bash
$ echo "janesmith.com" > CNAME
$ git add CNAME
$ git commit -m "Add custom domain"
$ git push
```

---

## 7. Self-Hosted Alternative: Hetzner VPS + Namecheap Domain

GitHub Pages works for static sites. If you need a server (running APIs, databases,
long computations, or hosting overnight agents), use a VPS instead.

### Step 1: Get a Hetzner VPS

1. Create an account at [hetzner.com/cloud](https://www.hetzner.com/cloud/)
2. Create a new project, then click **Add Server**
3. Recommended config for research:
   - **Location**: Falkenstein or Helsinki (cheapest)
   - **Image**: Ubuntu 24.04
   - **Type**: CPX21 (3 vCPU, 4 GB RAM, ~5 EUR/mo) for lightweight tasks,
     or CCX23 (4 vCPU, 16 GB RAM, ~15 EUR/mo) for heavier workloads
   - **SSH key**: paste your public key (`cat ~/.ssh/id_ed25519.pub`)
4. Note the server IP address after creation

### Step 2: Initial server setup

```bash
# SSH into your new server
$ ssh root@YOUR_SERVER_IP

# Create a non-root user
$ adduser researcher
$ usermod -aG sudo researcher

# Set up firewall
$ ufw allow OpenSSH
$ ufw allow 80
$ ufw allow 443
$ ufw enable

# Install essentials
$ apt update && apt install -y git curl nginx certbot python3-certbot-nginx

# Switch to your user
$ su - researcher
```

### Step 3: Buy a domain on Namecheap

1. Go to [namecheap.com](https://www.namecheap.com/) and search for your domain
2. After purchase, go to **Domain List > Manage > Advanced DNS**
3. Add these records:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_SERVER_IP | Automatic |
| A | www | YOUR_SERVER_IP | Automatic |

### Step 4: Set up HTTPS with nginx

```bash
# Create nginx config
$ sudo tee /etc/nginx/sites-available/mysite <<'EOF'
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    root /home/researcher/website;
    index index.html;
}
EOF

$ sudo ln -s /etc/nginx/sites-available/mysite /etc/nginx/sites-enabled/
$ sudo nginx -t && sudo systemctl reload nginx

# Get free SSL certificate (wait for DNS propagation first)
$ sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### Step 5: Deploy your site

```bash
# On your local machine
$ rsync -avz website/ researcher@YOUR_SERVER_IP:~/website/

# Or set up a git hook for auto-deploy
$ ssh researcher@YOUR_SERVER_IP 'cd ~/website && git init'
$ git remote add deploy researcher@YOUR_SERVER_IP:~/website
$ git push deploy main
```

### Cost summary

| Service | Cost |
|---------|------|
| Hetzner CPX21 (3 vCPU, 4 GB) | ~5 EUR/mo |
| Namecheap .com domain | ~9 EUR/yr |
| SSL certificate (Let's Encrypt) | Free |
| **Total** | **~6 EUR/mo** |

### Multiple projects on one machine

A single Hetzner box can host many projects using a reverse proxy. Install
Caddy (auto-HTTPS, zero config) and point each project to its own subdomain:

```bash
# Install Caddy
$ sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
$ curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
$ curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
$ sudo apt update && sudo apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```
project1.yourdomain.com {
    reverse_proxy localhost:3001
}

project2.yourdomain.com {
    reverse_proxy localhost:3002
}

demo.yourdomain.com {
    reverse_proxy localhost:3003
}
```

Each project runs in its own Docker Compose stack on a different port. Caddy
handles HTTPS certificates automatically via Let's Encrypt.

**DNS setup**: add an A record for each subdomain pointing to the same server IP.

**Best practices for multi-project hosting:**
- Use `docker compose` per project with `mem_limit` and `cpus` to prevent one
  runaway project from killing everything else
- Keep databases on internal Docker networks only (never exposed to the internet)
- Use `fail2ban` + SSH keys only (no password auth)
- For heavy datasets, use Hetzner Storage Boxes (BX series) or S3-compatible
  storage (Hetzner, Backblaze B2, Cloudflare R2) instead of filling the boot disk
- Automate deploys: a simple `git pull && docker compose up -d` script via SSH,
  or a GitHub Actions self-hosted runner
- Back up Docker volumes and configs via `cron` + `rsync` to a Storage Box
- For GPU compute (ML training), burst to cloud (Lambda Labs, Vast.ai) and only
  deploy inference/demos on the Hetzner box

---

## 8. Automate Updates with ricet

### Auto-generate publication pages

When you add a new paper to `references.bib`, you can automatically regenerate
the publications page:

```
You: Read paper/references.bib and regenerate website/publications.html with
     all current publications in reverse chronological order.
```

### Overnight blog generation

Add a task to your `state/TODO.md`:

```markdown
- [ ] Write a blog post summarizing this week's research progress and update the website
```

During overnight mode, Claude will:
1. Read the progress log
2. Draft a blog post
3. Add it to the website
4. Commit the changes

### Cross-repository coordination

If your website is in a separate repository from your research project, the
cross-repo module (`core/cross_repo.py`) can synchronize changes:

```
You: Sync the latest publication list from this project to my website
     repository at ~/projects/janesmith.github.io.
```

---

## 9. Troubleshooting

### GitHub Pages shows 404

- Verify the repository name matches `<username>.github.io` for a user site
- Check that `index.html` is in the root directory (not in a subdirectory)
- Wait 2-3 minutes after pushing; deployment is not instant
- Check **Actions** tab for build errors

### CSS not loading

- Verify the `<link>` tag path is correct: `<link rel="stylesheet" href="style.css">`
- If using a project site (not user site), paths may need the repository name
  prefix: `href="/repo-name/style.css"`

### Custom domain not working

- DNS propagation takes up to 48 hours (usually 1-2 hours)
- Verify DNS records: `dig YOUR_DOMAIN +short`
- The CNAME file must contain only the domain name, no protocol or trailing slash

### Site looks broken on mobile

- Ensure the viewport meta tag is in every HTML file:
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  ```
- Use CSS media queries for responsive breakpoints
- Test with browser developer tools (F12 > toggle device toolbar)

### Images too large / slow loading

- Compress images before adding them: `convert photo.jpg -resize 400x400 -quality 85 photo_web.jpg`
- Use WebP format for smaller file sizes
- Add `loading="lazy"` to image tags: `<img src="photo.jpg" loading="lazy">`

---

**Next:** [Tutorial 6: Overnight Mode](overnight-mode.md)
