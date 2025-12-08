import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client
from fake_useragent import UserAgent

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize a fake browser identity
ua = UserAgent()

def get_page_content(url):
    """
    Visits a URL and returns the text content.
    Returns None if it fails or is a PDF.
    """
    try:
        # 1. Fake a browser visit (Chrome)
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=10)
        
        # 2. Check if it is a PDF (we skip these for now)
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type:
            print("      ⚠️  Skipping PDF (Binary file)")
            return None
            
        # 3. Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 4. Remove junk (scripts, styles, navbars)
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        # 5. Extract text
        text = soup.get_text(separator=' ')
        
        # 6. Clean up whitespace
        clean_text = ' '.join(text.split())
        return clean_text

    except Exception as e:
        print(f"      ❌ Error reading page: {e}")
        return None

def main():
    print("🕷️  Scraper Initialized...")
    
    # 1. Fetch rows that don't have text yet (limit 10 at a time to be safe)
    # We check where 'full_text' is null
    response = supabase.table("scholarships") \
        .select("id, url, title") \
        .is_("full_text", "null") \
        .limit(10) \
        .execute()
        
    tasks = response.data
    
    if not tasks:
        print("✅ All current scholarships have been read!")
        return

    print(f"📚 Found {len(tasks)} unread scholarships. Starting extraction...")

    for item in tasks:
        print(f"\n📖 Reading: {item['title'][:30]}...")
        
        # Extract
        content = get_page_content(item['url'])
        
        if content:
            # Save back to Supabase
            try:
                # We only store the first 10,000 characters to save DB space
                truncated_content = content[:10000] 
                
                supabase.table("scholarships") \
                    .update({"full_text": truncated_content, "is_processed": True}) \
                    .eq("id", item['id']) \
                    .execute()
                    
                print(f"   💾 Saved {len(truncated_content)} characters.")
            except Exception as e:
                print(f"   ⚠️  Database Update Error: {e}")
        else:
            # If we couldn't read it, mark it processed anyway so we don't loop forever
            print("   ⚠️  Marking as processed (skipped/failed).")
            supabase.table("scholarships") \
                .update({"is_processed": True}) \
                .eq("id", item['id']) \
                .execute()
        
        # Be polite to servers
        time.sleep(2)

if __name__ == "__main__":
    main()