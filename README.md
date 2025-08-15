# Duplicate Contact Management System

A comprehensive Python-based system for detecting and managing duplicate contacts in HubSpot CRM using various criteria including phone numbers, email addresses, creation dates, and activity patterns.

## 🚀 Features

- **Multiple Detection Methods**: Activity-based, date-based, phone-based, and form-based duplicate detection
- **Secure Configuration**: Environment variable-based API token management
- **Smart Merging**: HubSpot-compliant pairwise merge strategy
- **Comprehensive Analysis**: Detailed reporting and statistics
- **Rate Limiting**: Built-in delays to respect API limits
- **Manual Fallback**: Graceful handling of complex merge scenarios

## 📁 Project Structure

```
├── contactmerge.py                      # Main contact merging script
├── rest_code/                          # Specialized duplicate detection scripts
│   ├── Duplicate_on_activity_basis.py  # Activity-based duplicate detection
│   ├── Duplicate_on_createdate_basis.py # Creation date-based detection
│   ├── Form_basedon_activity_basis.py  # Form submission activity analysis
│   ├── Form_basedon_createdate_basis.py # Form submission date analysis
│   ├── discussed_logic_with_sales_team.py # Sales team validated logic
│   ├── phone_contain@neetprep.py       # Domain-specific phone analysis
│   ├── phonenumbercount.py             # Phone number frequency analysis
│   ├── sameday.py                      # Same-day contact detection
│   ├── singlenew.py                    # Single contact processing
│   ├── specific_phone_number_logic.py  # Target phone number analysis
│   └── three.py                        # Today-only duplicate processing
└── README.md                           # This documentation
```

## 🛠️ Setup

### Prerequisites

- Python 3.7+
- HubSpot Private App Token with Contacts read/write permissions
- Required Python packages: `requests`, `python-dateutil`

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Shivam4552/Duplicate_contact.git
   cd Duplicate_contact
   ```

2. **Install dependencies**:
   ```bash
   pip install requests python-dateutil
   ```

3. **Set up environment variable**:
   ```bash
   export HUBSPOT_TOKEN="your-hubspot-private-app-token-here"
   ```

   Or create a `.env` file (not recommended for production):
   ```
   HUBSPOT_TOKEN=your-hubspot-private-app-token-here
   ```

## 🔧 Configuration

### HubSpot Private App Setup

1. Go to HubSpot Settings → Integrations → Private Apps
2. Create a new private app
3. Grant the following scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.schemas.contacts.read`
4. Copy the generated token and set it as the `HUBSPOT_TOKEN` environment variable

### Script Configuration

Most scripts have configurable date targets at the top:

```python
# Example from contactmerge.py
TARGET_DATE = datetime(2025, 8, 14, tzinfo=timezone.utc)

# Or use dynamic dates
TARGET_DATE = datetime.now(timezone.utc) - timedelta(days=1)  # Yesterday
```

## 📋 Usage

### Main Contact Merger (`contactmerge.py`)

The primary script for comprehensive duplicate contact processing:

```bash
python contactmerge.py
```

**Features**:
- Processes contacts created on a specific date
- Groups duplicates by phone and email
- Uses smart pairwise merge strategy
- Provides detailed processing statistics
- Handles 2-contact, 3-contact, and complex scenarios

### Specialized Scripts

#### Activity-Based Detection
```bash
python rest_code/Duplicate_on_activity_basis.py
```
Detects duplicates based on last activity timestamps using IST timezone.

#### Creation Date Analysis
```bash
python rest_code/Duplicate_on_createdate_basis.py
```
Processes duplicates based on contact creation dates.

#### Form Submission Analysis
```bash
python rest_code/Form_basedon_activity_basis.py
```
Analyzes duplicates from form submissions and exports to CSV.

#### Sales Team Logic
```bash
python rest_code/discussed_logic_with_sales_team.py
```
Implements duplicate detection logic validated with the sales team, including lifecycle stage prioritization.

#### Phone Number Analysis
```bash
python rest_code/phonenumbercount.py
```
Analyzes phone number frequency and patterns.

#### Same-Day Processing
```bash
python rest_code/sameday.py
```
Processes contacts created on the same day with enhanced duplicate detection.

#### Target Phone Analysis
```bash
python rest_code/specific_phone_number_logic.py
```
Analyzes duplicates for a specific phone number (useful for testing).

## 🔍 Key Features Explained

### Phone Number Normalization

The system includes robust phone number normalization:
- Removes country codes (+91, 91)
- Handles various formatting (spaces, dashes, brackets)
- Validates Indian mobile numbers (10 digits starting with 6, 7, 8, or 9)

### Email Normalization

- Converts to lowercase
- Trims whitespace
- Handles additional email fields

### Smart Merging Strategy

1. **2 Contacts**: Direct merge (newer → older based on last contact date)
2. **3 Contacts**: Two-step merge strategy
3. **4+ Contacts**: Flags for manual review in HubSpot UI

### Date Handling

- Supports multiple timezones (UTC, IST)
- Flexible date targeting
- Last contact date prioritization from multiple fields

### Rate Limiting

- Built-in delays between API calls
- Batch processing with progress indicators
- Error handling and retry logic

## 📊 Output and Reporting

### Console Output

All scripts provide detailed console output including:
- Progress indicators with emojis
- Contact statistics
- Merge operation results
- Error handling and warnings
- Final summary reports

### CSV Export

Some scripts (like `Form_basedon_activity_basis.py`) export results to CSV:
- Duplicate contact details
- Form submission information
- Merge recommendations

### Example Output

```
🚀 DUPLICATE CONTACT PROCESSOR
📅 Processing Date: 2025-08-14
🎯 HubSpot-compliant pairwise merge strategy
================================================================================

🔍 Fetching contacts created on 2025-08-14...
📊 Fetched 100 contacts so far...
✅ Total contacts created on 2025-08-14: 145

📊 DUPLICATE ANALYSIS:
📱 Phone duplicates found: 8
📧 Email duplicates found: 12

📱 PROCESSING PHONE DUPLICATES:
==================================================
🔄 Processing phone: 9876543210 (2 contacts)
✅ Successfully merged! Final contact: 12345

📊 FINAL PROCESSING SUMMARY:
============================================================
📅 Date Processed: 2025-08-14
📧 Total Contacts: 145
🔄 Total Successful Merges: 15
✅ Phone Merges Successful: 8
✅ Email Merges Successful: 7
🎯 Overall Success Rate: 93.8%
```

## ⚠️ Important Notes

### Security

- **Never commit API tokens** to version control
- Use environment variables for sensitive data
- Regularly rotate API tokens
- Monitor API usage and permissions

### Rate Limits

- HubSpot API has rate limits (100 requests per 10 seconds)
- Scripts include built-in delays
- Monitor your API usage in HubSpot settings

### Data Safety

- **Test on staging environment first**
- Merging is irreversible in HubSpot
- Always backup important data before bulk operations
- Review merge candidates manually for critical contacts

### Complex Scenarios

For 4+ duplicate contacts, the system will:
- Flag them for manual review
- Provide contact IDs for HubSpot UI processing
- Skip automatic merging to prevent data loss

## 🚨 Troubleshooting

### Common Issues

1. **API Token Errors**:
   ```
   Error: 401 Unauthorized
   ```
   - Check `HUBSPOT_TOKEN` environment variable
   - Verify token permissions in HubSpot

2. **Rate Limit Errors**:
   ```
   Error: 429 Too Many Requests
   ```
   - Increase delay between requests
   - Reduce batch sizes

3. **Merge Failures**:
   ```
   Merge failed: Contact not found
   ```
   - Contact may have been deleted
   - Check contact permissions

### Debug Mode

Add debug logging to any script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with proper testing
4. Update documentation
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License. See the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review HubSpot API documentation
3. Create an issue in the GitHub repository

## 📚 Additional Resources

- [HubSpot API Documentation](https://developers.hubspot.com/docs/api/overview)
- [HubSpot Private Apps Guide](https://developers.hubspot.com/docs/api/private-apps)
- [Contact Merge API Reference](https://developers.hubspot.com/docs/api/crm/contacts)

---

**⚡ Quick Start**: Set your `HUBSPOT_TOKEN`, configure the target date in `contactmerge.py`, and run `python contactmerge.py` to begin processing duplicates!