#!/bin/bash

# Quick Setup Script for Telegram Course Bot
# This script automates the initial setup process

set -e

echo "🤖 Telegram Course Bot - Quick Setup"
echo "===================================="
echo ""

# Check if Python 3.11+ is installed
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 or higher is required but not found."
    echo "   Please install Python 3.11+ first."
    exit 1
fi

echo "✅ Python 3.11+ found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3.11 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip -q

# Install requirements
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q
echo "✅ Dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your bot token and database credentials"
    echo "   nano .env"
else
    echo "✅ .env file already exists"
fi

# Check PostgreSQL connection
echo ""
echo "🔍 Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    echo "✅ PostgreSQL client found"
else
    echo "⚠️  PostgreSQL client not found. Install with:"
    echo "   sudo apt install postgresql-client"
fi

# Check Redis
echo ""
echo "🔍 Checking Redis..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis is running"
    else
        echo "⚠️  Redis is installed but not running"
    fi
else
    echo "⚠️  Redis not found (optional but recommended)"
fi

echo ""
echo "📋 Next Steps:"
echo "=============="
echo "1. Edit .env file with your configuration:"
echo "   nano .env"
echo ""
echo "2. Create PostgreSQL database:"
echo "   sudo -u postgres psql"
echo "   CREATE DATABASE course_bot;"
echo "   CREATE USER bot_user WITH PASSWORD 'your_password';"
echo "   GRANT ALL PRIVILEGES ON DATABASE course_bot TO bot_user;"
echo ""
echo "3. Run database migrations:"
echo "   source venv/bin/activate"
echo "   alembic upgrade head"
echo ""
echo "4. Start the bot:"
echo "   python bot.py"
echo ""
echo "✅ Setup complete!"
