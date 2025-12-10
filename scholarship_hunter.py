import os
import requests
import random
import time
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_search_terms():
    """Fetches active topics from the database"""
    try:
        response = supabase.table("search_terms").select("topic").eq("is_active", True).execute()
        return [row['topic'] for row in response.data]
    except Exception as e:
        print(f"⚠️ Error fetching search terms: {e}")
        return ["civil engineering", "aerospace engineering", "optometry"] # Added Optometry fallback

def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'num': 10,
        'dateRestrict': 'y1'  # <--- THE MAGIC FIX: Only results from the last 1 year
    }
    response = requests.get(url, params=params)
    return response.json()

def save_to_supabase(items, source_query):
    count = 0
    for item in items:
        try:
            data = {
                "title": item.get('title'),
                "url": item.get('link'),
                "content_snippet": item.get('snippet'),
                "source_query": source_query,
                "is_processed": False # Mark as new so the Scraper reads it
            }
            # Insert, ignore if URL already exists
            supabase.table("scholarships").upsert(data, on_conflict="url").execute()
            print(f"   ✅ Saved: {item.get('title')[:40]}..")
            count += 1
        except Exception:
            pass
    return count

def main():
    print("🚀 HunterAI: Initializing Freshness Protocol...")
    
    # 1. Get topics from DB
    topics = get_search_terms()
    
    # If DB is empty, default to your profile interests
    if not topics:
        topics = ["Aerospace Engineering", "Optometry", "Civil Engineering"]
        
    print(f"🎯 Targeting {len(topics)} topics: {topics}")
    
   # 2. Build smart queries (Explicitly asking for 2025/2026)
    dork_templates = [
        'site:.edu "{topic}" scholarship 2025 2026 international',
        'filetype:pdf "application" "{topic}" scholarship 2025',
        '"fully funded" masters "{topic}" uk 2025',
        'site:.ac.uk "{topic}" funding international students 2025',
        
        # 🧬 THE ALPHA EVOLVED SURVIVOR:
        'filetype:pdf intitle:application "{topic}" scholarship guidelines' 
    ]
    
    total_found = 0
    
    # 3. Hunt
    for topic in topics:
        selected_dorks = random.sample(dork_templates, 3) # Increased to 3
        
        for template in selected_dorks:
            query = template.format(topic=topic)
            print(f"\n🔍 Hunting for: {query}")
            
            try:
                results = google_search(query)
                
                if 'items' in results:
                    count = save_to_supabase(results['items'], query)
                    total_found += count
                elif 'error' in results:
                    print(f"   ⚠️ Google Error: {results['error']['message']}")
                else:
                    print(f"   ⚠️ No fresh results found.")
                    
                time.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Critical Error: {e}")
                
    print(f"\n🏁 Mission Complete. Hunted {total_found} FRESH scholarships.")

if __name__ == "__main__":
    main()

