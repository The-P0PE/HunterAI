import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_database():
    print("🧹 HunterAI: Running Garbage Collection...")
    
    # 1. DELETE EXPIRED DEADLINES
    # (Requires that your Scraper actually found a date)
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        response = supabase.table("scholarships").delete().lt("deadline", today).execute()
        if response.data:
            print(f"   🗑️ Removed {len(response.data)} expired scholarships (Deadline passed).")
    except Exception as e:
        print(f"   ⚠️ Error cleaning deadlines: {e}")

    # 2. DELETE OLD RECORDS (Stale Data)
    # If a link has been in our DB for > 365 days, assume it's dead/changed.
    one_year_ago = (datetime.now() - timedelta(days=365)).isoformat()
    try:
        response = supabase.table("scholarships").delete().lt("created_at", one_year_ago).execute()
        if response.data:
            print(f"   🗑️ Removed {len(response.data)} stale scholarships (> 1 year old).")
    except Exception as e:
        print(f"   ⚠️ Error cleaning stale data: {e}")

    # 3. STATS
    count = supabase.table("scholarships").select("id", count="exact").execute().count
    print(f"✨ Database clean. {count} active opportunities remaining.")

if __name__ == "__main__":
    clean_database()