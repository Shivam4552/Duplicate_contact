import os
import requests
import time
from datetime import datetime, timezone, timedelta
from dateutil import parser

# ========== CONFIG ==========
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN', 'your-hubspot-token-here')
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# Create IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# ========== SET YOUR TARGET DATE HERE (OPTIONAL) ==========
TARGET_DATE = datetime(2025, 8, 1, tzinfo=IST)  # Now using IST timezone

# ========== Helper Functions ==========

def normalize_phone(phone):
    """Check if phone number exists and is valid"""
    if not phone:
        return False
    phone_str = str(phone).replace("+91", "").replace(" ", "").replace("-", "").strip()
    return phone_str.isdigit() and len(phone_str) >= 10

def fetch_contacts_without_phone(start_date=None, end_date=None, limit=15000):
    """Fetch contacts and count those without phone numbers"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    fetched = 0
    page_count = 0

    if start_date and end_date:
        print(f"🔍 Fetching contacts created between {start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} and {end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}...")
    else:
        print(f"🔍 Fetching all contacts...")

    while fetched < limit:
        page_count += 1
        payload = {
            "properties": ["email", "phone", "createdate", "firstname", "lastname"],
            "limit": 100,
            "sorts": ["createdate"]
        }
        
        # Add date filters if provided
        if start_date and end_date:
            payload["filterGroups"] = [{
                "filters": [
                    {
                        "propertyName": "createdate",
                        "operator": "GTE",
                        "value": start_date.isoformat()
                    },
                    {
                        "propertyName": "createdate",
                        "operator": "LT",
                        "value": end_date.isoformat()
                    }
                ]
            }]
        
        if after:
            payload["after"] = after

        try:
            print(f"📄 Fetching page {page_count}... (Total so far: {fetched})")
            response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            print("⏱️ Read timeout while fetching contacts. Continuing with what we have...")
            break
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error while fetching contacts: {e}")
            break

        data = response.json()
        results = data.get("results", [])
        
        if not results:
            print("📭 No more results found.")
            break
            
        all_contacts.extend(results)
        fetched += len(results)
        
        print(f"✅ Page {page_count}: Retrieved {len(results)} contacts")

        # Check if there are more pages
        if "paging" in data and "next" in data["paging"]:
            after = data["paging"]["next"]["after"]
            time.sleep(0.1)  # Small delay to avoid rate limiting
        else:
            print("📄 No more pages available.")
            break

    print(f"🎯 Total contacts fetched: {len(all_contacts)}")
    return all_contacts[:limit]

def count_contacts_without_phone(target_date=None):
    """Count contacts without phone numbers for a specific date or all contacts"""
    
    if target_date:
        # Set start time to beginning of the day (00:00:00)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # Set end time to beginning of next day
        end_of_day = start_of_day + timedelta(days=1)
        
        print(f"🔍 Checking contacts created on {target_date.strftime('%Y-%m-%d')} (from 00:00 to 23:59 IST)")
        contacts = fetch_contacts_without_phone(start_of_day, end_of_day)
    else:
        print(f"🔍 Checking all contacts")
        contacts = fetch_contacts_without_phone()
    
    if not contacts:
        print("📭 No contacts found.")
        return
    
    total_contacts = len(contacts)
    contacts_without_phone = 0
    contacts_with_phone = 0
    
    print(f"\n📊 Analyzing {total_contacts} contacts...")
    
    for contact in contacts:
        props = contact["properties"]
        phone = props.get("phone")
        
        if not normalize_phone(phone):
            contacts_without_phone += 1
        else:
            contacts_with_phone += 1
    
    # Display results
    print("\n" + "="*60)
    print("📈 PHONE NUMBER ANALYSIS RESULTS:")
    print("="*60)
    print(f"📊 Total contacts analyzed: {total_contacts}")
    print(f"📱 Contacts WITH phone numbers: {contacts_with_phone}")
    print(f"❌ Contacts WITHOUT phone numbers: {contacts_without_phone}")
    
    if total_contacts > 0:
        percentage_without_phone = (contacts_without_phone / total_contacts) * 100
        percentage_with_phone = (contacts_with_phone / total_contacts) * 100
        print(f"📊 Percentage WITHOUT phone: {percentage_without_phone:.2f}%")
        print(f"📊 Percentage WITH phone: {percentage_with_phone:.2f}%")
    
    return contacts_without_phone

# ========== Main Logic ==========

def main():
    print("🚀 Starting Phone Number Analysis...")
    
    # Option 1: Count for specific date
    print(f"📅 Analyzing contacts for: {TARGET_DATE.strftime('%Y-%m-%d %Z')}")
    count_without_phone_specific_date = count_contacts_without_phone(TARGET_DATE)
    
    # Option 2: Count for all contacts (uncomment if needed)
    """
    print(f"\n📅 Analyzing all contacts...")
    count_without_phone_all = count_contacts_without_phone()
    """
    
    print(f"\n🎯 FINAL RESULT: {count_without_phone_specific_date} contacts don't have phone numbers on {TARGET_DATE.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
