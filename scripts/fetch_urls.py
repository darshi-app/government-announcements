import urllib.request
import urllib.error
import json
import re
import time
import os

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "igod_urls.json")

def fetch_batch(start, limit=24):
    url = f"https://igod.gov.in/districts/list_more/{start}/{limit}"
    req = urllib.request.Request(url)
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"HTTP Error fetching batch {start}: {e.code}")
    except Exception as e:
        print(f"Error fetching batch {start}: {e}")
    return None

def extract_links(html_snippet):
    # Regex to find <a href="...">Content</a>
    # The content might contain <span> or other tags, so we use .*? non-greedy match until </a>
    pattern = r'<a\s+[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
    matches = re.findall(pattern, html_snippet, re.DOTALL)
    
    cleaned_links = []
    for url, raw_name in matches:
        # Remove HTML tags from name
        name = re.sub(r'<[^>]+>', '', raw_name).strip()
        cleaned_links.append((url, name))
        
    return cleaned_links

def scrape_igod():
    all_links = {}
    
    # 1. Scraping the Main Page
    print("Fetching main page...")
    req = urllib.request.Request("https://igod.gov.in/districts")
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    try:
        with urllib.request.urlopen(req) as response:
            main_html = response.read().decode('utf-8')
            found = extract_links(main_html)
            print(f"Found {len(found)} links on main page.")
            for url, name in found:
                # Filter out navigation links
                if "/district/" not in url and "nic.in" not in url and ".gov.in" not in url:
                     continue 
                # Filter out "Home", "About", text
                name = name.strip()
                if len(name) < 2 or "Content" in name or "Screen" in name:
                    continue
                
                all_links[name] = url
    except Exception as e:
        print(f"Failed to fetch main page: {e}")

    # 2. Loop the API
    # Start at 0? Or 60? The user said infinite scroll loads usually append.
    # The browser analysis script used `60`. Let's stick with 60 but enable DEBUG print if empty.
    start = 60
    limit = 24
    
    print("Starting API scraping...")
    
    while True:
        print(f"Fetching batch starting at {start}...", end="", flush=True)
        html_snippet = fetch_batch(start, limit)
        
        if not html_snippet:
            print(" No data/Error.")
            break
            
        if not html_snippet.strip():
             print(" Empty response.")
             break

        links = extract_links(html_snippet)
        if not links:
            print(" No links found in snippet.")
            # print(f"DEBUG SNIPPET: {html_snippet[:200]}") # Uncomment if needed
            if start > 7000: # Safety break
                 break
            # If no links found, maybe the offset is wrong or we are done?
            # Typically if we are done, the snippet is empty string.
            # If snippet has content but no links, maybe it's an error message or "No more records"?
            # Let's verify if snippet contains "No records".
            if "No Record" in html_snippet:
                 print(" 'No Record' found.")
                 break
                 
            # If we just don't find links but content exists, maybe regex is failing?
            # Let's break to avoid infinite loop of nothing.
            break
            
        print(f" Found {len(links)} links.")
        for url, name in links:
             all_links[name.strip()] = url
        
        start += limit
        time.sleep(0.5) 
        
    print(f"Total Unique URLs found: {len(all_links)}")
    
    # Save to file
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_links, f, indent=4)
        
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_igod()
