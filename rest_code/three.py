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

# Date range - TODAY ONLY
TODAY = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
TOMORROW = TODAY + timedelta(days=1)

# ========== Helper Functions ==========

def normalize_phone(phone):
    """Normalize phone number by removing country codes and spaces"""
    if not phone:
        return None
    phone_str = str(phone).replace("+91", "").replace(" ", "").replace("-", "").strip()
    return phone_str if phone_str.isdigit() and len(phone_str) >= 10 else None

def fetch_todays_contacts(limit=10000):
    """Fetch only contacts created today"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    fetched = 0

    print(f"🔍 Fetching contacts created TODAY ({TODAY.strftime('%Y-%m-%d')})...")

    while fetched < limit:
        payload = {
            "filterGroups": [{
                "filters": [
                    {
                        "propertyName": "createdate",
                        "operator": "GTE",
                        "value": TODAY.isoformat()
                    },
                    {
                        "propertyName": "createdate",
                        "operator": "LT", 
                        "value": TOMORROW.isoformat()
                    }
                ]
            }],
            "properties": [
                "email", "phone", "hs_additional_emails", "createdate", 
                "firstname", "lastname", "company", "lifecylestage"
            ],
            "limit": 100,
            "sorts": ["createdate"]
        }
        
        if after:
            payload["after"] = after

        try:
            response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            print("⏱️ Read timeout while fetching contacts. Try again later.")
            break
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error while fetching contacts: {e}")
            break

        data = response.json()
        results = data.get("results", [])
        all_contacts.extend(results)
        fetched += len(results)

        if fetched > 0:
            print(f"📊 Fetched {fetched} contacts created today so far...")

        if "paging" in data and "next" in data["paging"]:
            after = data["paging"]["next"]["after"]
        else:
            break

        # Small delay to avoid rate limiting
        time.sleep(0.1)

    print(f"✅ Total contacts created today: {len(all_contacts)}")
    return all_contacts[:limit]

def find_todays_contacts_with_multiple_duplicates():
    """Find all phone numbers and emails from TODAY that have more than 2 contacts"""
    
    print("🚀 FINDING TODAY'S CONTACTS WITH MORE THAN 2 DUPLICATES")
    print(f"📅 Date: {TODAY.strftime('%Y-%m-%d')}")
    print("=" * 80)
    
    # Fetch today's contacts only
    contacts = fetch_todays_contacts()
    
    if not contacts:
        print("📭 No contacts created today.")
        return
    
    # Group contacts by phone and email
    phone_groups = defaultdict(list)
    email_groups = defaultdict(list)
    
    print(f"\n📊 Analyzing {len(contacts)} contacts created today for duplicates...")
    
    for contact in contacts:
        props = contact["properties"]
        contact_id = contact["id"]
        email = props.get("email", "").lower().strip() if props.get("email") else None
        phone = normalize_phone(props.get("phone"))
        
        contact_info = {
            "id": contact_id,
            "email": email,
            "phone": phone,
            "firstname": props.get("firstname", ""),
            "lastname": props.get("lastname", ""),
            "createdate": props.get("createdate", ""),
            "company": props.get("company", "")
        }
        
        # Group by phone
        if phone:
            phone_groups[phone].append(contact_info)
        
        # Group by email
        if email:
            email_groups[email].append(contact_info)
    
    # Find groups with more than 2 contacts
    phone_complex_cases = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 2}
    email_complex_cases = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 2}
    
    # Display results
    print("\n" + "="*80)
    print("📱 TODAY'S PHONE NUMBERS WITH MORE THAN 2 CONTACTS:")
    print("="*80)
    
    if phone_complex_cases:
        for phone, duplicate_contacts in phone_complex_cases.items():
            print(f"\n🔄 Phone: {phone} ({len(duplicate_contacts)} contacts created today)")
            print("-" * 60)
            for i, contact in enumerate(duplicate_contacts, 1):
                name = f"{contact['firstname']} {contact['lastname']}".strip() or "No Name"
                created_time = parser.parse(contact['createdate']).strftime('%H:%M:%S') if contact['createdate'] else 'Unknown'
                print(f"  {i}. ID: {contact['id']}")
                print(f"     👤 Name: {name}")
                print(f"     📧 Email: {contact['email'] or 'No Email'}")
                print(f"     ⏰ Created Today at: {created_time}")
                print(f"     🏢 Company: {contact['company'] or 'No Company'}")
                print()
        
        print(f"📊 Phone numbers created today with 3+ contacts: {len(phone_complex_cases)}")
    else:
        print("✅ No phone numbers created today have more than 2 contacts.")
    
    print("\n" + "="*80)
    print("📧 TODAY'S EMAIL ADDRESSES WITH MORE THAN 2 CONTACTS:")
    print("="*80)
    
    if email_complex_cases:
        for email, duplicate_contacts in email_complex_cases.items():
            print(f"\n🔄 Email: {email} ({len(duplicate_contacts)} contacts created today)")
            print("-" * 60)
            for i, contact in enumerate(duplicate_contacts, 1):
                name = f"{contact['firstname']} {contact['lastname']}".strip() or "No Name"
                phone_display = contact['phone'] or 'No Phone'
                created_time = parser.parse(contact['createdate']).strftime('%H:%M:%S') if contact['createdate'] else 'Unknown'
                print(f"  {i}. ID: {contact['id']}")
                print(f"     👤 Name: {name}")
                print(f"     📱 Phone: {phone_display}")
                print(f"     ⏰ Created Today at: {created_time}")
                print(f"     🏢 Company: {contact['company'] or 'No Company'}")
                print()
        
        print(f"📊 Email addresses created today with 3+ contacts: {len(email_complex_cases)}")
    else:
        print("✅ No email addresses created today have more than 2 contacts.")
    
    # Summary
    print("\n" + "="*80)
    print(f"📈 TODAY'S COMPLEX DUPLICATE SUMMARY ({TODAY.strftime('%Y-%m-%d')}):")
    print("="*80)
    print(f"📱 Phone numbers with 3+ duplicates today: {len(phone_complex_cases)}")
    print(f"📧 Email addresses with 3+ duplicates today: {len(email_complex_cases)}")
    
    total_complex_phone_contacts = sum(len(contacts) for contacts in phone_complex_cases.values())
    total_complex_email_contacts = sum(len(contacts) for contacts in email_complex_cases.values())
    
    print(f"📊 Total contacts in complex phone groups today: {total_complex_phone_contacts}")
    print(f"📊 Total contacts in complex email groups today: {total_complex_email_contacts}")
    
    if phone_complex_cases or email_complex_cases:
        print(f"\n⚠️ RECOMMENDATION FOR TODAY'S COMPLEX CASES:")
        print(f"These need special pairwise merge handling due to HubSpot limitations.")
        
        # Show specific phone numbers for easy copy-paste
        if phone_complex_cases:
            print(f"\n📋 Today's phone numbers to process with pairwise merge:")
            for phone in phone_complex_cases.keys():
                print(f"   - {phone}")
        
        if email_complex_cases:
            print(f"\n📋 Today's email addresses to process with pairwise merge:")
            for email in email_complex_cases.keys():
                print(f"   - {email}")
    else:
        print(f"\n✅ EXCELLENT NEWS FOR TODAY!")
        print(f"No contacts created today have more than 2 duplicates.")
        print(f"All today's duplicates can be merged with the simple 2-contact merge!")
    
    return phone_complex_cases, email_complex_cases

def get_todays_duplicate_summary():
    """Provide complete summary of today's duplicates"""
    
    print(f"🔍 TODAY'S COMPLETE DUPLICATE ANALYSIS ({TODAY.strftime('%Y-%m-%d')})")
    print("=" * 80)
    
    contacts = fetch_todays_contacts()
    
    if not contacts:
        print("📭 No contacts created today.")
        return
    
    phone_groups = defaultdict(list)
    email_groups = defaultdict(list)
    
    for contact in contacts:
        props = contact["properties"]
        contact_id = contact["id"]
        email = props.get("email", "").lower().strip() if props.get("email") else None
        phone = normalize_phone(props.get("phone"))
        
        contact_info = {
            "id": contact_id,
            "email": email,
            "phone": phone,
            "firstname": props.get("firstname", ""),
            "lastname": props.get("lastname", ""),
            "createdate": props.get("createdate", "")
        }
        
        if phone:
            phone_groups[phone].append(contact_info)
        if email:
            email_groups[email].append(contact_info)
    
    # Categorize today's duplicates
    phone_pairs = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) == 2}
    phone_complex = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 2}
    
    email_pairs = {email: contacts for email, contacts in email_groups.items() if len(contacts) == 2}
    email_complex = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 2}
    
    print(f"\n📊 TODAY'S DUPLICATE BREAKDOWN:")
    print("=" * 50)
    print(f"📱 Phone duplicates - Simple pairs (2 contacts): {len(phone_pairs)}")
    print(f"📱 Phone duplicates - Complex (3+ contacts): {len(phone_complex)}")
    print(f"📧 Email duplicates - Simple pairs (2 contacts): {len(email_pairs)}")
    print(f"📧 Email duplicates - Complex (3+ contacts): {len(email_complex)}")
    
    print(f"\n✅ Can merge easily today: {len(phone_pairs) + len(email_pairs)} cases")
    print(f"⚠️ Need pairwise merge today: {len(phone_complex) + len(email_complex)} cases")
    
    total_duplicate_contacts = (
        sum(len(contacts) for contacts in phone_pairs.values()) +
        sum(len(contacts) for contacts in phone_complex.values()) +
        sum(len(contacts) for contacts in email_pairs.values()) +
        sum(len(contacts) for contacts in email_complex.values())
    )
    
    print(f"📊 Total contacts involved in duplicates today: {total_duplicate_contacts}")

# ========== Main Logic ==========

def main():
    print("🔍 TODAY'S DUPLICATE CONTACT ANALYSIS")
    print(f"📅 Analyzing contacts created on: {TODAY.strftime('%Y-%m-%d')}")
    print("🎯 Finding TODAY'S contacts with MORE THAN 2 duplicates")
    print("⚠️ These cases need special handling due to HubSpot limitations")
    print("=" * 80)
    
    try:
        # Find today's complex cases (3+ duplicates)
        phone_complex, email_complex = find_todays_contacts_with_multiple_duplicates()
        
        # Also show complete summary
        print(f"\n" + "="*80)
        get_todays_duplicate_summary()
        
        print(f"\n" + "="*80)
        print("💡 NEXT STEPS FOR TODAY'S DUPLICATES:")
        print("="*80)
        print("1. Use simple merge for 2-contact duplicates")
        print("2. Use pairwise merge strategy for 3+ duplicates (listed above)")
        print("3. Process all today's simple cases first")
        print("4. Handle complex cases manually if needed")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()
