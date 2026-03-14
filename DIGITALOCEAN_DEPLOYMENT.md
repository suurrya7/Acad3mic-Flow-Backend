# DigitalOcean Deployment Guide

This guide covers deploying the Acad3mic-Flow application (FastAPI backend + React Admin Panel) to DigitalOcean while keeping Supabase as your database.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    DigitalOcean                          │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │  Droplet (Ubuntu 22.04)                      │       │
│  │                                               │       │
│  │  ├─ Nginx (Reverse Proxy + SSL)              │       │
│  │  ├─ Backend (FastAPI on :8000)               │       │
│  │  └─ Admin Panel (Static files served by Nginx)│      │
│  └──────────────────────────────────────────────┘       │
│                                                          │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │   Supabase     │
                   │  (PostgreSQL)  │
                   └────────────────┘
```

## Prerequisites

- ✅ DigitalOcean account
- ✅ Domain name (optional but recommended)
- ✅ Supabase project (already configured)
- ✅ Git repository with your code

---

## Part 1: Create DigitalOcean Droplet

### Step 1: Create Droplet

1. **Log in to DigitalOcean** → Click "Create" → "Droplets"

2. **Choose Configuration:**
   - **Image:** Ubuntu 22.04 LTS
   - **Droplet Type:** Basic
   - **CPU Options:** Regular (SSD)
   - **Size:** 
     - **For Testing:** $6/month (1GB RAM, 1 CPU)
     - **For Production:** $12/month (2GB RAM, 1 CPU) - Recommended
     - **For High Traffic:** $24/month (4GB RAM, 2 CPUs)

3. **Choose Region:** Select closest to your target users

4. **Authentication:** 
   - ✅ **SSH Key** (recommended) - Add your public key
   - OR Password (less secure)

5. **Hostname:** `acad3mic-flow-api` (or your choice)

6. Click **Create Droplet**

### Step 2: Initial Server Setup

SSH into your droplet:
```bash
ssh root@your_droplet_ip
```

Update system packages:
```bash
apt update && apt upgrade -y
```

Install required software:
```bash
# Install Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# Install Node.js 20 (for building admin panel)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Install Nginx
apt install -y nginx

# Install Git
apt install -y git

# Install other utilities
apt install -y curl wget ufw certbot python3-certbot-nginx
```

---

## Part 2: Deploy Backend (FastAPI)

### Step 1: Create Application User

Create a dedicated user for running the application:
```bash
adduser acad3mic --disabled-password --gecos ""
usermod -aG sudo acad3mic
su - acad3mic
```

### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/yourusername/your-repo.git acad3mic-flow
cd acad3mic-flow
```

### Step 3: Setup Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create production `.env` file:
```bash
nano .env
```

Add the following (update with your actual values):
```env
# Environment
ENV=production

# Supabase Configuration (from your existing Supabase project)
SUPABASE_URL=https://xbvgyjbxjlqkchnrsrey.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret

# AI Configuration
GEMINI_API_KEY=your_gemini_api_key

# Payment Configuration
PAYU_MERCHANT_KEY=your_payu_merchant_key
PAYU_SALT=your_payu_salt

# CORS Origins (add your domain)
PROD_ORIGINS=https://yourdomain.com,https://api.yourdomain.com,https://admin.yourdomain.com
```

Save and exit (`Ctrl+X`, then `Y`, then `Enter`)

### Step 5: Test Backend Locally

```bash
# Activate venv if not already activated
source venv/bin/activate

# Test run
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, test health check
curl http://localhost:8000/health
```

If successful, stop the test server (`Ctrl+C`)

### Step 6: Setup Systemd Service

Create systemd service file:
```bash
sudo nano /etc/systemd/system/acad3mic-flow.service
```

Add the following:
```ini
[Unit]
Description=Acad3mic-Flow FastAPI Backend
After=network.target

[Service]
Type=simple
User=acad3mic
Group=acad3mic
WorkingDirectory=/home/acad3mic/acad3mic-flow
Environment="PATH=/home/acad3mic/acad3mic-flow/venv/bin"
EnvironmentFile=/home/acad3mic/acad3mic-flow/.env
ExecStart=/home/acad3mic/acad3mic-flow/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable acad3mic-flow
sudo systemctl start acad3mic-flow

# Check status
sudo systemctl status acad3mic-flow

# View logs
sudo journalctl -u acad3mic-flow -f
```

---

## Part 3: Deploy Admin Panel (React/Vite)

### Step 1: Build Admin Panel

```bash
cd ~/acad3mic-flow/admin-panel

# Install dependencies
npm install

# Create production .env file
nano .env.production
```

Add:
```env
VITE_API_URL=https://api.yourdomain.com
VITE_SUPABASE_URL=https://xbvgyjbxjlqkchnrsrey.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

Build the admin panel:
```bash
npm run build
```

This creates a `dist/` folder with static files.

### Step 2: Copy Build to Web Directory

```bash
sudo mkdir -p /var/www/admin.yourdomain.com
sudo cp -r dist/* /var/www/admin.yourdomain.com/
sudo chown -R www-data:www-data /var/www/admin.yourdomain.com
```

---

## Part 4: Configure Nginx

### Step 1: Create Nginx Configuration for Backend

```bash
sudo nano /etc/nginx/sites-available/api.yourdomain.com
```

Add:
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Increase timeouts for long-running AI requests
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

### Step 2: Create Nginx Configuration for Admin Panel

```bash
sudo nano /etc/nginx/sites-available/admin.yourdomain.com
```

Add:
```nginx
server {
    listen 80;
    server_name admin.yourdomain.com;

    root /var/www/admin.yourdomain.com;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Step 3: Enable Sites

```bash
sudo ln -s /etc/nginx/sites-available/api.yourdomain.com /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/admin.yourdomain.com /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Part 5: Setup SSL Certificates (HTTPS)

### Step 1: Configure Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

### Step 2: Obtain SSL Certificates

Make sure your domains point to your droplet's IP address first!

```bash
# For backend API
sudo certbot --nginx -d api.yourdomain.com

# For admin panel
sudo certbot --nginx -d admin.yourdomain.com
```

Follow the prompts:
- Enter your email
- Agree to terms
- Choose to redirect HTTP to HTTPS (option 2)

Certbot will automatically update your Nginx configuration.

### Step 3: Auto-Renewal

Certbot automatically sets up renewal. Test it:
```bash
sudo certbot renew --dry-run
```

---

## Part 6: Domain Configuration

### Option A: Using Your Own Domain

1. Go to your domain registrar (Namecheap, GoDaddy, etc.)
2. Add A records:
   - `api.yourdomain.com` → Your droplet IP
   - `admin.yourdomain.com` → Your droplet IP

### Option B: Using DigitalOcean DNS

1. Go to DigitalOcean → Networking → Domains
2. Add your domain
3. Add A records as above
4. Update nameservers at your registrar to DigitalOcean's NS

---

## Part 7: Verification & Testing

### Test Backend

```bash
# Health check
curl https://api.yourdomain.com/health

# Expected response:
# {"status":"healthy","database":"healthy","version":"1.0.0","environment":"production"}
```

### Test Admin Panel

1. Open browser: `https://admin.yourdomain.com`
2. You should see the login page
3. Log in with your admin credentials
4. Verify dashboard loads

### Check Logs

```bash
# Backend logs
sudo journalctl -u acad3mic-flow -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

---

## Part 8: Ongoing Maintenance

### Update Application

```bash
cd ~/acad3mic-flow
git pull origin main

# Backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart acad3mic-flow

# Admin Panel
cd admin-panel
npm install
npm run build
sudo cp -r dist/* /var/www/admin.yourdomain.com/
```

### Monitor Resources

```bash
# Check disk usage
df -h

# Check memory
free -h

# Check service status
sudo systemctl status acad3mic-flow

# Check processes
htop
```

### Backup .env File

```bash
# Backup to secure location
cp .env .env.backup.$(date +%Y%m%d)
```

---

## Troubleshooting

### Backend Not Starting

```bash
# Check logs
sudo journalctl -u acad3mic-flow -n 100 --no-pager

# Test run manually
cd ~/acad3mic-flow
source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Admin Panel Shows Blank Page

- Check browser console for errors
- Verify `.env.production` has correct API URL
- Rebuild admin panel: `npm run build`

### CORS Errors

- Update `PROD_ORIGINS` in backend `.env`
- Include all your domains (with https://)
- Restart backend: `sudo systemctl restart acad3mic-flow`

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

---

## Cost Estimation

### Monthly Costs:
- **DigitalOcean Droplet:** $12-24/month
- **Supabase:** Free tier (up to 500MB DB, 1GB storage)
- **Domain:** $10-15/year
- **SSL Certificate:** Free (Let's Encrypt)

**Total:** ~$12-24/month + domain cost

---

## Security Best Practices

✅ **Keep system updated:** `sudo apt update && sudo apt upgrade`
✅ **Use SSH keys** instead of passwords
✅ **Enable UFW firewall**
✅ **Regular backups** of .env and database
✅ **Monitor logs** for suspicious activity
✅ **Keep dependencies updated**
✅ **Use strong admin passwords**

---

## Next Steps

1. ✅ Set up monitoring (e.g., UptimeRobot for uptime monitoring)
2. ✅ Configure log rotation to prevent disk filling
3. ✅ Set up automated backups
4. ✅ Add error tracking (Sentry, Rollbar)
5. ✅ Consider adding a CDN (Cloudflare) for better performance

---

## Support

- **DigitalOcean Community:** https://www.digitalocean.com/community
- **Supabase Docs:** https://supabase.com/docs
- **FastAPI Deployment:** https://fastapi.tiangolo.com/deployment/

**Need help?** Check the logs first, then consult the troubleshooting section above.
