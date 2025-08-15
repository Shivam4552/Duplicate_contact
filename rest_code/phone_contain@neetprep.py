import os
import requests
import time
from datetime import datetime, timezone, timedelta
from dateutil import parser
from collections import defaultdict

# ========== CONFIG ==========
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN', 'your-hubspot-token-here')
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# Create IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# ========== SET TARGET DATE TO YESTERDAY ==========
# Current date: August 7, 2025, so yesterday is August 6, 2025
YESTERDAY = datetime(2025, 8, 6, tzinfo=IST)

# ========== Helper Functions ==========

def fetch_contacts_created_yesterday_with_neetprep_email(target_date, limit=15000):
    """Fetch contacts created on target_date with @neetprep.com email addresses"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    fetched = 0
    page_count = 0

    # Set start time to beginning of the day (00:00:00)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    # Set end time to beginning of next day
    end_of_day = start_of_day + timedelta(days=1)

    print(f"🔍 Fetching contacts created on {target_date.strftime('%Y-%m-%d')} with @neetprep.com emails...")
    print(f"   Start: {start_of_day.isoformat()}")
    print(f"   End:   {end_of_day.isoformat()}")

    while fetched < limit:
        page_count += 1
        payload = {
            "filterGroups": [{
                "filters": [
                    {
                        "propertyName": "createdate",  # Back to createdate
                        "operator": "GTE",
                        "value": start_of_day.isoformat()
                    },
                    {
                        "propertyName": "createdate",  # Back to createdate
                        "operator": "LT",
                        "value": end_of_day.isoformat()
                    },
                    {
                        "propertyName": "email",  # Add email filter
                        "operator": "CONTAINS_TOKEN",
                        "value": "@neetprep.com"
                    }
                ]
            }],
            "properties": ["email", "phone", "hs_additional_emails", "createdate", "firstname", "lastname"],
            "limit": 100,
            "sorts": ["createdate"]  # Sort by create date
        }
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

def display_neetprep_contacts(target_date):
    """Display all contacts created on target_date with @neetprep.com emails"""
    contacts = fetch_contacts_created_yesterday_with_neetprep_email(target_date)
    
    if not contacts:
        print(f"📭 No contacts found with @neetprep.com emails created on {target_date.strftime('%Y-%m-%d')}.")
        return None
    
    print(f"\n📊 Found {len(contacts)} contacts with @neetprep.com emails created on {target_date.strftime('%Y-%m-%d')}.")
    
    print("\n" + "="*80)
    print(f"📧 CONTACTS WITH @NEETPREP.COM EMAILS CREATED ON {target_date.strftime('%Y-%m-%d')}:")
    print("="*80)
    
    for i, contact in enumerate(contacts, 1):
        props = contact["properties"]
        contact_id = contact["id"]
        email = props.get("email", "")
        phone = props.get("phone", "")
        firstname = props.get("firstname", "")
        lastname = props.get("lastname", "")
        created = props.get("createdate", "")
        
        print(f"\n{i}. Contact ID: {contact_id}")
        print(f"   Name: {firstname} {lastname}")
        print(f"   Email: {email}")
        print(f"   Phone: {phone}")
        print(f"   Created: {created}")
        print("-" * 50)
    
    # Summary
    print("\n" + "="*60)
    print("📈 SUMMARY:")
    print("="*60)
    print(f"📧 Total @neetprep.com contacts created yesterday: {len(contacts)}")
    print(f"📅 Date checked: {target_date.strftime('%Y-%m-%d')} (00:00 - 23:59 IST)")
    
    return contacts

def find_duplicates_in_neetprep_contacts(contacts):
    """Find duplicates among the @neetprep.com contacts"""
    if not contacts:
        return None, None
    
    email_groups = defaultdict(list)
    phone_groups = defaultdict(list)
    
    for contact in contacts:
        props = contact["properties"]
        contact_id = contact["id"]
        email = props.get("email", "").lower().strip() if props.get("email") else None
        phone = props.get("phone", "").replace("+91", "").replace(" ", "").replace("-", "").strip() if props.get("phone") else None
        firstname = props.get("firstname", "")
        lastname = props.get("lastname", "")
        created = props.get("createdate")
        
        contact_info = {
            "id": contact_id,
            "email": email,
            "phone": phone,
            "firstname": firstname,
            "lastname": lastname,
            "createdate": created
        }
        
        # Group by email
        if email:
            email_groups[email].append(contact_info)
        
        # Group by phone (if phone has at least 10 digits)
        if phone and phone.isdigit() and len(phone) >= 10:
            phone_groups[phone].append(contact_info)
    
    # Find duplicates
    email_duplicates = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 1}
    phone_duplicates = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 1}
    
    if email_duplicates or phone_duplicates:
        print("\n" + "="*60)
        print("🔄 DUPLICATE ANALYSIS AMONG @NEETPREP.COM CONTACTS:")
        print("="*60)
        
        if email_duplicates:
            print(f"\n📧 Email duplicates found: {len(email_duplicates)} groups")
            for email, duplicate_contacts in email_duplicates.items():
                print(f"\n🔄 Email: {email}")
                for i, contact in enumerate(duplicate_contacts, 1):
                    print(f"  {i}. ID: {contact['id']}, Name: {contact['firstname']} {contact['lastname']}")
        
        if phone_duplicates:
            print(f"\n📱 Phone duplicates found: {len(phone_duplicates)} groups")
            for phone, duplicate_contacts in phone_duplicates.items():
                print(f"\n🔄 Phone: {phone}")
                for i, contact in enumerate(duplicate_contacts, 1):
                    print(f"  {i}. ID: {contact['id']}, Name: {contact['firstname']} {contact['lastname']}")
    
    return email_duplicates, phone_duplicates

# ========== Main Logic ==========

def main():
    print("🚀 Starting @NEETPREP.COM Contact Detection for YESTERDAY...")
    print(f"📅 Target date: {YESTERDAY.strftime('%Y-%m-%d %Z')} (checking contacts created from 00:00 to 23:59 IST)")
    
    # Find all contacts created yesterday with @neetprep.com emails
    neetprep_contacts = display_neetprep_contacts(YESTERDAY)
    
    # Optional: Check for duplicates among the @neetprep.com contacts
    if neetprep_contacts:
        find_duplicates_in_neetprep_contacts(neetprep_contacts)

if __name__ == "__main__":
    main()
