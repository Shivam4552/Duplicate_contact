import os
import requests
import time
from datetime import datetime, timezone, timedelta
from dateutil import parser
from collections import defaultdict
import re

# ========== CONFIG ==========
HUBSPOT_TOKEN = os.getenv('HUBSPOT_TOKEN', 'your-hubspot-token-here')
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

NEETPREP_DOMAIN = "@neetprep.com"
NEW_CONTACT_HOURS = 24  # Contacts newer than this are "new"

# ========== Helper Functions ==========

def normalize_phone(phone):
    """Normalize phone number by removing country codes and spaces"""
    if not phone:
        return None
    phone_str = str(phone).replace("+91", "").replace(" ", "").replace("-", "").strip()
    return phone_str if phone_str.isdigit() and len(phone_str) >= 10 else None

def is_system_generated_email(email):
    """Check if email is system generated (number@neetprep.com format)"""
    if not email:
        return False
    pattern = r'^\d+@neetprep\.com$'
    return bool(re.match(pattern, email.lower()))

def get_creation_date(contact):
    """Get contact creation date"""
    create_date_str = contact["properties"].get("createdate")
    if create_date_str:
        try:
            return parser.parse(create_date_str)
        except:
            return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)

def is_new_contact(contact, hours=NEW_CONTACT_HOURS):
    """Check if contact was created within specified hours"""
    creation_date = get_creation_date(contact)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return creation_date > cutoff

def get_contacts_by_phone(phone):
    """Get all contacts with same phone number"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "phone",
                "operator": "EQ",
                "value": phone
            }]
        }],
        "properties": [
            "email", "phone", "hs_additional_emails", "createdate", 
            "firstname", "lastname", "company", "lifecyclestage",
            "duplicate_contact_notes", "notes_last_contacted", "lastcontactdate"  # Updated property name
        ],
        "limit": 100
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching contacts by phone: {e}")
        return []

def add_duplicate_contact_note(contact_id, note):
    """Add note to custom duplicate_contact_notes property"""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    
    # Get current notes from custom property
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        current_data = response.json()
        current_notes = current_data.get("properties", {}).get("duplicate_contact_notes", "")  # Updated property name
        
        # Create timestamped note
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        new_note = f"[{timestamp}] {note}"
        
        # Append to existing notes
        if current_notes:
            updated_notes = f"{current_notes}\n{new_note}"
        else:
            updated_notes = new_note
        
        # Update contact with new notes
        payload = {
            "properties": {
                "duplicate_contact_notes": updated_notes,  # Updated property name
                "notes_last_contacted": f"Last duplicate merge: {timestamp}"  # Also update general notes
            }
        }
        
        response = requests.patch(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        print(f"📝 Added note to contact {contact_id}: {note}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error adding duplicate contact note: {e}")
        return False

def update_additional_emails(contact_id, additional_emails_list):
    """Update additional emails field"""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    
    # Join emails with semicolon as HubSpot expects
    additional_emails_str = ";".join(additional_emails_list) if additional_emails_list else ""
    
    payload = {
        "properties": {
            "hs_additional_emails": additional_emails_str
        }
    }
    
    try:
        response = requests.patch(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        print(f"📧 Updated additional emails for contact {contact_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Error updating additional emails: {e}")
        return False

def merge_contacts(primary_id, secondary_id):
    """Merge secondary contact into primary"""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/merge"
    payload = {
        "primaryObjectId": str(primary_id),
        "objectIdToMerge": str(secondary_id)
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        print(f"🔄 Successfully merged contact {secondary_id} into {primary_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Merge failed: {e}")
        return False

# ========== Processing Functions ==========

def process_new_contact_duplicates(phone, contacts):
    """
    LOGIC FOR NEW CONTACTS:
    1. Identify new contacts (< 24 hours) vs old contacts
    2. Find system email contact (number@neetprep.com) in old contacts
    3. For each new personal email contact:
       - Add personal email to system contact's additional emails
       - Add merge note to system contact
       - Merge new contact into system contact
    """
    print(f"\n🆕 Processing NEW contact duplicates for phone: {phone}")
    print("=" * 70)
    
    # Separate new vs old contacts
    new_contacts = []
    old_contacts = []
    
    for contact in contacts:
        if is_new_contact(contact):
            new_contacts.append(contact)
        else:
            old_contacts.append(contact)
    
    print(f"📊 Analysis:")
    print(f"   🆕 New contacts (< {NEW_CONTACT_HOURS}h): {len(new_contacts)}")
    print(f"   🗂️ Old contacts (> {NEW_CONTACT_HOURS}h): {len(old_contacts)}")
    
    # Find system email contact (should be in old contacts)
    system_contact = None
    for contact in old_contacts:
        email = contact["properties"].get("email", "")
        if is_system_generated_email(email):
            system_contact = contact
            break
    
    if not system_contact:
        print("⚠️ No system email contact found in old contacts")
        return {"status": "no_system_contact"}
    
    system_email = system_contact["properties"].get("email", "")
    print(f"🎯 System contact found:")
    print(f"   ID: {system_contact['id']}")
    print(f"   Email: {system_email}")
    
    # Process each new contact with personal email
    merged_count = 0
    processed_emails = []
    
    for new_contact in new_contacts:
        if new_contact["id"] == system_contact["id"]:
            continue
            
        new_email = new_contact["properties"].get("email", "")
        if new_email and not is_system_generated_email(new_email):
            
            print(f"\n🔄 Processing new contact:")
            print(f"   ID: {new_contact['id']}")
            print(f"   Personal Email: {new_email}")
            
            # Step 1: Add personal email to system contact's additional emails
            current_additional = system_contact["properties"].get("hs_additional_emails", "")
            additional_emails = [e.strip() for e in current_additional.split(";") if e.strip()] if current_additional else []
            
            if new_email not in additional_emails:
                additional_emails.append(new_email)
                if update_additional_emails(system_contact["id"], additional_emails):
                    print(f"   ✅ Added {new_email} to additional emails")
                else:
                    print(f"   ⚠️ Failed to add to additional emails")
            
            # Step 2: Add merge note to system contact
            note = f"MERGED: Personal email contact {new_contact['id']} with email {new_email} merged into system contact. Personal email preserved in additional emails."
            add_duplicate_contact_note(system_contact["id"], note)
            
            # Step 3: Merge new contact into system contact
            if merge_contacts(system_contact["id"], new_contact["id"]):
                merged_count += 1
                processed_emails.append(new_email)
                print(f"   ✅ Successfully merged contact {new_contact['id']}")
            else:
                print(f"   ❌ Failed to merge contact {new_contact['id']}")
            
            time.sleep(2)  # Rate limiting
    
    # Final note summarizing all merges
    if processed_emails:
        summary_note = f"NEW CONTACT MERGE SUMMARY: Merged {merged_count} new personal email contacts. Emails preserved: {', '.join(processed_emails)}"
        add_duplicate_contact_note(system_contact["id"], summary_note)
    
    return {
        "status": "success", 
        "merged_count": merged_count, 
        "system_contact": system_contact["id"],
        "processed_emails": processed_emails
    }

def process_old_contact_duplicates(phone, contacts):
    """
    LOGIC FOR OLD CONTACTS:
    1. Sort contacts by creation date (oldest first)
    2. Find system email contact (number@neetprep.com)
    3. Identify personal email contacts
    4. Handle scenarios:
       - 2 contacts (1 system + 1 personal): Add remark that system is duplicate of personal
       - 3+ contacts (1 system + multiple personal): Merge all, prioritize latest personal email
    """
    print(f"\n🗂️ Processing OLD contact duplicates for phone: {phone}")
    print("=" * 70)
    
    # Sort contacts by creation date (oldest first)
    contacts_sorted = sorted(contacts, key=get_creation_date)
    
    print(f"📊 Contact Analysis (oldest to newest):")
    for i, contact in enumerate(contacts_sorted, 1):
        email = contact["properties"].get("email", "N/A")
        create_date = get_creation_date(contact).strftime("%Y-%m-%d %H:%M")
        email_type = "🏫 SYSTEM" if is_system_generated_email(email) else "👤 PERSONAL"
        name = f"{contact['properties'].get('firstname', '')} {contact['properties'].get('lastname', '')}".strip() or "No Name"
        
        print(f"   {i}. {email_type} | ID: {contact['id']}")
        print(f"      Name: {name} | Email: {email} | Created: {create_date}")
    
    # Find system email contact and personal contacts
    system_contact = None
    personal_contacts = []
    
    for contact in contacts_sorted:
        email = contact["properties"].get("email", "")
        if is_system_generated_email(email):
            system_contact = contact
        else:
            personal_contacts.append(contact)
    
    if not system_contact:
        print("⚠️ No system email contact found - cannot determine primary")
        return {"status": "no_system_contact"}
    
    system_email = system_contact["properties"].get("email", "")
    print(f"\n🎯 System contact (primary): {system_contact['id']} ({system_email})")
    print(f"👥 Personal email contacts to process: {len(personal_contacts)}")
    
    if len(personal_contacts) == 0:
        print("ℹ️ No personal email contacts to merge")
        return {"status": "no_personal_contacts"}
    
    elif len(personal_contacts) == 1:
        # SCENARIO 1: 2 contacts (1 system + 1 personal)
        personal_contact = personal_contacts[0]
        personal_email = personal_contact["properties"].get("email", "")
        
        print(f"\n📧 SCENARIO 1: Single personal contact")
        print(f"   Personal Email: {personal_email}")
        print(f"   Personal Contact ID: {personal_contact['id']}")
        
        # Add remark that system email is duplicate of personal email
        remark = f"DUPLICATE REMARK: System email {system_email} is duplicate of personal email {personal_email}. Original personal email preserved in additional emails."
        add_duplicate_contact_note(system_contact["id"], remark)
        
        # Add personal email to additional emails
        current_additional = system_contact["properties"].get("hs_additional_emails", "")
        additional_emails = [e.strip() for e in current_additional.split(";") if e.strip()] if current_additional else []
        
        if personal_email not in additional_emails:
            additional_emails.append(personal_email)
            update_additional_emails(system_contact["id"], additional_emails)
        
        # Merge personal contact into system contact
        if merge_contacts(system_contact["id"], personal_contact["id"]):
            merge_note = f"MERGED: Personal email contact {personal_contact['id']} with email {personal_email} merged into system contact."
            add_duplicate_contact_note(system_contact["id"], merge_note)
            print(f"✅ Successfully merged personal contact into system contact")
            return {"status": "success", "merged_count": 1, "scenario": "single_personal"}
        else:
            return {"status": "merge_failed"}
    
    elif len(personal_contacts) >= 2:
        # SCENARIO 2: 3+ contacts (1 system + multiple personal)
        print(f"\n🔄 SCENARIO 2: Multiple personal contacts ({len(personal_contacts)} contacts)")
        
        # Get latest personal contact (most recent creation date)
        latest_personal = max(personal_contacts, key=get_creation_date)
        other_personals = [c for c in personal_contacts if c["id"] != latest_personal["id"]]
        
        latest_email = latest_personal["properties"].get("email", "")
        latest_date = get_creation_date(latest_personal).strftime("%Y-%m-%d %H:%M")
        
        print(f"   📧 Latest personal email: {latest_email} (Created: {latest_date})")
        print(f"   📧 Other personal emails: {len(other_personals)}")
        
        # Collect all personal emails for additional emails
        personal_emails = []
        for contact in personal_contacts:
            email = contact["properties"].get("email", "")
            if email:
                personal_emails.append(email)
        
        print(f"   📧 All personal emails to preserve: {', '.join(personal_emails)}")
        
        # Update system contact with all personal emails as additional
        update_additional_emails(system_contact["id"], personal_emails)
        
        # Add comprehensive note
        emails_list = ", ".join(personal_emails)
        comprehensive_note = f"MULTIPLE DUPLICATE MERGE: Merged {len(personal_contacts)} personal email contacts. Latest email: {latest_email}. All emails: {emails_list}. Latest email prioritized."
        add_duplicate_contact_note(system_contact["id"], comprehensive_note)
        
        # Add individual notes for each personal contact
        for i, contact in enumerate(personal_contacts, 1):
            email = contact["properties"].get("email", "")
            is_latest = contact["id"] == latest_personal["id"]
            priority = "LATEST" if is_latest else f"OLDER #{i}"
            
            individual_note = f"PERSONAL EMAIL {priority}: {email} from contact {contact['id']} - {'Latest email kept as priority' if is_latest else 'Older email merged'}"
            add_duplicate_contact_note(system_contact["id"], individual_note)
        
        # Merge all personal contacts into system contact (latest first, then others)
        merged_count = 0
        
        # First merge latest personal contact
        print(f"\n   🔄 Merging latest personal contact {latest_personal['id']}...")
        if merge_contacts(system_contact["id"], latest_personal["id"]):
            merged_count += 1
            time.sleep(2)
        
        # Then merge other personal contacts
        for contact in other_personals:
            print(f"   🔄 Merging personal contact {contact['id']}...")
            if merge_contacts(system_contact["id"], contact["id"]):
                merged_count += 1
            else:
                print(f"   ❌ Failed to merge {contact['id']}")
            time.sleep(2)
        
        # Final summary note
        final_note = f"MERGE COMPLETE: Successfully merged {merged_count}/{len(personal_contacts)} personal contacts. System email {system_email} remains primary. All personal emails preserved."
        add_duplicate_contact_note(system_contact["id"], final_note)
        
        return {
            "status": "success", 
            "merged_count": merged_count, 
            "scenario": "multiple_personal",
            "total_contacts": len(personal_contacts),
            "latest_email": latest_email
        }

def test_specific_phone_number(phone_number):
    """
    TESTING LOGIC:
    1. Normalize and validate phone number
    2. Fetch all contacts with this phone number
    3. Display detailed information about each contact
    4. Analyze the scenario (new vs old contacts)
    5. Ask for user confirmation before processing
    6. Execute appropriate processing logic
    7. Display detailed results
    """
    
    print(f"🧪 TESTING SPECIFIC PHONE NUMBER")
    print("=" * 60)
    print(f"📱 Input Phone Number: {phone_number}")
    
    # Step 1: Normalize the phone number
    normalized_phone = normalize_phone(phone_number)
    if not normalized_phone:
        print(f"❌ Invalid phone number format: {phone_number}")
        print("💡 Expected format: 10-digit number (with or without +91)")
        return
    
    print(f"📱 Normalized Phone: {normalized_phone}")
    
    # Step 2: Get all contacts with this phone number
    print(f"\n🔍 Searching for contacts with phone: {normalized_phone}")
    contacts = get_contacts_by_phone(normalized_phone)
    
    if not contacts:
        print(f"📭 No contacts found with phone number: {normalized_phone}")
        print("💡 This phone number has no duplicates to process")
        return
    
    print(f"📊 Found {len(contacts)} contact(s) with this phone number")
    
    # Step 3: Analyze and display contact details
    print(f"\n📋 DETAILED CONTACT ANALYSIS:")
    print("-" * 80)
    
    new_contacts = []
    old_contacts = []
    system_contacts = []
    personal_contacts = []
    
    for i, contact in enumerate(contacts, 1):
        props = contact["properties"]
        email = props.get("email", "N/A")
        name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip() or "No Name"
        create_date = get_creation_date(contact)
        create_date_str = create_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Categorize contact
        is_new = is_new_contact(contact)
        is_system = is_system_generated_email(email)
        
        if is_new:
            new_contacts.append(contact)
        else:
            old_contacts.append(contact)
            
        if is_system:
            system_contacts.append(contact)
        else:
            personal_contacts.append(contact)
        
        # Display contact info
        age_label = "🆕 NEW" if is_new else "🗂️ OLD"
        email_type = "🏫 SYSTEM" if is_system else "👤 PERSONAL"
        
        print(f"Contact {i}: {age_label} {email_type}")
        print(f"   📧 Email: {email}")
        print(f"   🆔 Contact ID: {contact['id']}")
        print(f"   👤 Name: {name}")
        print(f"   📅 Created: {create_date_str}")
        print(f"   ⏰ Age: {(datetime.now(timezone.utc) - create_date).days} days old")
        
        # Show existing additional emails
        additional_emails = props.get("hs_additional_emails", "")
        if additional_emails:
            print(f"   📧 Additional Emails: {additional_emails}")
        
        # Show existing duplicate notes (updated property name)
        existing_notes = props.get("duplicate_contact_notes", "")
        if existing_notes:
            print(f"   📝 Existing Notes: {existing_notes[:100]}...")
        
        print()
    
    # Step 4: Scenario Analysis
    print(f"📊 SCENARIO ANALYSIS:")
    print("-" * 50)
    print(f"🆕 New contacts (< {NEW_CONTACT_HOURS}h): {len(new_contacts)}")
    print(f"🗂️ Old contacts (> {NEW_CONTACT_HOURS}h): {len(old_contacts)}")
    print(f"🏫 System email contacts: {len(system_contacts)}")
    print(f"👤 Personal email contacts: {len(personal_contacts)}")
    
    # Determine processing scenario
    if len(contacts) < 2:
        print("✅ NO DUPLICATES: Only one contact found, no processing needed")
        return
    
    has_new_contacts = len(new_contacts) > 0
    has_system_contact = len(system_contacts) > 0
    
    print(f"\n🎯 PROCESSING SCENARIO:")
    if has_new_contacts and has_system_contact:
        print("   📋 NEW CONTACT SCENARIO: Will merge new personal emails into existing system contact")
    elif not has_new_contacts and has_system_contact:
        if len(personal_contacts) == 1:
            print("   📋 OLD CONTACT SCENARIO (2 contacts): Will add duplicate remark and merge")
        elif len(personal_contacts) > 1:
            print(f"   📋 OLD CONTACT SCENARIO ({len(contacts)} contacts): Will merge multiple personal emails, prioritize latest")
        else:
            print("   📋 NO PROCESSING NEEDED: Only system contact found")
    else:
        print("   ⚠️ COMPLEX SCENARIO: No system contact found or multiple system contacts")
    
    # Step 5: Show what will happen
    print(f"\n🔄 PLANNED ACTIONS:")
    print("-" * 40)
    
    if has_system_contact:
        system_contact = system_contacts[0]
        system_email = system_contact["properties"].get("email", "")
        print(f"✅ Primary Contact: {system_contact['id']} ({system_email})")
        
        if personal_contacts:
            print(f"📧 Personal emails to preserve:")
            for contact in personal_contacts:
                personal_email = contact["properties"].get("email", "")
                print(f"   - {personal_email} (Contact: {contact['id']})")
            
            print(f"🔄 Contacts to merge: {len(personal_contacts)}")
            print(f"📝 Notes to add: Duplicate merge tracking")
            print(f"📧 Additional emails to update: Yes")
    else:
        print("⚠️ Cannot proceed - no system contact found")
        return
    
    # Step 6: Ask for confirmation
    print(f"\n⚠️ CONFIRMATION REQUIRED")
    print("=" * 40)
    print("This will:")
    print("✅ Keep system email as primary")
    print("✅ Preserve all personal emails in additional emails field")
    print("✅ Add detailed notes in 'duplicate_contact_notes' property")
    print("✅ Merge duplicate contacts")
    print("❌ This action cannot be undone!")
    
    confirmation = input("\n🤔 Type 'PROCEED' to continue, anything else to cancel: ").strip().upper()
    
    if confirmation != 'PROCEED':
        print("❌ Processing cancelled by user")
        print("💡 No changes were made to your contacts")
        return
    
    # Step 7: Execute processing
    print(f"\n🚀 EXECUTING PROCESSING...")
    print("=" * 50)
    
    # Determine processing type and execute
    if has_new_contacts:
        result = process_new_contact_duplicates(normalized_phone, contacts)
    else:
        result = process_old_contact_duplicates(normalized_phone, contacts)
    
    # Step 8: Display detailed results
    print(f"\n📊 PROCESSING RESULTS")
    print("=" * 50)
    print(f"Status: {result['status']}")
    
    if result['status'] == 'success':
        print(f"✅ Processing completed successfully!")
        print(f"🔄 Contacts merged: {result.get('merged_count', 0)}")
        
        if result.get('system_contact'):
            print(f"🎯 Final primary contact: {result['system_contact']}")
        
        if result.get('processed_emails'):
            print(f"📧 Processed emails: {', '.join(result['processed_emails'])}")
        
        if result.get('scenario'):
            print(f"📋 Scenario handled: {result['scenario']}")
        
        print(f"\n💡 WHAT HAPPENED:")
        print(f"   ✅ System email remains primary")
        print(f"   ✅ Personal emails preserved in additional emails")
        print(f"   ✅ Detailed notes added to 'duplicate_contact_notes' property")
        print(f"   ✅ Duplicate contacts merged and cleaned up")
        
    else:
        print(f"❌ Processing failed: {result['status']}")
        if result.get('error'):
            print(f"Error details: {result['error']}")
    
    print(f"\n🎉 Test processing complete!")

# ========== Comprehensive Processor ==========

def get_all_contacts_recent(hours_back=48):
    """Get all contacts from last N hours"""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    all_contacts = []
    after = None
    
    print(f"🔍 Fetching contacts from last {hours_back} hours...")
    
    while True:
        payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": cutoff_time.isoformat()
                }]
            }],
            "properties": [
                "email", "phone", "hs_additional_emails", "createdate", 
                "firstname", "lastname", "company", "lifecyclestage",
                "duplicate_contact_notes"  # Updated property name
            ],
            "limit": 100,
            "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}]
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
                
            time.sleep(0.1)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching contacts: {e}")
            break
    
    print(f"✅ Found {len(all_contacts)} contacts")
    return all_contacts

def comprehensive_duplicate_processor():
    """Process all recent contacts for duplicates"""
    
    print("🚀 COMPREHENSIVE DUPLICATE CONTACT PROCESSOR")
    print("🎯 Handles both new and old contacts with smart merge logic")
    print("📝 Notes stored in 'duplicate_contact_notes' property")
    print("=" * 80)
    
    # Get contacts from last 48 hours (to catch both new and some old)
    all_contacts = get_all_contacts_recent(hours_back=48)
    
    if not all_contacts:
        print("📭 No contacts found to process")
        return
    
    # Group contacts by phone number
    phone_groups = defaultdict(list)
    
    for contact in all_contacts:
        phone = normalize_phone(contact["properties"].get("phone"))
        if phone:
            phone_groups[phone].append(contact)
    
    # Find phone numbers with potential duplicates
    duplicate_phone_groups = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 1}
    
    print(f"\n📊 ANALYSIS:")
    print(f"📱 Total unique phone numbers: {len(phone_groups)}")
    print(f"🔄 Phone numbers with duplicates: {len(duplicate_phone_groups)}")
    
    if not duplicate_phone_groups:
        print("✨ No duplicates found!")
        return
    
    # Process results tracking
    results = {
        "processed_groups": 0,
        "new_contact_groups": 0,
        "old_contact_groups": 0,
        "successful_merges": 0,
        "failed_merges": 0,
        "total_contacts_merged": 0,
        "manual_review_needed": []
    }
    
    # Process each phone group
    for phone, duplicate_contacts in duplicate_phone_groups.items():
        print(f"\n" + "="*80)
        
        results["processed_groups"] += 1
        
        # Determine if this group has new contacts
        has_new_contacts = any(is_new_contact(c) for c in duplicate_contacts)
        
        if has_new_contacts:
            # Process as new contact group
            results["new_contact_groups"] += 1
            result = process_new_contact_duplicates(phone, duplicate_contacts)
        else:
            # Process as old contact group
            results["old_contact_groups"] += 1
            result = process_old_contact_duplicates(phone, duplicate_contacts)
        
        # Track results
        if result["status"] == "success":
            results["successful_merges"] += 1
            results["total_contacts_merged"] += result.get("merged_count", 0)
        elif result["status"] in ["merge_failed", "failed"]:
            results["failed_merges"] += 1
        elif result["status"] in ["no_system_contact", "multiple_system_contacts"]:
            results["manual_review_needed"].append({
                "phone": phone,
                "reason": result["status"],
                "contact_ids": [c["id"] for c in duplicate_contacts]
            })
        
        # Rate limiting between groups
        time.sleep(3)
    
    # Final comprehensive summary
    print(f"\n" + "="*80)
    print(f"📊 COMPREHENSIVE PROCESSING SUMMARY")
    print("="*80)
    print(f"📱 Phone Groups Processed: {results['processed_groups']}")
    print(f"🆕 New Contact Groups: {results['new_contact_groups']}")
    print(f"🗂️ Old Contact Groups: {results['old_contact_groups']}")
    print(f"✅ Successful Merge Groups: {results['successful_merges']}")
    print(f"❌ Failed Merge Groups: {results['failed_merges']}")
    print(f"🔄 Total Contacts Merged: {results['total_contacts_merged']}")
    print(f"⚠️ Manual Review Needed: {len(results['manual_review_needed'])}")
    
    if results['manual_review_needed']:
        print(f"\n📋 MANUAL REVIEW REQUIRED:")
        print("-" * 50)
        for item in results['manual_review_needed']:
            print(f"📱 Phone: {item['phone']}")
            print(f"   Reason: {item['reason']}")
            print(f"   Contact IDs: {item['contact_ids']}")
    
    if results['processed_groups'] > 0:
        success_rate = (results['successful_merges'] / results['processed_groups']) * 100
        print(f"\n🎯 Overall Success Rate: {success_rate:.1f}%")
    
    print(f"\n🎉 Comprehensive Processing Complete!")
    print(f"💡 All notes stored in 'duplicate_contact_notes' custom property")

# ========== Main Function ==========

def main():
    """Main execution function with options"""
    print("🚀 NEETPREP COMPREHENSIVE DUPLICATE RESOLVER")
    print("📝 Custom Property: duplicate_contact_notes")
    print("🎯 System emails priority with smart personal email preservation")
    print("=" * 80)
    print("OPTIONS:")
    print("1. Process all recent contacts (comprehensive)")
    print("2. Test specific phone number (recommended for testing)")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    try:
        if choice == "1":
            print("⚠️ This will process ALL recent contacts!")
            confirm = input("Type 'YES' to proceed: ").strip().upper()
            if confirm == 'YES':
                comprehensive_duplicate_processor()
            else:
                print("❌ Comprehensive processing cancelled")
                
        elif choice == "2":
            phone = input("Enter phone number to test: ").strip()
            test_specific_phone_number(phone)
            
        elif choice == "3":
            print("👋 Goodbye!")
            return
        else:
            print("❌ Invalid choice")
            
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
