import os
import requests
import time
from datetime import datetime, timezone, timedelta
from dateutil import parser
import re
from collections import defaultdict


# ========== CONFIG ==========
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN', 'your-hubspot-token-here')
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# ========== DATE TARGET ==========
TARGET_DATE = datetime(2025, 8, 2, tzinfo=timezone.utc)  # Change this date as needed
NEXT_DATE = TARGET_DATE + timedelta(days=1)

# Define priority lifecycle stages
PRIORITY_LIFECYCLE_STAGES = {"pre-mql", "mql", "sql", "opportunity", "customer", "lapsed customer", "marketingqualifiedlead"}


# ========== HELPER FUNCTIONS ==========

def normalize_phone(phone):
    """Enhanced phone number normalization"""
    if not phone:
        return None
    
    phone_str = str(phone).strip()
    phone_str = re.sub(r'[^\d+]', '', phone_str)
    
    if phone_str.startswith('+91'):
        phone_str = phone_str[3:]
    elif phone_str.startswith('91') and len(phone_str) == 12:
        phone_str = phone_str[2:]
    elif phone_str.startswith('0') and len(phone_str) == 11:
        phone_str = phone_str[1:]
    
    if len(phone_str) == 10 and phone_str.isdigit() and phone_str[0] in '6789':
        return phone_str
    
    return None


def normalize_email(email):
    """Normalize email by converting to lowercase and trimming"""
    if not email:
        return None
    return email.lower().strip()


def get_last_contact_date(contact):
    """Get the most recent contact date from various possible fields"""
    props = contact["properties"]
    
    date_fields = [
        "lastcontactdate",
        "notes_last_contacted", 
        "hs_analytics_last_timestamp",
        "hs_latest_meeting_activity",
        "hs_latest_sequence_ended_date"
    ]
    
    latest_date_parsed = None
    
    for field in date_fields:
        date_value = props.get(field)
        if date_value:
            try:
                parsed_date = parser.parse(date_value)
                if latest_date_parsed is None or parsed_date > latest_date_parsed:
                    latest_date_parsed = parsed_date
            except:
                continue
    
    if not latest_date_parsed:
        latest_date = props.get("createdate")
        if latest_date:
            try:
                latest_date_parsed = parser.parse(latest_date)
            except:
                latest_date_parsed = datetime.min.replace(tzinfo=timezone.utc)
    
    return latest_date_parsed


def has_priority_lifecycle_stage(contact):
    """Check if contact has a priority lifecycle stage"""
    lifecycle_stage = contact["properties"].get("lifecyclestage", "").lower()
    return lifecycle_stage in PRIORITY_LIFECYCLE_STAGES


def is_old_contact(contact):
    """Check if contact is older than 1 month"""
    create_date_str = contact["properties"].get("createdate")
    if not create_date_str:
        return False
    
    try:
        create_date = parser.parse(create_date_str)
        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        return create_date < one_month_ago
    except:
        return False


def has_owner(contact):
    """Check if contact has an owner assigned"""
    owner = contact["properties"].get("hubspot_owner_id")
    return bool(owner and owner.strip())


def was_contacted_recently(contact):
    """Check if contact was contacted within 1 month"""
    last_contact_parsed = get_last_contact_date(contact)
    if not last_contact_parsed:
        return False
    
    one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    return last_contact_parsed > one_month_ago


def get_create_date(contact):
    """Get parsed create date of contact"""
    create_date_str = contact["properties"].get("createdate")
    if not create_date_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    
    try:
        return parser.parse(create_date_str)
    except:
        return datetime.min.replace(tzinfo=timezone.utc)


def get_contact_quality_score(contact):
    """Calculate a quality score for the contact based on data completeness"""
    props = contact["properties"]
    score = 0
    
    # Basic info
    if props.get("firstname"): score += 1
    if props.get("lastname"): score += 1
    if props.get("email"): score += 2
    if props.get("phone"): score += 2
    
    # Advanced info
    if props.get("city"): score += 1
    if props.get("state"): score += 1
    
    return score


def determine_primary_contact(contacts):
    """Determine which contact should be primary based on business rules"""
    
    print(f"🧠 Analyzing {len(contacts)} contacts to determine primary...")
    
    # Rule 1: Priority lifecycle stages
    priority_contacts = [c for c in contacts if has_priority_lifecycle_stage(c)]
    if priority_contacts:
        if len(priority_contacts) == 1:
            print(f"  ✅ Primary selected: {priority_contacts[0]['id']} (priority lifecycle)")
            return priority_contacts[0]
        else:
            return get_highest_quality_contact(priority_contacts)
    
    # Rule 2: Old uncontacted contacts
    old_uncontacted = [c for c in contacts if is_old_contact(c) and not was_contacted_recently(c)]
    if old_uncontacted:
        if len(old_uncontacted) == 1:
            print(f"  ✅ Primary selected: {old_uncontacted[0]['id']} (old uncontacted)")
            return old_uncontacted[0]
        else:
            oldest = min(old_uncontacted, key=get_create_date)
            print(f"  ✅ Primary selected: {oldest['id']} (oldest uncontacted)")
            return oldest
    
    # Rule 3: Recent contacts with owner
    recent_with_owner = [c for c in contacts if not is_old_contact(c) and has_owner(c)]
    if recent_with_owner:
        if len(recent_with_owner) == 1:
            print(f"  ✅ Primary selected: {recent_with_owner[0]['id']} (recent with owner)")
            return recent_with_owner[0]
        else:
            return get_most_recent_contact(recent_with_owner)
    
    # Rule 4: Contacts with no owner - pick newest
    no_owner_contacts = [c for c in contacts if not has_owner(c)]
    if no_owner_contacts:
        newest = max(no_owner_contacts, key=get_create_date)
        print(f"  ✅ Primary selected: {newest['id']} (newest without owner)")
        return newest
    
    # Rule 5: Fallback
    return get_most_recent_contact(contacts)


def get_highest_quality_contact(contacts):
    """Get contact with highest quality score"""
    contacts_with_quality = []
    for contact in contacts:
        quality_score = get_contact_quality_score(contact)
        last_contact_parsed = get_last_contact_date(contact)
        contacts_with_quality.append({
            'contact': contact,
            'quality_score': quality_score,
            'last_contact_parsed': last_contact_parsed or datetime.min.replace(tzinfo=timezone.utc)
        })
    
    contacts_with_quality.sort(key=lambda x: (x['quality_score'], x['last_contact_parsed']), reverse=True)
    primary = contacts_with_quality[0]['contact']
    print(f"  ✅ Primary selected: {primary['id']} (highest quality)")
    return primary


def get_most_recent_contact(contacts):
    """Get contact with most recent contact date"""
    contacts_with_dates = []
    for contact in contacts:
        last_contact_parsed = get_last_contact_date(contact)
        quality_score = get_contact_quality_score(contact)
        contacts_with_dates.append({
            'contact': contact,
            'last_contact_parsed': last_contact_parsed or datetime.min.replace(tzinfo=timezone.utc),
            'quality_score': quality_score
        })
    
    contacts_with_dates.sort(key=lambda x: (x['last_contact_parsed'], x['quality_score']), reverse=True)
    primary = contacts_with_dates[0]['contact']
    print(f"  ✅ Primary selected: {primary['id']} (most recent contact with quality: {contacts_with_dates[0]['quality_score']})")
    return primary


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
                "firstname", "lastname", "company", "lifecyclestage", "jobtitle",
                "website", "industry", "city", "state",
                "lastcontactdate", "notes_last_contacted", "hs_analytics_last_timestamp",
                "hs_latest_meeting_activity", "hs_latest_sequence_ended_date",
                "hubspot_owner_id"
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
    """Process a group of duplicate contacts using intelligent merge strategy"""
    print(f"\n🔄 Processing {identifier_type}: {identifier} ({len(contacts)} contacts)")
    print("=" * 60)
    
    # Display contact details
    for i, contact in enumerate(contacts, 1):
        props = contact['properties']
        name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip() or "No Name"
        lifecycle = props.get('lifecyclestage', 'N/A')
        owner = "Yes" if props.get('hubspot_owner_id') else "No"
        created = props.get('createdate', 'N/A')[:10] if props.get('createdate') else 'N/A'
        quality_score = get_contact_quality_score(contact)
        
        print(f"  {i}. ID: {contact['id']} | {name} | Quality: {quality_score}")
        print(f"     Phone: {props.get('phone', 'N/A')} | Email: {props.get('email', 'N/A')}")
        print(f"     Lifecycle: {lifecycle} | Owner: {owner} | Created: {created}")
        print()
    
    # Determine primary and merge
    primary_contact = determine_primary_contact(contacts)
    other_contacts = [c for c in contacts if c['id'] != primary_contact['id']]
    
    print(f"🎯 Primary Contact: {primary_contact['id']}")
    print(f"📝 Merging: {[c['id'] for c in other_contacts]} → {primary_contact['id']}")
    
    # Execute merges
    for merge_contact in other_contacts:
        try:
            print(f"🚀 Merging {merge_contact['id']} into {primary_contact['id']}...")
            merge_contacts(primary_contact['id'], merge_contact['id'])
            print(f"✅ Success!")
            time.sleep(2)  # Rate limiting
        except Exception as e:
            print(f"❌ Failed: {e}")
            return


def process_all_duplicates():
    """Main function to process all duplicate contacts for the specified date"""
    
    print("🚀 PROCESSING ALL DUPLICATE CONTACTS")
    print(f"📅 Date: {TARGET_DATE.strftime('%Y-%m-%d')}")
    print("🧠 Using intelligent business-rule merge strategy")
    print("🔍 Priority: Lifecycle → Age/Contact → Owner → Quality → Fallback")
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
        email = normalize_email(props.get("email"))
        phone = normalize_phone(props.get("phone"))
        
        if phone:
            phone_groups[phone].append(contact)
        if email:
            email_groups[email].append(contact)
    
    # Find duplicates
    phone_duplicates = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 1}
    email_duplicates = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 1}
    
    print(f"\n📊 DUPLICATE ANALYSIS FOR {TARGET_DATE.strftime('%Y-%m-%d')}:")
    print(f"📱 Phone duplicates found: {len(phone_duplicates)}")
    print(f"📧 Email duplicates found: {len(email_duplicates)}")
    
    # Process results tracking
    results = {
        "phone_success": 0,
        "phone_failed": 0,
        "email_success": 0,
        "email_failed": 0,
        "total_merges": 0
    }
    
    # Process phone duplicates
    if phone_duplicates:
        print(f"\n📱 PROCESSING PHONE DUPLICATES:")
        print("=" * 50)
        
        for phone, duplicate_contacts in phone_duplicates.items():
            try:
                process_duplicate_group(phone, duplicate_contacts, "phone")
                results["phone_success"] += 1
                results["total_merges"] += len(duplicate_contacts) - 1
            except Exception as e:
                print(f"❌ Group failed: {e}")
                results["phone_failed"] += 1
            
            time.sleep(2)  # Rate limiting between groups
    
    # Process email duplicates
    if email_duplicates:
        print(f"\n📧 PROCESSING EMAIL DUPLICATES:")
        print("=" * 50)
        
        for email, duplicate_contacts in email_duplicates.items():
            try:
                process_duplicate_group(email, duplicate_contacts, "email")
                results["email_success"] += 1
                results["total_merges"] += len(duplicate_contacts) - 1
            except Exception as e:
                print(f"❌ Group failed: {e}")
                results["email_failed"] += 1
            
            time.sleep(2)  # Rate limiting between groups
    
    # Final Summary
    print(f"\n📊 FINAL PROCESSING SUMMARY:")
    print("=" * 60)
    print(f"📅 Date Processed: {TARGET_DATE.strftime('%Y-%m-%d')}")
    print(f"📧 Total Contacts: {len(contacts)}")
    print(f"🔄 Total Successful Merges: {results['total_merges']}")
    print(f"✅ Phone Groups Successful: {results['phone_success']}")
    print(f"✅ Email Groups Successful: {results['email_success']}")
    print(f"❌ Phone Groups Failed: {results['phone_failed']}")
    print(f"❌ Email Groups Failed: {results['email_failed']}")
    
    print(f"\n🎉 Processing Complete for {TARGET_DATE.strftime('%Y-%m-%d')}!")


# ========== Main Logic ==========


def main():
    print("🚀 DATE-BASED DUPLICATE CONTACT PROCESSOR")
    print(f"📅 Processing Date: {TARGET_DATE.strftime('%Y-%m-%d')}")
    print("🎯 Finds and merges ALL duplicates for the specified date")
    print("🧠 Smart merge logic: Lifecycle → Age/Contact → Owner → Quality")
    print("=" * 80)
    
    try:
        process_all_duplicates()
    except Exception as e:
        print(f"❌ An error occurred: {e}")


if __name__ == "__main__":
    main()
