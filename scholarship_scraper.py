import os
import time
import requests
import io
from datetime import datetime
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dotenv import load_dotenv
from supabase import create_client, Client
from fake_useragent import UserAgent
import dateparser # The Date Reader

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ua = UserAgent()

def extract_text_from_pdf(pdf_bytes):
    try:
        text = ""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for i, page in enumerate(reader.pages):
            if i > 5: break 
            text += page.extract_text() + "\n"
        return text
    except Exception:
        return None

def find_deadline(text):
    """
    Scans text for dates near keywords like 'Deadline'
    """
    if not text: return None
    
    # Keywords to look for
    keywords = ["deadline", "closing date", "due date", "closes on", "applications close"]
    text_lower = text.lower()
    
    for word in keywords:
        if word in text_lower:
            try:
                # Find the keyword position
                start = text_lower.find(word)
                # Grab a snippet of text AFTER the keyword (e.g., "Deadline: Jan 5")
                # We grab 50 chars to be safe
                snippet = text[start:start+60]
                
                # Ask dateparser to find a date in that mess
                found_date = dateparser.parse(
                    snippet, 
                    settings={'PREFER_DATES_FROM': 'future', 'DATE_ORDER': 'DMY'}
                )
                
                if found_date:
                    return found_date
            except:
                continue
    return None

def get_page_content(url):
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=15)
        
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'pdf' in content_type or url.endswith('.pdf'):
            print("      📄 Detected PDF...")
            return extract_text_from_pdf(response.content)
        else:
            soup = BeautifulSoup(response.content, 'html.parser')
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
            return ' '.join(soup.get_text(separator=' ').split())

    except Exception:
        return None

def main():
    print("🕷️  Scraper (with Expiration Guard) Initialized...")
    
    # 1. Fetch unread items (Limit 50 to clear backlog faster)
    response = supabase.table("scholarships") \
        .select("id, url, title") \
        .is_("full_text", "null") \
        .limit(50) \
        .execute()
        
    tasks = response.data
    
    if not tasks:
        print("✅ No unread scholarships found.")
        return

    print(f"📚 Found {len(tasks)} unread scholarships...")

    for item in tasks:
        print(f"\n📖 Reading: {item['title'][:40]}...")
        content = get_page_content(item['url'])
        
        if content:
            # --- EXPIRATION CHECK ---
            deadline = find_deadline(content)
            is_active = True
            deadline_str = None
            
            if deadline:
                deadline_str = deadline.strftime("%Y-%m-%d")
                # If deadline is in the past (and not today), it's expired
                if deadline < datetime.now():
                    print(f"      ❌ EXPIRED! (Deadline was {deadline_str})")
                    is_active = False 
                else:
                    print(f"      ✅ Active! (Deadline: {deadline_str})")
            else:
                print("      ⚠️  No specific deadline found (Keeping as Active).")

            # Update Database
            try:
                # Truncate to save space
                truncated_content = content[:15000]
                
                supabase.table("scholarships") \
                    .update({
                        "full_text": truncated_content, 
                        "is_processed": True,
                        "is_active": is_active,
                        "deadline": deadline_str
                    }) \
                    .eq("id", item['id']) \
                    .execute()
            except Exception as e:
                print(f"   ⚠️ DB Error: {e}")
        else:
            # If we can't read it, mark processed so we don't retry forever
            print("      ⚠️  Failed to read.")
            supabase.table("scholarships").update({"is_processed": True}).eq("id", item['id']).execute()
            
        time.sleep(1)

if __name__ == "__main__":
    main()
