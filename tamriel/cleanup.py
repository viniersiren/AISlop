import os
import shutil
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import time

# Constants
BASE_URL = "https://en.uesp.net/wiki"
BASE_DIR = Path(__file__).parent / "lore_data"

def get_category_entries(category, letter):
    """Get all entries for a category and letter from UESP wiki."""
    page_url = f"{BASE_URL}/Lore:{category}_{letter}"
    print(f"\nFetching entries for {category} - Letter {letter}")
    print(f"URL: {page_url}")
    
    try:
        response = requests.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all entry links
        content = soup.find('div', {'class': 'mw-parser-output'})
        if not content:
            print("No content found for this letter")
            return []
            
        entries = []
        for link in content.find_all('a'):
            href = link.get('href')
            if href and href.startswith('/wiki/Lore:'):
                entry_name = href.split(':')[-1]
                entries.append(entry_name)
                
        print(f"Found {len(entries)} entries")
        return entries
        
    except Exception as e:
        print(f"Error fetching entries: {str(e)}")
        return []

def get_all_category_entries(category):
    """Get all entries for a category across all letters."""
    all_entries = []
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        entries = get_category_entries(category, letter)
        all_entries.extend(entries)
        time.sleep(1)  # Be nice to the server
    return all_entries

def move_entry(source_path, target_dir):
    """Move an entry to its correct category directory."""
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    target_path = os.path.join(target_dir, os.path.basename(source_path))
    
    # If target already exists, append a number to make it unique
    counter = 1
    while os.path.exists(target_path):
        base_name = os.path.basename(source_path)
        name, ext = os.path.splitext(base_name)
        target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
        counter += 1
    
    shutil.move(source_path, target_path)
    print(f"Moved {source_path} to {target_path}")

def cleanup_directory():
    """Clean up the lore data directories using UESP wiki data."""
    print("Starting cleanup process...")
    
    # Get all entries from UESP wiki for each category
    category_entries = {}
    for category in ["Gods", "Races", "Places"]:
        print(f"\nFetching entries for category: {category}")
        category_entries[category] = get_all_category_entries(category)
    
    # Process each category directory
    for category in ["People", "Gods", "Races", "Places"]:
        category_dir = BASE_DIR / category
        if not os.path.exists(category_dir):
            continue
            
        # Get all entries in the directory
        entries = [d for d in os.listdir(category_dir) 
                  if os.path.isdir(os.path.join(category_dir, d))]
        
        for entry in entries:
            entry_path = os.path.join(category_dir, entry)
            
            # Check if entry belongs in a different category
            for target_category, valid_entries in category_entries.items():
                if category != target_category and entry in valid_entries:
                    print(f"\nFound {entry} in {category}, should be in {target_category}")
                    move_entry(entry_path, BASE_DIR / target_category)
                    break

def main():
    """Main function to run the cleanup."""
    print("Starting lore data cleanup...")
    cleanup_directory()
    print("Cleanup complete!")

if __name__ == "__main__":
    main() 