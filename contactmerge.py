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

# ========== DATE CONFIGURATION ==========
# Just change this date to process any day you want
TARGET_DATE = datetime(2025, 8, 14, tzinfo=timezone.utc)  # Change this date as needed

# For convenience, you can also use these shortcuts:
# TARGET_DATE = datetime.now(timezone.utc) - timedelta(days=1)  # Yesterday
# TARGET_DATE = datetime.now(timezone.utc) - timedelta(days=2)  # Day before yesterday
# TARGET_DATE = datetime.now(timezone.utc)  # Today

# Calculate the next day for filtering
NEXT_DATE = TARGET_DATE + timedelta(days=1)

# ========== Helper Functions ==========

def normalize_phone(phone):
    """Normalize phone number by removing country codes and spaces"""
    if not phone:
        return None
    phone_str = str(phone).replace("+91", "").replace(" ", "").replace("-", "").strip()
    return phone_str if phone_str.isdigit() and len(phone_str) >= 10 else None

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

def fetch_contacts_for_date():
    """Fetch all contacts created on the target date"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    fetched = 0

    print(f"🔍 Fetching contacts created on {TARGET_DATE.strftime('%Y-%m-%d')}...")

    while True:
        payload = {
            "filterGroups": [{
                "filters": [
                    {
                        "propertyName": "createdate",
                        "operator": "GTE",
                        "value": TARGET_DATE.isoformat()
                    },
                    {
                        "propertyName": "createdate",
                        "operator": "LT", 
                        "value": NEXT_DATE.isoformat()
                    }
                ]
            }],
            "properties": [
                "email", "phone", "hs_additional_emails", "createdate", 
                "firstname", "lastname", "company", "lifecylestage",
                "lastcontactdate", "notes_last_contacted", "hs_analytics_last_timestamp"
            ],
            "limit": 100,
            "sorts": ["createdate"]
        }
        
        if after:
            payload["after"] = after

        try:
            response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            all_contacts.extend(results)
            fetched += len(results)

            if fetched > 0 and fetched % 100 == 0:
                print(f"📊 Fetched {fetched} contacts so far...")

            if "paging" in data and "next" in data["paging"]:
                after = data["paging"]["next"]["after"]
            else:
                break

            time.sleep(0.1)  # Rate limiting
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching contacts: {e}")
            break

    print(f"✅ Total contacts created on {TARGET_DATE.strftime('%Y-%m-%d')}: {len(all_contacts)}")
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

def process_duplicate_group(identifier, contacts, identifier_type="phone"):
    """Process a group of duplicate contacts using pairwise merge strategy"""
    print(f"\n🔄 Processing {identifier_type}: {identifier} ({len(contacts)} contacts)")
    print("=" * 60)
    
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
    
    # Display contacts
    for i, item in enumerate(contacts_with_dates, 1):
        contact = item['contact']
        props = contact['properties']
        name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip() or "No Name"
        print(f"  {i}. ID: {contact['id']} | Name: {name} | Email: {props.get('email', 'N/A')}")
    
    if len(contacts) == 2:
        # Simple case: merge 2 contacts
        primary_contact = contacts_with_dates[0]['contact']
        merge_contact = contacts_with_dates[1]['contact']
        
        try:
            print(f"🚀 Merging {merge_contact['id']} into {primary_contact['id']}...")
            result = merge_contacts(primary_contact['id'], merge_contact['id'])
            print(f"✅ Successfully merged! Final contact: {primary_contact['id']}")
            return {"status": "success", "final_contact": primary_contact['id'], "merged_count": 1}
        except Exception as e:
            print(f"❌ Merge failed: {e}")
            return {"status": "failed", "error": str(e)}
            
    elif len(contacts) == 3:
        # For 3 contacts: use two-step merge strategy
        most_recent = contacts_with_dates[0]['contact']
        second_recent = contacts_with_dates[1]['contact'] 
        oldest = contacts_with_dates[2]['contact']
        
        print(f"🔄 3-contact merge strategy:")
        print(f"  Step 1: {second_recent['id']} → {oldest['id']}")
        print(f"  Step 2: {oldest['id']} → {most_recent['id']}")
        
        try:
            # Step 1: Merge 2nd recent into oldest
            print(f"🔄 Step 1: Merging {second_recent['id']} into {oldest['id']}...")
            result1 = merge_contacts(oldest['id'], second_recent['id'])
            print(f"✅ Step 1 complete!")
            
            time.sleep(3)  # Wait between merges
            
            # Step 2: Merge result into most recent
            print(f"🔄 Step 2: Merging {oldest['id']} into {most_recent['id']}...")
            result2 = merge_contacts(most_recent['id'], oldest['id'])
            print(f"✅ Step 2 complete! Final contact: {most_recent['id']}")
            
            return {"status": "success", "final_contact": most_recent['id'], "merged_count": 2}
            
        except Exception as e:
            print(f"❌ 3-contact merge failed: {e}")
            print("💡 Manual merge required in HubSpot UI")
            return {"status": "failed", "error": str(e), "manual_required": True}
            
    else:
        # For 4+ contacts - too complex for API
        print(f"⚠️ Complex case ({len(contacts)} contacts) - Manual merge required")
        print("💡 Use HubSpot UI duplicate management for this group")
        contact_ids = [item['contact']['id'] for item in contacts_with_dates]
        return {"status": "manual_required", "contact_ids": contact_ids, "count": len(contacts)}

def process_duplicates():
    """Main function to process duplicate contacts for the specified date"""
    
    print("🚀 PROCESSING DUPLICATE CONTACTS")
    print(f"📅 Target Date: {TARGET_DATE.strftime('%Y-%m-%d')}")
    print("🎯 Using HubSpot-compliant pairwise merge strategy")
    print("=" * 80)
    
    # Fetch contacts for the target date
    contacts = fetch_contacts_for_date()
    
    if not contacts:
        print(f"📭 No contacts created on {TARGET_DATE.strftime('%Y-%m-%d')}.")
        return
    
    # Group contacts by phone and email
    phone_groups = defaultdict(list)
    email_groups = defaultdict(list)
    
    for contact in contacts:
        props = contact["properties"]
        email = props.get("email", "").lower().strip() if props.get("email") else None
        phone = normalize_phone(props.get("phone"))
        
        if phone:
            phone_groups[phone].append(contact)
        if email:
            email_groups[email].append(contact)
    
    # Find duplicates
    phone_duplicates = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 1}
    email_duplicates = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 1}
    
    print(f"\n📊 DUPLICATE ANALYSIS:")
    print(f"📱 Phone duplicates found: {len(phone_duplicates)}")
    print(f"📧 Email duplicates found: {len(email_duplicates)}")
    
    # Process results tracking
    results = {
        "phone_success": 0,
        "phone_failed": 0,
        "phone_manual": 0,
        "email_success": 0,
        "email_failed": 0,
        "email_manual": 0,
        "total_merges": 0,
        "manual_cases": []
    }
    
    # Process phone duplicates
    if phone_duplicates:
        print(f"\n📱 PROCESSING PHONE DUPLICATES:")
        print("=" * 50)
        
        for phone, duplicate_contacts in phone_duplicates.items():
            result = process_duplicate_group(phone, duplicate_contacts, "phone")
            
            if result["status"] == "success":
                results["phone_success"] += 1
                results["total_merges"] += result["merged_count"]
            elif result["status"] == "failed":
                results["phone_failed"] += 1
            elif result["status"] == "manual_required":
                results["phone_manual"] += 1
                results["manual_cases"].append({"type": "phone", "identifier": phone, "contacts": result["contact_ids"]})
            
            time.sleep(2)  # Rate limiting between groups
    
    # Process email duplicates
    if email_duplicates:
        print(f"\n📧 PROCESSING EMAIL DUPLICATES:")
        print("=" * 50)
        
        for email, duplicate_contacts in email_duplicates.items():
            result = process_duplicate_group(email, duplicate_contacts, "email")
            
            if result["status"] == "success":
                results["email_success"] += 1
                results["total_merges"] += result.get("merged_count", 0)
            elif result["status"] == "failed":
                results["email_failed"] += 1
            elif result["status"] == "manual_required":
                results["email_manual"] += 1
                results["manual_cases"].append({"type": "email", "identifier": email, "contacts": result["contact_ids"]})
            
            time.sleep(2)  # Rate limiting between groups
    
    # Final Summary
    print(f"\n📊 FINAL PROCESSING SUMMARY:")
    print("=" * 60)
    print(f"📅 Date Processed: {TARGET_DATE.strftime('%Y-%m-%d')}")
    print(f"📧 Total Contacts: {len(contacts)}")
    print(f"🔄 Total Successful Merges: {results['total_merges']}")
    print(f"✅ Phone Merges Successful: {results['phone_success']}")
    print(f"✅ Email Merges Successful: {results['email_success']}")
    print(f"❌ Phone Merges Failed: {results['phone_failed']}")
    print(f"❌ Email Merges Failed: {results['email_failed']}")
    print(f"⚠️ Phone Groups Needing Manual Merge: {results['phone_manual']}")
    print(f"⚠️ Email Groups Needing Manual Merge: {results['email_manual']}")
    
    if results["manual_cases"]:
        print(f"\n📋 MANUAL MERGE REQUIRED:")
        print("=" * 40)
        for case in results["manual_cases"]:
            print(f"{case['type'].upper()}: {case['identifier']}")
            print(f"  Contact IDs: {case['contacts']}")
    
    total_processed = (results['phone_success'] + results['phone_failed'] + results['phone_manual'] + 
                      results['email_success'] + results['email_failed'] + results['email_manual'])
    
    if total_processed > 0:
        success_rate = ((results['phone_success'] + results['email_success']) / total_processed) * 100
        print(f"\n🎯 Overall Success Rate: {success_rate:.1f}%")
    
    print(f"\n🎉 Processing Complete!")

# ========== Main Logic ==========

def main():
    print("🚀 DUPLICATE CONTACT PROCESSOR")
    print(f"📅 Processing Date: {TARGET_DATE.strftime('%Y-%m-%d')}")
    print("🎯 HubSpot-compliant pairwise merge strategy")
    print("=" * 80)
    
    try:
        process_duplicates()
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()
