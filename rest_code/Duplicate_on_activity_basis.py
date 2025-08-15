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


# ========== SET YOUR TARGET DATE HERE ==========
TARGET_DATE = datetime(2025, 8, 14, tzinfo=IST)  # Now using IST timezone


# ========== Helper Functions ==========


def fetch_contacts_by_last_activity_date(start_date, end_date, limit=15000):
    """Fetch contacts with last activity between start_date and end_date"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    fetched = 0
    page_count = 0


    print(f"🔍 Fetching contacts with last activity between {start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} and {end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}...")


    while fetched < limit:
        page_count += 1
        payload = {
            "filterGroups": [{
                "filters": [
                    {
                        "propertyName": "notes_last_contacted",  # Changed from createdate
                        "operator": "GTE",
                        "value": start_date.isoformat()
                    },
                    {
                        "propertyName": "notes_last_contacted",  # Changed from createdate
                        "operator": "LT",
                        "value": end_date.isoformat()
                    }
                ]
            }],
            "properties": ["email", "phone", "hs_additional_emails", "createdate", "notes_last_contacted", "firstname", "lastname"],  # Added notes_last_contacted
            "limit": 100,
            "sorts": ["notes_last_contacted"]  # Changed sorting
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


def normalize_phone(phone):
    """Normalize phone number by removing country codes and spaces"""
    if not phone:
        return None
    phone_str = str(phone).replace("+91", "").replace(" ", "").replace("-", "").strip()
    return phone_str if phone_str.isdigit() and len(phone_str) >= 10 else None


def find_duplicates_for_specific_date_by_activity(target_date):
    """Find all duplicate contacts with last activity on the specified date (from 12:00 AM to 11:59:59 PM)"""
    # Set start time to beginning of the day (00:00:00)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Set end time to beginning of next day (this will exclude the next day)
    end_of_day = start_of_day + timedelta(days=1)
    
    print(f"🔍 Exact search range for LAST ACTIVITY:")
    print(f"   Start: {start_of_day.isoformat()}")
    print(f"   End:   {end_of_day.isoformat()}")
    
    contacts = fetch_contacts_by_last_activity_date(start_of_day, end_of_day)
    
    if not contacts:
        print(f"📭 No contacts found with last activity on {target_date.strftime('%Y-%m-%d')}.")
        return None, None
    
    print(f"📊 Found {len(contacts)} contacts with last activity on {target_date.strftime('%Y-%m-%d')} (from 00:00 to 23:59 IST).")
    
    # Group contacts by email and phone
    email_groups = defaultdict(list)
    phone_groups = defaultdict(list)
    
    for contact in contacts:
        props = contact["properties"]
        contact_id = contact["id"]
        email = props.get("email", "").lower().strip() if props.get("email") else None
        phone = normalize_phone(props.get("phone"))
        firstname = props.get("firstname", "")
        lastname = props.get("lastname", "")
        created = props.get("createdate")
        last_activity = props.get("notes_last_contacted")  # Added last activity
        
        contact_info = {
            "id": contact_id,
            "email": email,
            "phone": phone,
            "firstname": firstname,
            "lastname": lastname,
            "createdate": created,
            "last_activity": last_activity  # Added last activity
        }
        
        # Group by email
        if email:
            email_groups[email].append(contact_info)
        
        # Group by phone
        if phone:
            phone_groups[phone].append(contact_info)
    
    # Find duplicates
    email_duplicates = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 1}
    phone_duplicates = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 1}
    
    print("\n" + "="*60)
    print(f"📧 EMAIL DUPLICATES FOUND BY LAST ACTIVITY ON {target_date.strftime('%Y-%m-%d')} (00:00 - 23:59 IST):")
    print("="*60)
    
    if email_duplicates:
        for email, duplicate_contacts in email_duplicates.items():
            print(f"\n🔄 Email: {email}")
            print("-" * 50)
            for i, contact in enumerate(duplicate_contacts, 1):
                print(f"  {i}. ID: {contact['id']}")
                print(f"     Name: {contact['firstname']} {contact['lastname']}")
                print(f"     Phone: {contact['phone']}")
                print(f"     Created: {contact['createdate']}")
                print(f"     Last Activity: {contact['last_activity']}")  # Added last activity display
    else:
        print("✅ No email duplicates found.")
    
    print("\n" + "="*60)
    print(f"📱 PHONE DUPLICATES FOUND BY LAST ACTIVITY ON {target_date.strftime('%Y-%m-%d')} (00:00 - 23:59 IST):")
    print("="*60)
    
    if phone_duplicates:
        for phone, duplicate_contacts in phone_duplicates.items():
            print(f"\n🔄 Phone: {phone}")
            print("-" * 50)
            for i, contact in enumerate(duplicate_contacts, 1):
                print(f"  {i}. ID: {contact['id']}")
                print(f"     Name: {contact['firstname']} {contact['lastname']}")
                print(f"     Email: {contact['email']}")
                print(f"     Created: {contact['createdate']}")
                print(f"     Last Activity: {contact['last_activity']}")  # Added last activity display
    else:
        print("✅ No phone duplicates found.")
    
    # Summary
    total_email_duplicates = sum(len(contacts) for contacts in email_duplicates.values())
    total_phone_duplicates = sum(len(contacts) for contacts in phone_duplicates.values())
    
    print("\n" + "="*60)
    print("📈 SUMMARY:")
    print("="*60)
    print(f"📧 Email duplicate groups: {len(email_duplicates)}")
    print(f"📧 Total contacts with duplicate emails: {total_email_duplicates}")
    print(f"📱 Phone duplicate groups: {len(phone_duplicates)}")
    print(f"📱 Total contacts with duplicate phones: {total_phone_duplicates}")
    
    return email_duplicates, phone_duplicates


def merge_contacts(primary_id, to_merge_id):
    """Merge two contacts"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/merge"
    payload = {
        "primaryObjectId": primary_id,
        "objectIdToMerge": to_merge_id
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Merge failed: {e}")


def find_duplicates_for_date_range_by_activity(start_date, days_range=7):
    """Find duplicates by last activity for multiple dates (useful for checking past week)"""
    print(f"\n🔍 Searching for duplicates by LAST ACTIVITY over {days_range} days starting from {start_date.strftime('%Y-%m-%d')}...")
    
    all_results = {}
    for days_back in range(days_range):
        current_date = start_date - timedelta(days=days_back)
        date_str = current_date.strftime('%Y-%m-%d')
        
        print(f"\n📅 Checking last activity on {date_str}...")
        email_dups, phone_dups = find_duplicates_for_specific_date_by_activity(current_date)
        
        if email_dups or phone_dups:
            all_results[date_str] = {
                'email_duplicates': email_dups,
                'phone_duplicates': phone_dups
            }
    
    return all_results


# ========== Main Logic ==========


def main():
    print("🚀 Starting Duplicate Contact Detection by LAST ACTIVITY DATE...")
    print(f"📅 Target date: {TARGET_DATE.strftime('%Y-%m-%d %Z')} (searching contacts with last activity from 00:00 to 23:59 IST)")
    
    # Find duplicates for the specified date based on last activity
    email_duplicates, phone_duplicates = find_duplicates_for_specific_date_by_activity(TARGET_DATE)
    
    # Optional: Uncomment below to check multiple dates
    """
    # Check duplicates for the past week starting from TARGET_DATE
    range_results = find_duplicates_for_date_range_by_activity(TARGET_DATE, days_range=7)
    if range_results:
        print(f"\n📊 Found duplicates on {len(range_results)} different dates!")
        for date_str, results in range_results.items():
            print(f"  - {date_str}: {len(results['email_duplicates'])} email groups, {len(results['phone_duplicates'])} phone groups")
    """


if __name__ == "__main__":
    main()
