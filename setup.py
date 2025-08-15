#!/usr/bin/env python3
"""
Setup script for local environment configuration
"""
import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.7+"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ is required. Current version:", sys.version)
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def install_dependencies():
    """Install required Python packages"""
    try:
        print("📦 Installing required packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def setup_env_file():
    """Setup .env file from template"""
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if env_path.exists():
        print("⚠️  .env file already exists")
        response = input("Do you want to overwrite it? (y/n): ").lower()
        if response != 'y':
            print("Skipping .env file setup")
            return True
    
    if example_path.exists():
        try:
            # Copy example to .env
            with open(example_path, 'r') as src, open(env_path, 'w') as dst:
                dst.write(src.read())
            print("✅ Created .env file from template")
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    else:
        # Create basic .env file
        with open(env_path, 'w') as f:
            f.write("# HubSpot API Configuration\n")
            f.write("HUBSPOT_TOKEN=your-hubspot-private-app-token-here\n")
        print("✅ Created basic .env file")
    
    return True

def setup_hubspot_token():
    """Interactive setup for HubSpot token"""
    env_path = Path(".env")
    
    print("\n🔑 HubSpot Token Setup")
    print("=" * 40)
    print("To get your HubSpot Private App Token:")
    print("1. Go to HubSpot Settings → Integrations → Private Apps")
    print("2. Create a new private app or select existing one")
    print("3. Grant scopes: crm.objects.contacts.read and crm.objects.contacts.write")
    print("4. Copy the generated token")
    print()
    
    token = input("Enter your HubSpot Private App Token (or press Enter to skip): ").strip()
    
    if token and token != "your-hubspot-private-app-token-here":
        try:
            # Read current .env file
            with open(env_path, 'r') as f:
                content = f.read()
            
            # Replace the token
            updated_content = content.replace(
                "HUBSPOT_TOKEN=your-hubspot-private-app-token-here",
                f"HUBSPOT_TOKEN={token}"
            )
            
            # Write back to .env
            with open(env_path, 'w') as f:
                f.write(updated_content)
            
            print("✅ HubSpot token configured successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to save token: {e}")
            return False
    else:
        print("⚠️  HubSpot token not configured. You can edit .env file manually later.")
        return True

def test_setup():
    """Test if setup is working"""
    try:
        print("\n🧪 Testing setup...")
        
        # Try to import required packages
        import requests
        import dateutil
        from dotenv import load_dotenv
        
        # Load .env file
        load_dotenv()
        
        # Check if token is set
        token = os.getenv('HUBSPOT_TOKEN')
        if token and token != 'your-hubspot-private-app-token-here':
            print("✅ Setup test passed! Ready to run scripts.")
        else:
            print("⚠️  Setup test passed, but HubSpot token needs to be configured.")
        
        return True
    except ImportError as e:
        print(f"❌ Setup test failed - missing package: {e}")
        return False
    except Exception as e:
        print(f"❌ Setup test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Duplicate Contact Management System - Local Setup")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Setup .env file
    if not setup_env_file():
        sys.exit(1)
    
    # Setup HubSpot token
    if not setup_hubspot_token():
        sys.exit(1)
    
    # Test setup
    if not test_setup():
        sys.exit(1)
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file to add your HubSpot token if not done already")
    print("2. Run any script: python contactmerge.py")
    print("3. Or run specific script: python rest_code/sameday.py")
    print("\n💡 Tip: Check README.md for detailed usage instructions")

if __name__ == "__main__":
    main()