# Deploying Content Factory to Digital Ocean

## Step 1: Create a Droplet

1. Go to [Digital Ocean](https://cloud.digitalocean.com)
2. Create Droplet → **Ubuntu 22.04** → **Basic** → **$12/mo (2GB RAM)** recommended
   - Video processing needs decent RAM
3. Choose a datacenter region close to you
4. Add your SSH key
5. Create Droplet

## Step 2: Point Domain (Namecheap)

1. Go to Namecheap → Domain List → **contentfactoryy.com** → Manage
2. Go to **Advanced DNS**
3. Add these records:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_DROPLET_IP | Automatic |
| A | www | YOUR_DROPLET_IP | Automatic |

4. Wait 5-30 minutes for DNS to propagate

## Step 3: Deploy the App

SSH into your droplet:
```bash
ssh root@YOUR_DROPLET_IP
```

### Quick Deploy (copy-paste this):

```bash
# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ffmpeg

# Create app user
useradd -m -s /bin/bash contentfactory

# Create directory and clone repo
mkdir -p /var/www/contentfactory
cd /var/www/contentfactory

# Option A: Clone from GitHub (if you push it)
# git clone https://github.com/YOUR_USERNAME/video-generator.git .

# Option B: Upload via scp from your local machine (run locally):
# scp -r /path/to/video-generator/* root@YOUR_DROPLET_IP:/var/www/contentfactory/

# Set ownership
chown -R contentfactory:contentfactory /var/www/contentfactory

# Setup Python environment
sudo -u contentfactory python3 -m venv venv
sudo -u contentfactory ./venv/bin/pip install --upgrade pip
sudo -u contentfactory ./venv/bin/pip install -r deploy/requirements-prod.txt
sudo -u contentfactory ./venv/bin/pip install gunicorn

# Create directories
sudo -u contentfactory mkdir -p data outputs/videos outputs/thumbnails temp assets/music/{liminal,scary,horror,nostalgia,general}
```

### Create .env file:
```bash
cat > /var/www/contentfactory/.env << 'EOF'
ANTHROPIC_API_KEY=your_anthropic_key_here
HF_API_TOKEN=your_huggingface_token_here
DEFAULT_VOICE=en-US-AnaNeural
EOF
chown contentfactory:contentfactory /var/www/contentfactory/.env
chmod 600 /var/www/contentfactory/.env
```

### Setup systemd service:
```bash
cp /var/www/contentfactory/deploy/contentfactory.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable contentfactory
systemctl start contentfactory
```

### Setup Nginx:
```bash
cp /var/www/contentfactory/deploy/nginx.conf /etc/nginx/sites-available/contentfactory
ln -sf /etc/nginx/sites-available/contentfactory /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### Setup SSL (after DNS propagates):
```bash
certbot --nginx -d contentfactoryy.com -d www.contentfactoryy.com
```

## Step 4: Verify

Visit: http://contentfactoryy.com (or https:// after certbot)

## Useful Commands

```bash
# Check app status
systemctl status contentfactory

# View logs
journalctl -u contentfactory -f

# Restart app
systemctl restart contentfactory

# Check nginx
nginx -t
systemctl status nginx
```

## Updating the App

```bash
cd /var/www/contentfactory
git pull  # if using git
systemctl restart contentfactory
```

## YouTube OAuth Note

For YouTube publishing to work:
1. Copy `client_secrets.json` to `/var/www/contentfactory/`
2. Update Google Cloud Console OAuth redirect URI to: `https://contentfactoryy.com/youtube/callback`
3. First OAuth needs to be done via the web interface
