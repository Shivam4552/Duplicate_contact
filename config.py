"""
Configuration management for Duplicate Contact Management System
"""
import os
from pathlib import Path

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    # Load .env file from the project root
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
    print("✅ Loaded configuration from .env file")
except ImportError:
    print("⚠️  python-dotenv not installed. Using environment variables only.")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# HubSpot Configuration
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN')

if not HUBSPOT_TOKEN or HUBSPOT_TOKEN == 'your-hubspot-private-app-token-here':
    print("❌ HUBSPOT_TOKEN not configured!")
    print("Please set your HubSpot Private App Token in:")
    print("1. Environment variable: export HUBSPOT_TOKEN=your-token")
    print("2. Or in .env file: HUBSPOT_TOKEN=your-token")
    print("\nTo get a token:")
    print("1. Go to HubSpot Settings → Integrations → Private Apps")
    print("2. Create new app with contacts read/write permissions")
    print("3. Copy the generated token")
    exit(1)

# Headers for HubSpot API
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# Optional configuration
TIMEZONE = os.getenv('TIMEZONE', 'UTC')
DATE_FORMAT = os.getenv('DATE_FORMAT', '%Y-%m-%d')
RATE_LIMIT = int(os.getenv('RATE_LIMIT', '10'))  # requests per second

print(f"🔧 Configuration loaded:")
print(f"   Token: {'✅ Set' if HUBSPOT_TOKEN else '❌ Missing'}")
print(f"   Timezone: {TIMEZONE}")
print(f"   Rate Limit: {RATE_LIMIT} req/sec")