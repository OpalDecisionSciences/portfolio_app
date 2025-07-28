#!/bin/bash

# AWS EC2 Deployment Script for Opal Decision Sciences
# Replace YOUR_EC2_IP and YOUR_KEY_FILE.pem with actual values

set -e

# Configuration
EC2_IP="13.223.94.223"
KEY_FILE="~/.ssh/opal-decision-sciences-prod-kp.pem"
EC2_USER="ubuntu"
APP_DIR="/home/ubuntu/portfolio_app"

echo "🚀 Deploying Opal Decision Sciences to AWS EC2..."

# 1. Copy application files to EC2
echo "📁 Copying application files..."
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.venv' --exclude='*.pyc' \
    -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    ./ $EC2_USER@$EC2_IP:$APP_DIR/

# 2. Run setup commands on EC2
echo "⚙️ Setting up application on EC2..."
ssh -i $KEY_FILE -o StrictHostKeyChecking=no $EC2_USER@$EC2_IP << 'EOF'
    # Update system
    sudo apt update && sudo apt upgrade -y
    
    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
    
    # Install Docker Compose
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    # Navigate to app directory
    cd /home/ubuntu/portfolio_app
    
    # Create necessary directories
    mkdir -p logs ssl ssl-challenges
    
    # Set permissions
    sudo chown -R ubuntu:ubuntu /home/ubuntu/portfolio_app
    
    # Start application
    docker-compose -f docker-compose.prod.yml up -d
    
    echo "✅ Application deployed successfully!"
    echo "🌐 Your app should be accessible at: http://13.223.94.223"
    echo "🔒 Set up SSL with: docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot"
EOF

echo "🎉 Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Replace YOUR_EC2_IP in .env.prod with actual IP"
echo "2. Update DNS to point to your EC2 IP"
echo "3. Run SSL setup: ssh into server and run SSL command above"
echo "4. Test at: http://YOUR_EC2_IP"