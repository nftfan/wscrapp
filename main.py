import requests
import re
import json
from urllib.parse import urlparse
import time
import os

EXCLUDED_DOMAINS = {
    "sentry.wixpress.com",
    "sentry-next.wixpress.com"
}

# Firebase Realtime Database endpoint for emails collection
FIREBASE_DB_URL = "https://trackingclients-default-rtdb.firebaseio.com/emails.json"
EMAILS_FILE = "emails.txt"

def load_emails_from_file(filename=EMAILS_FILE):
    """Load emails from a local file into a set."""
    if not os.path.exists(filename):
        return set()
    with open(filename, "r") as f:
        emails = {line.strip() for line in f if line.strip()}
    return emails

def append_emails_to_file(emails, filename=EMAILS_FILE):
    """Append new emails to the local file."""
    with open(filename, "a") as f:
        for email in emails:
            f.write(email + "\n")

def save_email_to_firebase(email):
    """
    Save a single email address to Firebase Realtime Database under 'emails'
    """
    data = {"email": email}
    try:
        response = requests.post(FIREBASE_DB_URL, data=json.dumps(data))
        if response.ok:
            print(f"Saved to Firebase: {email}")
            return True
        else:
            print(f"Failed to save {email} to Firebase: {response.text}")
            return False
    except Exception as e:
        print(f"Error saving to Firebase: {e}")
        return False

def clean_url(url):
    url = url.replace("\\", "")  # Remove backslashes
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
    return url

def extract_emails_from_url(url):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    url = clean_url(url)
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        print(f"Fetching webpage: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        source_code = response.text
        print(f"Successfully fetched {len(source_code)} characters of source code")
        email_matches = re.findall(email_pattern, source_code)
        unique_emails = list(set(email_matches))
        print(f"Found {len(unique_emails)} unique email addresses from {url}")
        return unique_emails
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred with {url}: {e}")
        return []

def is_probably_system_email(email):
    domain = email.split('@')[-1]
    if domain in EXCLUDED_DOMAINS:
        return True
    local = email.split('@')[0]
    # Exclude long hex (16+ chars), all digits, or mostly non-alpha
    if re.fullmatch(r"[0-9a-f]{16,}", local, re.IGNORECASE):
        return True
    if re.fullmatch(r"\d{8,}", local):
        return True
    return False

def is_valid_email(email):
    # Exclude image files and other non-email "@" strings
    image_exts = ('.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp', '.bmp', '.tiff', '.ico')
    if email.lower().endswith(image_exts):
        return False
    valid_pattern = re.compile(
        r"^(?!\.)[a-zA-Z0-9._%+-]+@(?!-)(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
    )
    if not valid_pattern.match(email):
        return False
    if '..' in email:
        return False
    if is_probably_system_email(email):
        return False
    return True

def filter_valid_emails_and_save(email_list):
    """
    Filter a list of emails, returning only refined valid ones.
    Also save each valid email to Firebase automatically, and to a local file.
    Do not save to Firebase if email is already present in the local file.
    """
    valid_emails = []
    emails_already_saved = load_emails_from_file()
    new_emails_to_file = []
    for email in set(email_list):
        if is_valid_email(email):
            valid_emails.append(email)
            if email not in emails_already_saved:
                if save_email_to_firebase(email):
                    new_emails_to_file.append(email)
            else:
                print(f"Skipped saving {email} to Firebase: already in file")
    if new_emails_to_file:
        append_emails_to_file(new_emails_to_file)
    return sorted(valid_emails)

def extract_emails_from_urls(urls):
    all_emails = []
    print(f"Processing {len(urls)} URLs...")
    print("=" * 60)
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processing: {url}")
        emails = extract_emails_from_url(url)
        all_emails.extend(emails)
        if emails:
            print(f"  → Found emails: {emails}")
        else:
            print(f"  → No emails found")
    unique_all_emails = sorted(list(set(all_emails)))
    print(f"\n" + "=" * 60)
    print(f"SUMMARY: Found {len(unique_all_emails)} unique email addresses across all URLs")
    print("=" * 60)
    # Filter and save automatically
    valid_emails = filter_valid_emails_and_save(unique_all_emails)
    return unique_all_emails, valid_emails

def main():
    print("Starting 24/7 Email Address Extractor")
    print("=" * 50)
    
    while True:
        print("\n--- Starting new scan cycle ---")
        
        # Read URLs from file instead of input()
        if not os.path.exists("urls.txt"):
            print("Error: urls.txt file not found! Retrying in 1 hour...")
            time.sleep(3600)
            continue
            
        with open("urls.txt", "r") as f:
            urls = [clean_url(line.strip()) for line in f if line.strip()]
            
        if not urls:
            print("No URLs found in urls.txt. Please add some. Retrying in 1 hour...")
            time.sleep(3600)
            continue
            
        print(f"\nLoaded {len(urls)} URLs from urls.txt.")
        
        # Run the extraction
        all_emails, valid_emails = extract_emails_from_urls(urls)
        
        print(f"\nCycle complete. Found {len(valid_emails)} valid emails.")
        print("Sleeping for 24 hours before scanning again...")
        time.sleep(86400) # Sleep for 24 hours

if __name__ == "__main__":
    main()
