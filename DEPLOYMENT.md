# Deployment Guide - Run Saiborg 24/7

## Option 1: Render.com (Easiest - Recommended)

### Steps:
1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Deploy on Render:**
   - Go to https://render.com and sign up
   - Click "New +" → "Background Worker"
   - Connect your GitHub repo
   - Configure:
     - **Name:** saiborg
     - **Environment:** Python 3
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python3 app.py`
   
3. **Add Environment Variables in Render Dashboard:**
   - `SLACK_BOT_TOKEN` = (your token)
   - `SLACK_APP_TOKEN` = (your token)
   - `GOOGLE_API_KEY` = (your key)
   - `MONDAY_API_KEY` = (your key, optional)
   - `MONDAY_CUSTOMER_BOARD_ID` = 5085798849 (or your board ID)
   - `CHROMA_DB_PATH` = chroma_db

4. **Deploy!** Render will automatically deploy and keep it running.

**Cost:** Free tier available (with some limitations), then ~$7/month

---

## Option 2: Railway.app

### Steps:
1. **Push to GitHub** (same as above)

2. **Deploy on Railway:**
   - Go to https://railway.app
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repo
   - Railway auto-detects Python
   - Add environment variables in the dashboard
   - Deploy!

**Cost:** ~$5/month, free trial available

---

## Option 3: DigitalOcean Droplet (More Control)

### Steps:
1. **Create Droplet:**
   - Go to DigitalOcean, create Ubuntu 22.04 droplet ($6/month)
   - SSH into it: `ssh root@your-droplet-ip`

2. **On the server, install dependencies:**
   ```bash
   apt update
   apt install -y python3 python3-pip git
   ```

3. **Clone your repo:**
   ```bash
   git clone <your-repo-url>
   cd saiborg
   pip3 install -r requirements.txt
   ```

4. **Create systemd service** (see `saiborg.service` file)

5. **Start the service:**
   ```bash
   sudo systemctl enable saiborg
   sudo systemctl start saiborg
   sudo systemctl status saiborg
   ```

**Cost:** $6/month for basic droplet

---

## Option 4: Fly.io

### Steps:
1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Run: `fly launch`
3. Add secrets: `fly secrets set SLACK_BOT_TOKEN=xxx SLACK_APP_TOKEN=xxx ...`
4. Deploy: `fly deploy`

**Cost:** Free tier available

---

## Important Notes:

### Chroma DB Persistence
- **Render/Railway:** Chroma DB will persist in the filesystem, but may be lost on redeploy
- **Solution:** Use external storage (S3) or rebuild index after deploy
- **Alternative:** Use a managed vector DB (Pinecone, Weaviate) for production

### Environment Variables
Never commit `.env` file! Always set variables in the platform's dashboard.

### Monitoring
- Check logs regularly in the platform dashboard
- Set up alerts if the service goes down
- Monitor API usage (Google, Monday.com)

### Updates
After pushing to GitHub, most platforms auto-deploy. Or manually trigger:
- Render: "Manual Deploy" button
- Railway: Auto-deploys on push

---

## Quick Start (Render - Recommended)

1. Push code to GitHub
2. Sign up at render.com
3. Create Background Worker
4. Connect repo
5. Add env vars
6. Deploy!

Done! Your bot runs 24/7 🚀

