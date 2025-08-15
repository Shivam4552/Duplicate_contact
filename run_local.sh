#!/bin/bash

# Local Environment Setup Script for Duplicate Contact Management System

echo "🚀 Setting up local environment..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created!"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed!"
else
    echo "⚠️  requirements.txt not found. Installing basic dependencies..."
    pip install requests python-dateutil python-dotenv
fi

# Setup .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📋 Creating .env file from template..."
        cp .env.example .env
        echo "✅ .env file created! Please edit it with your HubSpot token."
    else
        echo "📋 Creating basic .env file..."
        cat > .env << EOL
# HubSpot API Configuration
HUBSPOT_TOKEN=your-hubspot-private-app-token-here
EOL
        echo "✅ .env file created! Please edit it with your HubSpot token."
    fi
else
    echo "⚠️  .env file already exists."
fi

# Make scripts executable
chmod +x *.py
chmod +x rest_code/*.py

echo ""
echo "🎉 Local environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file and add your HubSpot Private App Token"
echo "2. Run any script:"
echo "   python contactmerge.py"
echo "   python rest_code/sameday.py"
echo ""
echo "💡 To get HubSpot token:"
echo "   1. Go to HubSpot Settings → Integrations → Private Apps"
echo "   2. Create new app with contacts read/write permissions"
echo "   3. Copy the generated token to .env file"
echo ""
echo "🔧 To activate this environment later, run:"
echo "   source venv/bin/activate"