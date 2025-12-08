import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from supabase import create_client, Client

# Load secrets from .env file
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
CX = os.getenv("SEARCH_ENGINE_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def google_search(query, num_results=10):
    print(f"🔍 Hunting for: {query}")
    service = build("customsearch", "v1", developerKey=API_KEY)
    results = []
    
    try:
        res = service.cse().list(q=query, cx=CX, num=num_results).execute()
        if 'items' in res:
            results.extend(res['items'])
        else:
            print("   ⚠️ No results found.")
    except Exception as e:
        print(f"   ❌ Error contacting Google: {e}")
        
    return results

def save_to_supabase(item, query):
    data = {
        "title": item.get("title"),
        "url": item.get("link"),
        "content_snippet": item.get("snippet"),
        "source_query": query,
        "is_processed": False
    }

    try:
        response = supabase.table("scholarships").upsert(data, on_conflict="url").execute()
        short_title = (data['title'][:40] + '..') if len(data['title']) > 40 else data['title']
        print(f"   ✅ Saved: {short_title}")
    except Exception as e:
        print(f"   ⚠️ Database Error: {e}")

def main():
    # Targeted 'Dorks' for Ghanaian Civil Engineers
    dorks = [
        'site:.edu "civil engineering" scholarship 2025 ghana',
        'filetype:pdf "application form" scholarship civil engineering africa',
        '"fully funded" masters civil engineering international students',
        'site:.org "tuition waiver" engineering students developing countries'
    ]

    print("🚀 HunterAI: Initializing Raw Hunt...")
    
    total_found = 0
    for dork in dorks:
        results = google_search(dork)
        for item in results:
            save_to_supabase(item, dork)
            total_found += 1

    print(f"\n🏁 Mission Complete. Hunted {total_found} potential scholarships.")

if __name__ == "__main__":
    main()