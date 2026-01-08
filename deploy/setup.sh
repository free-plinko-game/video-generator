#!/bin/bash
# Digital Ocean Droplet Setup Script for Content Factory
# Run as root on a fresh Ubuntu 22.04 droplet

set -e

echo "=== Content Factory Deployment Setup ==="

# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ffmpeg

# Create app user
useradd -m -s /bin/bash contentfactory || true

# Create app directory
mkdir -p /var/www/contentfactory
chown contentfactory:contentfactory /var/www/contentfactory

# Clone or copy your app (adjust repo URL)
# git clone https://github.com/YOUR_USERNAME/video-generator.git /var/www/contentfactory

echo "=== Setting up Python environment ==="
cd /var/www/contentfactory

# Create virtual environment
sudo -u contentfactory python3 -m venv venv
sudo -u contentfactory ./venv/bin/pip install --upgrade pip

# Install dependencies
sudo -u contentfactory ./venv/bin/pip install -r requirements.txt
sudo -u contentfactory ./venv/bin/pip install gunicorn

# Create necessary directories
sudo -u contentfactory mkdir -p data outputs/videos outputs/thumbnails temp assets/music/{liminal,scary,horror,nostalgia,general}

echo "=== Setting up systemd service ==="
cp /var/www/contentfactory/deploy/contentfactory.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable contentfactory

echo "=== Setting up Nginx ==="
cp /var/www/contentfactory/deploy/nginx.conf /etc/nginx/sites-available/contentfactory
ln -sf /etc/nginx/sites-available/contentfactory /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy your .env file to /var/www/contentfactory/.env"
echo "2. Copy your client_secrets.json if using YouTube"
echo "3. Update /etc/nginx/sites-available/contentfactory with your domain"
echo "4. Run: systemctl start contentfactory"
echo "5. Run: certbot --nginx -d yourdomain.com"
echo ""
