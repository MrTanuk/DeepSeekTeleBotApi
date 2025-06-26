import os
import sys
import logging

# --- Setup ---
# This script should be run from the root of your project directory
# so it can find the 'config' module and the 'cookies.txt' file.

# Suppress verbose logs from libraries unless there's an issue
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

try:
    # Import the initialized supabase client from your main config
    from config import supabase
except ImportError:
    print("\nERROR: Could not import 'config.py'.")
    print("Please make sure you are running this script from your project's root directory.")
    sys.exit(1)
except Exception as e:
    print(f"\nAn unexpected error occurred during import: {e}")
    sys.exit(1)

# --- Configuration ---
# Define the table and row details here for clarity
TABLE_NAME = "cookies"
# This is the column that uniquely identifies the row (like a primary key or unique column)
ID_COLUMN_NAME = "name_media" 
ID_COLUMN_VALUE = "Youtube/Instagram"
# This is the column where the cookie data is stored
COOKIE_DATA_COLUMN = "cookies_data"
COOKIE_FILENAME = "cookies.txt"

def print_header(title):
    """Prints a simple header to the console."""
    print("\n" + "="*50)
    print(f" {title}")
    print("="*50)

def update_cookies():
    """
    Reads a local cookies.txt file and uploads its content to Supabase,
    updating the existing entry.
    """
    print_header("Supabase Cookie Uploader")

    # 1. Check if Supabase client is available
    if not supabase:
        print("ERROR: Supabase client is not configured in 'config.py'.")
        print("Please check your .env file and ensure SUPABASE_URL and SUPABASE_KEY are set.")
        return

    # 2. Check for the local cookie file
    print(f"--> Looking for '{COOKIE_FILENAME}' in the current directory...")
    if not os.path.exists(COOKIE_FILENAME):
        print(f"\nERROR: File not found.")
        print(f"Please place your '{COOKIE_FILENAME}' file in the same directory as this script.")
        return
    
    # 3. Read the cookie file content
    try:
        with open(COOKIE_FILENAME, "r", encoding="utf-8") as file:
            cookie_content = file.read()
        
        if not cookie_content.strip():
            print("\nWARNING: The cookie file appears to be empty. Aborting.")
            return

        print(f"--> Successfully read '{COOKIE_FILENAME}' ({len(cookie_content)} characters).")
    except Exception as e:
        print(f"\nERROR: Failed to read the cookie file: {e}")
        return

    # 4. Confirm before uploading
    print("\nThis action will overwrite the existing cookies in the database.")
    try:
        confirm = input("Are you sure you want to proceed? (y/n): ").lower().strip()
        if confirm != 'y':
            print("\nOperation cancelled by user.")
            return
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return
        
    # 5. Perform the upsert operation
    try:
        print("\n--> Uploading to Supabase...")
        
        # 'upsert' will update the row if it matches the unique ID, or create it if it doesn't.
        # It's generally safer than a simple 'update'.
        response = supabase.table(TABLE_NAME).upsert({
            "id": 1,
            ID_COLUMN_NAME: ID_COLUMN_VALUE,
            COOKIE_DATA_COLUMN: cookie_content
        }).execute()
        
        # Check if the API call was successful. A successful upsert might return
        # data or just a success status code.
        if (response.data or (200 <= response.status_code < 300)):
            print("\nSUCCESS: Cookies have been successfully updated in Supabase!")
        else:
            print(f"\nERROR: Supabase API call failed.")
            print(f"   Status: {response.status_code}")
            print(f"   Details: {response.error or response.data}")

    except Exception as e:
        print(f"\nAn unexpected error occurred while communicating with Supabase:")
        logger.error("Supabase communication error", exc_info=True)
        print(f"   {e}")

if __name__ == "__main__":
    update_cookies()
