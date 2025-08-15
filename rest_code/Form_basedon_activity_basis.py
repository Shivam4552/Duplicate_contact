import os
import requests
import time
import csv
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
TARGET_DATE = datetime(2025, 8, 12, tzinfo=IST)  # Now using IST timezone

# ========== Helper Functions ==========

def fetch_contacts_by_date(start_date, end_date, limit=15000):
    """Fetch contacts with last activity between start_date and end_date with comprehensive form-related properties"""
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
                        "propertyName": "lastmodifieddate",  # Changed from createdate
                        "operator": "GTE",
                        "value": start_date.isoformat()
                    },
                    {
                        "propertyName": "lastmodifieddate",  # Changed from createdate
                        "operator": "LT",
                        "value": end_date.isoformat()
                    }
                ]
            }],
            "properties": [
                # Basic contact info
                "email", "phone", "hs_additional_emails", "createdate", 
                "firstname", "lastname", "lastmodifieddate",  # Added last modified date
                
                # Form submission related properties
                "hs_analytics_first_url", "hs_analytics_source", 
                "hs_analytics_source_data_1", "hs_analytics_source_data_2",
                "recent_conversion_event_name", "first_conversion_event_name",
                "hs_analytics_first_referrer", "hs_analytics_last_referrer",
                "hs_form_submissions", "hs_analytics_num_page_views",
                
                # Additional tracking properties
                "hs_analytics_first_touch_converting_campaign",
                "hs_analytics_last_touch_converting_campaign", 
                "hs_latest_source", "hs_latest_source_data_1", "hs_latest_source_data_2",
                "hs_analytics_revenue", "hs_analytics_source_data_3",
                "hs_analytics_first_visit_timestamp", "hs_analytics_last_visit_timestamp",
                
                # Lead source properties
                "hs_lead_status", "lifecyclestage", "hs_analytics_average_page_views",
                "hs_analytics_first_timestamp", "hs_analytics_last_timestamp"
            ],
            "limit": 100,
            "sorts": ["lastmodifieddate"]  # Changed from createdate
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

def get_comprehensive_form_data(contact_id):
    """Get comprehensive form submission data for a contact"""
    form_data = {
        'form_submissions': [],
        'form_submission_details': []
    }
    
    # Get form submissions via associations
    try:
        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/form_submission"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        for result in data.get("results", []):
            form_id = result.get("id")
            if form_id:
                form_data['form_submissions'].append(form_id)
                
                # Try to get form submission details
                try:
                    form_detail_url = f"https://api.hubapi.com/form-integrations/v1/submissions/forms/{form_id}"
                    form_response = requests.get(form_detail_url, headers=HEADERS, timeout=10)
                    if form_response.status_code == 200:
                        form_details = form_response.json()
                        form_data['form_submission_details'].append({
                            'form_id': form_id,
                            'details': form_details
                        })
                except:
                    pass
                    
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Could not fetch form submissions for contact {contact_id}: {e}")
    
    # Alternative: Try to get form submissions from timeline/activities
    try:
        timeline_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
        timeline_params = {
            "properties": "hs_form_submissions,recent_conversion_event_name,first_conversion_event_name"
        }
        response = requests.get(timeline_url, headers=HEADERS, params=timeline_params, timeout=10)
        response.raise_for_status()
        
        timeline_data = response.json()
        props = timeline_data.get("properties", {})
        
        # Extract form submissions from properties
        if props.get("hs_form_submissions"):
            form_data['property_form_submissions'] = props["hs_form_submissions"]
            
    except:
        pass
    
    return form_data

def extract_all_form_sources(contact_props, contact_id):
    """Extract all possible form sources from contact properties and API calls"""
    form_sources = []
    
    # Helper function to safely get string values
    def safe_get_string(key):
        value = contact_props.get(key)
        return str(value) if value is not None else ""
    
    # Get comprehensive form data via API
    form_data = get_comprehensive_form_data(contact_id)
    
    # Extract form IDs from direct form submissions
    if form_data['form_submissions']:
        for form_id in form_data['form_submissions']:
            form_sources.append(f"Form Submission: {form_id}")
    
    # Extract from form submission details
    for detail in form_data.get('form_submission_details', []):
        form_id = detail['form_id']
        form_sources.append(f"Form Detail: {form_id}")
    
    # Extract from property-based form submissions
    if form_data.get('property_form_submissions'):
        form_sources.append(f"Property Form: {form_data['property_form_submissions']}")
    
    # Check all URL-based properties for form references
    url_properties = [
        "hs_analytics_first_url", "hs_analytics_first_referrer", 
        "hs_analytics_last_referrer", "hs_analytics_source_data_1",
        "hs_analytics_source_data_2", "hs_analytics_source_data_3",
        "hs_latest_source_data_1", "hs_latest_source_data_2"
    ]
    
    for prop in url_properties:
        value = safe_get_string(prop)
        if value and ("hsforms.com" in value or "form" in value.lower()):
            # Try to extract form ID from URL
            if "hsforms.com" in value:
                # Extract form ID from HubSpot form URL
                if "/1" in value:
                    try:
                        parts = value.split("/1")[1].split("?")[0].split("/")[0]
                        form_sources.append(f"URL Form ({prop}): {parts}")
                    except:
                        form_sources.append(f"URL Form ({prop}): {value}")
                else:
                    form_sources.append(f"Form URL ({prop}): {value}")
            else:
                form_sources.append(f"Form Reference ({prop}): {value}")
    
    # Check conversion events
    conversion_properties = ["recent_conversion_event_name", "first_conversion_event_name"]
    for prop in conversion_properties:
        value = safe_get_string(prop)
        if value and "form" in value.lower():
            form_sources.append(f"Conversion Event ({prop}): {value}")
    
    # Check source properties
    source_properties = [
        "hs_analytics_source", "hs_latest_source",
        "hs_analytics_first_touch_converting_campaign",
        "hs_analytics_last_touch_converting_campaign"
    ]
    
    for prop in source_properties:
        value = safe_get_string(prop)
        if value and ("form" in value.lower() or "hsforms" in value.lower()):
            form_sources.append(f"Source ({prop}): {value}")
    
    # Remove duplicates while preserving order
    unique_sources = []
    seen = set()
    for source in form_sources:
        if source not in seen:
            unique_sources.append(source)
            seen.add(source)
    
    return unique_sources if unique_sources else ["No form data found"]

def normalize_phone(phone):
    """Normalize phone number by removing country codes and spaces"""
    if not phone:
        return None
    phone_str = str(phone).replace("+91", "").replace(" ", "").replace("-", "").strip()
    return phone_str if phone_str.isdigit() and len(phone_str) >= 10 else None

def export_duplicates_to_csv(email_duplicates, phone_duplicates, target_date):
    """Export duplicate contacts to CSV with comprehensive form information"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"duplicate_contacts_lastactivity_{target_date.strftime('%Y%m%d')}_{timestamp}.csv"  # Updated filename
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'Duplicate_Type', 'Duplicate_Value', 'Contact_ID', 'First_Name', 
            'Last_Name', 'Email', 'Phone', 'Create_Date', 'Last_Modified_Date',  # Added Last_Modified_Date
            'All_Form_Sources', 'First_URL', 'Source_Data_1', 'Source_Data_2', 
            'Recent_Conversion', 'First_Conversion', 'Analytics_Source', 'Latest_Source'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write email duplicates
        for email, contacts in email_duplicates.items():
            for contact in contacts:
                writer.writerow({
                    'Duplicate_Type': 'Email',
                    'Duplicate_Value': email,
                    'Contact_ID': contact['id'],
                    'First_Name': contact['firstname'],
                    'Last_Name': contact['lastname'],
                    'Email': contact['email'],
                    'Phone': contact['phone'],
                    'Create_Date': contact['createdate'],
                    'Last_Modified_Date': contact['lastmodifieddate'],  # Added this
                    'All_Form_Sources': "; ".join(contact['form_sources']),
                    'First_URL': contact.get('first_url', ''),
                    'Source_Data_1': contact.get('source_data_1', ''),
                    'Source_Data_2': contact.get('source_data_2', ''),
                    'Recent_Conversion': contact.get('recent_conversion', ''),
                    'First_Conversion': contact.get('first_conversion', ''),
                    'Analytics_Source': contact.get('analytics_source', ''),
                    'Latest_Source': contact.get('latest_source', '')
                })
        
        # Write phone duplicates
        for phone, contacts in phone_duplicates.items():
            for contact in contacts:
                writer.writerow({
                    'Duplicate_Type': 'Phone',
                    'Duplicate_Value': phone,
                    'Contact_ID': contact['id'],
                    'First_Name': contact['firstname'],
                    'Last_Name': contact['lastname'],
                    'Email': contact['email'],
                    'Phone': contact['phone'],
                    'Create_Date': contact['createdate'],
                    'Last_Modified_Date': contact['lastmodifieddate'],  # Added this
                    'All_Form_Sources': "; ".join(contact['form_sources']),
                    'First_URL': contact.get('first_url', ''),
                    'Source_Data_1': contact.get('source_data_1', ''),
                    'Source_Data_2': contact.get('source_data_2', ''),
                    'Recent_Conversion': contact.get('recent_conversion', ''),
                    'First_Conversion': contact.get('first_conversion', ''),
                    'Analytics_Source': contact.get('analytics_source', ''),
                    'Latest_Source': contact.get('latest_source', '')
                })
    
    print(f"📄 Comprehensive duplicate analysis exported to: {filename}")
    return filename

def find_duplicates_for_specific_date(target_date):
    """Find all duplicate contacts with last activity on specified date and comprehensively analyze their form sources"""
    # Set start time to beginning of the day (00:00:00)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Set end time to beginning of next day (this will exclude the next day)
    end_of_day = start_of_day + timedelta(days=1)
    
    print(f"🔍 Exact search range (LAST ACTIVITY DATE):")  # Updated description
    print(f"   Start: {start_of_day.isoformat()}")
    print(f"   End:   {end_of_day.isoformat()}")
    
    contacts = fetch_contacts_by_date(start_of_day, end_of_day)
    
    if not contacts:
        print(f"📭 No contacts found with last activity on {target_date.strftime('%Y-%m-%d')}.")  # Updated message
        return None, None
    
    print(f"📊 Found {len(contacts)} contacts with last activity on {target_date.strftime('%Y-%m-%d')} (from 00:00 to 23:59 IST).")  # Updated message
    
    # First pass: Find duplicates
    print("🔍 Step 1: Identifying duplicate contacts...")
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
        lastmodified = props.get("lastmodifieddate")  # Added this
        
        contact_info = {
            "id": contact_id,
            "email": email,
            "phone": phone,
            "firstname": firstname,
            "lastname": lastname,
            "createdate": created,
            "lastmodifieddate": lastmodified,  # Added this
            "properties": props  # Store all properties for later analysis
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
    
    # Collect all duplicate contacts for form analysis
    duplicate_contacts = []
    duplicate_contact_ids = set()
    
    for contacts in email_duplicates.values():
        for contact in contacts:
            if contact['id'] not in duplicate_contact_ids:
                duplicate_contacts.append(contact)
                duplicate_contact_ids.add(contact['id'])
    
    for contacts in phone_duplicates.values():
        for contact in contacts:
            if contact['id'] not in duplicate_contact_ids:
                duplicate_contacts.append(contact)
                duplicate_contact_ids.add(contact['id'])
    
    print(f"✅ Found {len(duplicate_contact_ids)} unique duplicate contacts")
    
    # Second pass: Comprehensive form analysis for duplicates only
    print("📋 Step 2: Comprehensive form analysis for duplicate contacts...")
    
    for i, contact in enumerate(duplicate_contacts, 1):
        print(f"   Analyzing contact {i}/{len(duplicate_contacts)}: {contact['id']}")
        
        # Extract all form sources
        form_sources = extract_all_form_sources(contact['properties'], contact['id'])
        contact['form_sources'] = form_sources
        
        # Store additional fields for CSV
        contact['first_url'] = contact['properties'].get("hs_analytics_first_url", "")
        contact['source_data_1'] = contact['properties'].get("hs_analytics_source_data_1", "")
        contact['source_data_2'] = contact['properties'].get("hs_analytics_source_data_2", "")
        contact['recent_conversion'] = contact['properties'].get("recent_conversion_event_name", "")
        contact['first_conversion'] = contact['properties'].get("first_conversion_event_name", "")
        contact['analytics_source'] = contact['properties'].get("hs_analytics_source", "")
        contact['latest_source'] = contact['properties'].get("hs_latest_source", "")
        
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(duplicate_contacts)} contacts analyzed...")
    
    # Update the duplicate dictionaries with form information
    for email, contacts in email_duplicates.items():
        for contact in contacts:
            # Find the corresponding contact with form data
            for dup_contact in duplicate_contacts:
                if dup_contact['id'] == contact['id']:
                    contact.update(dup_contact)
                    break
    
    for phone, contacts in phone_duplicates.items():
        for contact in contacts:
            # Find the corresponding contact with form data
            for dup_contact in duplicate_contacts:
                if dup_contact['id'] == contact['id']:
                    contact.update(dup_contact)
                    break
    
    # Display results
    print("\n" + "="*80)
    print(f"📧 EMAIL DUPLICATES WITH LAST ACTIVITY ON {target_date.strftime('%Y-%m-%d')}:")  # Updated title
    print("="*80)
    
    if email_duplicates:
        for email, duplicate_contacts_list in email_duplicates.items():
            print(f"\n🔄 Email: {email}")
            print("-" * 70)
            for i, contact in enumerate(duplicate_contacts_list, 1):
                print(f"  {i}. ID: {contact['id']}")
                print(f"     Name: {contact['firstname']} {contact['lastname']}")
                print(f"     Phone: {contact['phone']}")
                print(f"     Created: {contact['createdate']}")
                print(f"     Last Modified: {contact['lastmodifieddate']}")  # Added this
                print(f"     📝 Form Sources:")
                for source in contact.get('form_sources', ['No form data found']):
                    print(f"        • {source}")
    else:
        print("✅ No email duplicates found.")
    
    print("\n" + "="*80)
    print(f"📱 PHONE DUPLICATES WITH LAST ACTIVITY ON {target_date.strftime('%Y-%m-%d')}:")  # Updated title
    print("="*80)
    
    if phone_duplicates:
        for phone, duplicate_contacts_list in phone_duplicates.items():
            print(f"\n🔄 Phone: {phone}")
            print("-" * 70)
            for i, contact in enumerate(duplicate_contacts_list, 1):
                print(f"  {i}. ID: {contact['id']}")
                print(f"     Name: {contact['firstname']} {contact['lastname']}")
                print(f"     Email: {contact['email']}")
                print(f"     Created: {contact['createdate']}")
                print(f"     Last Modified: {contact['lastmodifieddate']}")  # Added this
                print(f"     📝 Form Sources:")
                for source in contact.get('form_sources', ['No form data found']):
                    print(f"        • {source}")
    else:
        print("✅ No phone duplicates found.")
    
    # Export to CSV if duplicates found
    if email_duplicates or phone_duplicates:
        csv_filename = export_duplicates_to_csv(email_duplicates, phone_duplicates, target_date)
        
        # Form analysis summary
        print("\n" + "="*80)
        print("📊 FORM SOURCE SUMMARY:")
        print("="*80)
        
        all_form_sources = []
        for contact in duplicate_contacts:
            all_form_sources.extend(contact.get('form_sources', []))
        
        form_stats = defaultdict(int)
        for source in all_form_sources:
            form_stats[source] += 1
        
        print("All form sources found in duplicate contacts:")
        for source, count in sorted(form_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  📝 {source}: {count} occurrences")
    
    # Summary
    total_email_duplicates = sum(len(contacts) for contacts in email_duplicates.values())
    total_phone_duplicates = sum(len(contacts) for contacts in phone_duplicates.values())
    
    print("\n" + "="*80)
    print("📈 FINAL SUMMARY:")
    print("="*80)
    print(f"📧 Email duplicate groups: {len(email_duplicates)}")
    print(f"📧 Total contacts with duplicate emails: {total_email_duplicates}")
    print(f"📱 Phone duplicate groups: {len(phone_duplicates)}")
    print(f"📱 Total contacts with duplicate phones: {total_phone_duplicates}")
    print(f"🔍 Total unique duplicate contacts analyzed: {len(duplicate_contact_ids)}")
    
    return email_duplicates, phone_duplicates

# ========== Main Logic ==========

def main():
    print("🚀 Starting Comprehensive Duplicate Contact & Form Analysis (LAST ACTIVITY BASIS)...")  # Updated title
    print(f"📅 Target date: {TARGET_DATE.strftime('%Y-%m-%d %Z')} (searching contacts with LAST ACTIVITY from 00:00 to 23:59 IST)")  # Updated description
    print("🔍 This will:")
    print("   1. Find contacts with LAST ACTIVITY on target date")  # Updated
    print("   2. Identify duplicate contacts (email & phone) from that set")  # Updated
    print("   3. Comprehensively analyze form sources for duplicates only")
    print("   4. Export detailed results to CSV")
    
    # Find duplicates for the specified date based on last activity
    email_duplicates, phone_duplicates = find_duplicates_for_specific_date(TARGET_DATE)
    
    if not email_duplicates and not phone_duplicates:
        print("✅ No duplicates found among contacts with last activity on the specified date!")  # Updated message
    else:
        print("🎯 Comprehensive duplicate and form analysis complete!")
        print("📄 Check the generated CSV file for detailed results with all form submission data.")

if __name__ == "__main__":
    main()
