import os
import requests
import time
from datetime import datetime, timezone, timedelta
from dateutil import parser
import re


# ========== CONFIG ==========
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN', 'your-hubspot-token-here')
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# ========== TARGET PHONE NUMBER ==========
TARGET_PHONE = "9609950075"  # Just change this number

# Define priority lifecycle stages
PRIORITY_LIFECYCLE_STAGES = {"pre-mql", "mql", "sql", "opportunity", "customer", "lapsed customer"}


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


def generate_phone_variations(phone_number):
    """Generate all possible variations of a phone number for search"""
    normalized = normalize_phone(phone_number)
    if not normalized:
        return []
    
    # Generate common variations
    variations = [
        normalized,                    # 9926232462
        f"91{normalized}",            # 919926232462
        f"+91{normalized}",           # +919926232462
        f"+91 {normalized}",          # +91 9926232462
        f"+91-{normalized}",          # +91-9926232462
        f"91-{normalized}",           # 91-9926232462
        f"91 {normalized}",           # 91 9926232462
        f"0{normalized}",             # 09926232462
    ]
    
    # Add formatted variations
    if len(normalized) == 10:
        formatted_variations = [
            f"{normalized[:5]}-{normalized[5:]}",        # 99262-32462
            f"+91 {normalized[:5]}-{normalized[5:]}",    # +91 99262-32462
            f"91-{normalized[:5]}-{normalized[5:]}",     # 91-99262-32462
            f"+91-{normalized[:5]}-{normalized[5:]}",    # +91-99262-32462
        ]
        variations.extend(formatted_variations)
    
    return list(set(variations))  # Remove duplicates


def search_contacts_by_single_variation(phone_variation):
    """Search for contacts using a single phone variation"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    
    while True:
        payload = {
            "filterGroups": [{
                "filters": [
                    {
                        "propertyName": "phone",
                        "operator": "EQ",
                        "value": phone_variation
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

            if "paging" in data and "next" in data["paging"]:
                after = data["paging"]["next"]["after"]
            else:
                break

            time.sleep(0.1)  # Rate limiting
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching contacts for {phone_variation}: {e}")
            break

    return all_contacts


def search_contacts_by_phone_variations(phone_number):
    """Search for contacts using all variations of the phone number"""
    variations = generate_phone_variations(phone_number)
    normalized_target = normalize_phone(phone_number)
    
    if not normalized_target:
        print(f"❌ Invalid phone number: {phone_number}")
        return []
    
    print(f"🔍 Searching for phone number: {phone_number}")
    print(f"🔍 Normalized target: {normalized_target}")
    print(f"🔍 Searching {len(variations)} variations...")
    
    all_found_contacts = []
    unique_contact_ids = set()
    
    # Search each variation separately to avoid API limits
    for i, variation in enumerate(variations, 1):
        print(f"  {i}/{len(variations)} Searching: {variation}")
        
        contacts = search_contacts_by_single_variation(variation)
        
        # Filter to exact normalized matches and deduplicate
        exact_matches = 0
        for contact in contacts:
            contact_phone = normalize_phone(contact["properties"].get("phone"))
            if contact_phone == normalized_target and contact['id'] not in unique_contact_ids:
                all_found_contacts.append(contact)
                unique_contact_ids.add(contact['id'])
                exact_matches += 1
        
        if exact_matches > 0:
            print(f"    ✅ Found {exact_matches} exact matches")
        
        time.sleep(0.2)  # Rate limiting between searches
    
    print(f"✅ Total unique contacts found: {len(all_found_contacts)}")
    return all_found_contacts


def get_last_contact_date(contact):
    """Get the most recent contact date"""
    props = contact["properties"]
    
    date_fields = [
        "lastcontactdate",
        "notes_last_contacted", 
        "hs_analytics_last_timestamp",
        "hs_latest_meeting_activity",
        "hs_latest_sequence_ended_date"
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
    _, last_contact_parsed = get_last_contact_date(contact)
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
    """Calculate a quality score for the contact"""
    props = contact["properties"]
    score = 0
    
    if props.get("firstname"): score += 1
    if props.get("lastname"): score += 1
    if props.get("email"): score += 2
    if props.get("phone"): score += 2
    if props.get("company"): score += 1
    if props.get("jobtitle"): score += 1
    if props.get("website"): score += 1
    if props.get("industry"): score += 1
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
        _, last_contact_parsed = get_last_contact_date(contact)
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
        _, last_contact_parsed = get_last_contact_date(contact)
        quality_score = get_contact_quality_score(contact)
        contacts_with_dates.append({
            'contact': contact,
            'last_contact_parsed': last_contact_parsed or datetime.min.replace(tzinfo=timezone.utc),
            'quality_score': quality_score
        })
    
    contacts_with_dates.sort(key=lambda x: (x['last_contact_parsed'], x['quality_score']), reverse=True)
    primary = contacts_with_dates[0]['contact']
    print(f"  ✅ Primary selected: {primary['id']} (most recent contact)")
    return primary


def merge_contacts(primary_id, to_merge_id):
    """Merge two contacts"""
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


def process_phone_duplicates(phone_number, contacts):
    """Process duplicate contacts for the phone number"""
    print(f"\n🔄 Processing duplicates for: {phone_number}")
    print("=" * 60)
    
    if len(contacts) <= 1:
        print(f"✅ No duplicates found")
        return {"status": "no_duplicates", "count": len(contacts)}
    
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
    merged_count = 0
    for merge_contact in other_contacts:
        try:
            print(f"🚀 Merging {merge_contact['id']} into {primary_contact['id']}...")
            merge_contacts(primary_contact['id'], merge_contact['id'])
            merged_count += 1
            print(f"✅ Success!")
            time.sleep(2)  # Rate limiting
        except Exception as e:
            print(f"❌ Failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    return {"status": "success", "final_contact": primary_contact['id'], "merged_count": merged_count}


def main():
    """Main function"""
    print("🚀 FOCUSED PHONE DUPLICATE PROCESSOR")
    print(f"📱 Target Phone: {TARGET_PHONE}")
    print("🎯 Only fetching contacts matching this phone number")
    print("🧠 Smart merge logic: Lifecycle → Age/Contact → Owner → Quality")
    print("=" * 70)
    
    try:
        # Search for contacts with matching phone number
        contacts = search_contacts_by_phone_variations(TARGET_PHONE)
        
        if not contacts:
            print(f"📭 No contacts found with phone: {TARGET_PHONE}")
            return
        elif len(contacts) == 1:
            print(f"✅ Only one contact found - no duplicates to merge")
            print(f"📝 Contact ID: {contacts[0]['id']}")
            return
        
        # Process duplicates
        result = process_phone_duplicates(TARGET_PHONE, contacts)
        
        # Summary
        print(f"\n📊 FINAL SUMMARY:")
        print("=" * 40)
        print(f"📱 Phone: {TARGET_PHONE}")
        print(f"📧 Contacts Found: {len(contacts)}")
        
        if result["status"] == "success":
            print(f"✅ Merge Successful!")
            print(f"🔄 Merged: {result['merged_count']} contacts")
            print(f"🎯 Final Contact: {result['final_contact']}")
        elif result["status"] == "failed":
            print(f"❌ Merge Failed: {result.get('error')}")
        else:
            print(f"ℹ️ No duplicates to process")
        
        print(f"\n🎉 Complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
