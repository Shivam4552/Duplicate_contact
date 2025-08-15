# 🚀 Quick Start Guide

Get up and running with the Duplicate Contact Management System in minutes!

## Option 1: Automated Setup (Recommended)

### For Linux/Mac:
```bash
# Clone the repository
git clone https://github.com/Shivam4552/Duplicate_contact.git
cd Duplicate_contact

# Run automated setup
./run_local.sh
```

### For Windows:
```bash
# Clone the repository
git clone https://github.com/Shivam4552/Duplicate_contact.git
cd Duplicate_contact

# Run Python setup
python setup.py
```

## Option 2: Manual Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file and add your HubSpot token
nano .env  # or use any text editor
```

### 3. Get HubSpot Token
1. Go to **HubSpot Settings** → **Integrations** → **Private Apps**
2. Create a new private app
3. Grant these scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
4. Copy the generated token
5. Add it to your `.env` file:
   ```
   HUBSPOT_TOKEN=your-actual-token-here
   ```

## 🎯 Run Your First Script

### Process Today's Duplicates:
```bash
python rest_code/sameday.py
```

### Process Specific Date Duplicates:
```bash
python contactmerge.py
```

### Target Specific Phone Number:
```bash
python rest_code/specific_phone_number_logic.py
```

## 🔧 Customize Your Setup

Edit the target date in any script:
```python
# In contactmerge.py (line ~24)
TARGET_DATE = datetime(2025, 8, 14, tzinfo=timezone.utc)

# Or use dynamic dates
TARGET_DATE = datetime.now(timezone.utc) - timedelta(days=1)  # Yesterday
```

## 🆘 Troubleshooting

### "HUBSPOT_TOKEN not configured" Error:
- Make sure you've set the token in `.env` file
- Verify the token is valid and has correct permissions
- Run `python config.py` to test configuration

### Import Errors:
```bash
# Install missing packages
pip install requests python-dateutil python-dotenv
```

### Permission Errors:
- Verify your HubSpot token has contacts read/write permissions
- Check if your HubSpot account has access to the API

## 📊 Expected Output

When running successfully, you'll see:
```
✅ Loaded configuration from .env file
🔧 Configuration loaded:
   Token: ✅ Set
   Timezone: UTC
   Rate Limit: 10 req/sec

🚀 DUPLICATE CONTACT PROCESSOR
📅 Processing Date: 2025-08-14
🎯 HubSpot-compliant pairwise merge strategy
```

## 🎉 You're Ready!

Your local environment is now configured. Check the main [README.md](README.md) for detailed script documentation and advanced usage.

**Need help?** Create an issue in the [GitHub repository](https://github.com/Shivam4552/Duplicate_contact/issues).