import os
import requests
import time
from datetime import datetime, timezone
from dateutil import parser


# ========== CONFIG ==========
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN', 'your-hubspot-token-here')
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# Target phone number for testing
TEST_PHONE = "8809190913"

# ========== Helper Functions ==========

def get_last_contact_date(contact):
    """Get the most recent contact date from various possible fields"""
    props = contact["properties"]
    
    date_fields = [
        "lastcontactdate",
        "notes_last_contacted", 
        "hs_analytics_last_timestamp"
    ]
    
    latest_date = None
    latest_date_parsed = None
    
    for field in date_fields:
        date_value = props.get(field)
        if date_value:
            try:
                parsed_date = parser.parse(date_value)
                if latest_date_parsed is None or parsed_date > latest_date_parsed:
                    latest_date = date_value
                    latest_date_parsed = parsed_date
            except:
                continue
    
    if not latest_date:
        latest_date = props.get("createdate")
        if latest_date:
            try:
                latest_date_parsed = parser.parse(latest_date)
            except:
                latest_date_parsed = datetime.min.replace(tzinfo=timezone.utc)
    
    return latest_date, latest_date_parsed

def search_contacts_by_phone(phone_number):
    """Search for all contacts with a specific phone number"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    phone_variations = [phone_number, f"+91{phone_number}", f"+91 {phone_number}", f"91{phone_number}"]
    all_contacts = []
    
    for phone_variation in phone_variations:
        payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "phone",
                    "operator": "EQ",
                    "value": phone_variation
                }]
            }],
            "properties": [
                "email", "phone", "hs_additional_emails", "createdate", 
                "firstname", "lastname", "company", "lifecylestage",
                "lastcontactdate", "notes_last_contacted", "hs_analytics_last_timestamp"
            ],
            "limit": 100
        }
        
        try:
            response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            contacts = data.get("results", [])
            
            for contact in contacts:
                if not any(c["id"] == contact["id"] for c in all_contacts):
                    all_contacts.append(contact)
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Error searching for phone {phone_variation}: {e}")
            continue
    
    return all_contacts

def merge_contacts(primary_id, to_merge_id):
    """Merge two contacts - merge to_merge_id into primary_id"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/merge"
    payload = {
        "primaryObjectId": str(primary_id),
        "objectIdToMerge": str(to_merge_id)
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Merge failed: {e}")

def merge_duplicate_contacts_pairwise(phone_number):
    """Handle duplicates using pairwise merging strategy for HubSpot limitations"""
    print(f"🔍 Searching for contacts with phone number: {phone_number}")
    
    # Search for contacts
    contacts = search_contacts_by_phone(phone_number)
    
    if not contacts:
        print(f"📭 No contacts found with phone number {phone_number}")
        return
    
    if len(contacts) == 1:
        print(f"✅ Only one contact found. No merging needed.")
        return
    
    print(f"\n📊 Found {len(contacts)} duplicate contacts")
    
    # Sort contacts by last contact date (most recent first)
    contacts_with_dates = []
    for contact in contacts:
        last_contact_str, last_contact_parsed = get_last_contact_date(contact)
        contacts_with_dates.append({
            'contact': contact,
            'last_contact_str': last_contact_str,
            'last_contact_parsed': last_contact_parsed or datetime.min.replace(tzinfo=timezone.utc)
        })
    
    contacts_with_dates.sort(key=lambda x: x['last_contact_parsed'], reverse=True)
    
    print("\n🎯 HUBSPOT LIMITATION WORKAROUND:")
    print("=" * 70)
    print("⚠️ HubSpot only allows merging 2 contacts at a time due to 'canonical object' restrictions")
    
    if len(contacts) == 2:
        # Simple case: just merge the two
        primary_contact = contacts_with_dates[0]['contact']
        merge_contact = contacts_with_dates[1]['contact']
        
        print(f"\n✅ SIMPLE MERGE (2 contacts):")
        print(f"🏆 Primary: {primary_contact['id']} (Most recent)")
        print(f"🔄 Merge: {merge_contact['id']} → {primary_contact['id']}")
        
        try:
            print(f"\n🚀 Merging {merge_contact['id']} into {primary_contact['id']}...")
            result = merge_contacts(primary_contact['id'], merge_contact['id'])
            print(f"✅ Successfully merged! Final contact: {primary_contact['id']}")
        except Exception as e:
            print(f"❌ Merge failed: {e}")
            
    elif len(contacts) == 3:
        # For 3 contacts: merge 2nd and 3rd first, then merge result with 1st
        print(f"\n🔄 STRATEGY FOR 3 CONTACTS:")
        print("Step 1: Merge 2nd oldest into 3rd oldest")
        print("Step 2: Merge result into most recent")
        
        most_recent = contacts_with_dates[0]['contact']
        second_recent = contacts_with_dates[1]['contact'] 
        oldest = contacts_with_dates[2]['contact']
        
        print(f"\n📋 Execution Plan:")
        print(f"🥇 Most Recent: {most_recent['id']} (Final target)")
        print(f"🥈 2nd Recent: {second_recent['id']} → Merge into oldest first")
        print(f"🥉 Oldest: {oldest['id']} ← First merge target")
        
        try:
            # Step 1: Merge 2nd recent into oldest
            print(f"\n🔄 Step 1: Merging {second_recent['id']} into {oldest['id']}...")
            result1 = merge_contacts(oldest['id'], second_recent['id'])
            print(f"✅ Step 1 complete! Intermediate result: {oldest['id']}")
            
            time.sleep(3)  # Wait between merges
            
            # Step 2: Merge the result into most recent
            print(f"\n🔄 Step 2: Merging {oldest['id']} into {most_recent['id']}...")
            result2 = merge_contacts(most_recent['id'], oldest['id'])
            print(f"✅ Step 2 complete! Final contact: {most_recent['id']}")
            
            print(f"\n🎉 ALL 3 CONTACTS SUCCESSFULLY MERGED!")
            print(f"🏆 Final consolidated contact: {most_recent['id']}")
            
        except Exception as e:
            print(f"❌ Multi-step merge failed: {e}")
            print("💡 You may need to merge these manually in HubSpot UI")
            
    else:
        # For 4+ contacts, this gets complex
        print(f"\n⚠️ COMPLEX CASE ({len(contacts)} contacts):")
        print("HubSpot's merge limitations make this challenging.")
        print("💡 Recommendations:")
        print("1. Use HubSpot's native duplicate management tools")
        print("2. Merge contacts manually in pairs through the UI")
        print("3. Consider using HubSpot's bulk merge features")
        
        print(f"\n📋 Contacts found:")
        for i, item in enumerate(contacts_with_dates, 1):
            contact = item['contact']
            props = contact['properties']
            print(f"{i}. ID: {contact['id']} | Email: {props.get('email', 'N/A')} | Name: {props.get('firstname', '')} {props.get('lastname', '')}")

# ========== Main Logic ==========

def main():
    print("🚀 HUBSPOT-COMPLIANT MERGE - Respects API Limitations")
    print(f"📱 Target Phone Number: {TEST_PHONE}")
    print("⚠️ Works around HubSpot's 'canonical object' merge restrictions")
    print("🎯 Optimized for 2-3 contacts, guidance for 4+")
    print("=" * 80)
    
    try:
        merge_duplicate_contacts_pairwise(TEST_PHONE)
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()
