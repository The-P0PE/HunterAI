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
    """Fetches active topics (e.g. 'Aerospace Engineering') from the database"""
    try:
        response = supabase.table("search_terms").select("topic").eq("is_active", True).execute()
        return [row['topic'] for row in response.data]
    except Exception as e:
        print(f"⚠️ Error fetching search terms: {e}")
        return ["civil engineering", "aerospace engineering", "optometry"]

def get_dork_templates():
    """
    NEW FUNCTION: Fetches 'Evolved' search templates from the DB.
    Combines them with a safe 'Default' list.
    """
    # 1. The Safety Net (Always keep these)
    defaults = [
        'site:.edu "{topic}" scholarship 2025 2026 international',
        'filetype:pdf "application" "{topic}" scholarship 2025',
        '"fully funded" masters "{topic}" uk 2025'
    ]
    
    try:
        # 2. Fetch the 'AlphaEvolved' dorks from the database
        response = supabase.table("search_dorks").select("dork_template").execute()
        db_dorks = [row['dork_template'] for row in response.data]
        
        if db_dorks:
            print(f"   🧬 Found {len(db_dorks)} evolved strategies in memory.")
        
        # 3. Combine and remove duplicates (using set)
        final_list = list(set(defaults + db_dorks))
        return final_list
        
    except Exception as e:
        print(f"   ⚠️ Could not fetch evolved dorks (using defaults): {e}")
        return defaults

def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'num': 10,
        'dateRestrict': 'y1'  # Freshness Filter (Last 1 Year)
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
                "is_processed": False 
            }
            supabase.table("scholarships").upsert(data, on_conflict="url").execute()
            print(f"   ✅ Saved: {item.get('title')[:40]}..")
            count += 1
        except Exception:
            pass
    return count

def main():
    print("🚀 HunterAI: Initializing Freshness Protocol...")
    
    # 1. Get Topics (What to search for)
    topics = get_search_terms()
    if not topics: 
        topics = ["Aerospace Engineering", "Optometry", "Civil Engineering"]
    
    # 2. Get Dorks (How to search) -> REPLACED HARDCODED LIST WITH THIS:
    dork_templates = get_dork_templates()
    
    print(f"🎯 Targeting {len(topics)} topics using {len(dork_templates)} strategies.")
    
    total_found = 0
    
    # 3. Hunt Loop
    for topic in topics:
        # Try 3 random strategies per topic to save API quota
        selected_dorks = random.sample(dork_templates, min(3, len(dork_templates)))
        
        for template in selected_dorks:
            query = template.format(topic=topic)
            print(f"\n🔍 Hunting: {query}")
            
            try:
                results = google_search(query)
                
                if 'items' in results:
                    count = save_to_supabase(results['items'], query)
                    total_found += count
                elif 'error' in results:
                    print(f"   ⚠️ Google Error: {results['error']['message']}")
                else:
                    print(f"   ⚠️ No fresh results.")
                    
                time.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Critical Error: {e}")
                
    print(f"\n🏁 Mission Complete. Hunted {total_found} FRESH scholarships.")

if __name__ == "__main__":
    main()
