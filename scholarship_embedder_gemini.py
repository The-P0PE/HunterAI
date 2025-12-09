import os
import time
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Setup & Config
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not SUPABASE_URL or not GEMINI_API_KEY:
    print("❌ Error: Missing API Keys in .env")
    exit()

# Initialize connections
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

def generate_embedding(text):
    """
    Turns text into a vector using Gemini.
    """
    try:
        # Clean text slightly to save tokens
        clean_text = text.replace("\n", " ")[:9000] # Limit to 9000 chars to be safe
        
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=clean_text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"   ⚠️ Embedding Error: {e}")
        return None

def main():
    print("🧠 Embedder (with Rate Limit Guard) Initialized...")
    
    # 2. Fetch scholarships that have Text but NO Memory (embedding is null)
    # We increase the limit slightly since we now have safety brakes
    response = supabase.table("scholarships") \
        .select("id, title, full_text") \
        .is_("embedding", "null") \
        .neq("full_text", "null") \
        .limit(50) \
        .execute()
        
    tasks = response.data
    
    if not tasks:
        print("✅ All readable scholarships have been memorized!")
        return

    print(f"📚 Found {len(tasks)} scholarships to memorize...")

    for item in tasks:
        print(f"\n⚡ Memorizing: {item['title'][:40]}...")
        
        # A. Generate the Vector
        vector = generate_embedding(item['full_text'])
        
        if vector:
            # B. Save to Database
            try:
                supabase.table("scholarships") \
                    .update({"embedding": vector}) \
                    .eq("id", item['id']) \
                    .execute()
                print("   ✅ Saved to memory.")
            except Exception as e:
                print(f"   ❌ DB Error: {e}")
        else:
            # If embedding failed (e.g., text too messy), skip it for now
            print("   ⚠️ Skipped.")

        # --- THE SAFETY BRAKE ---
        # Gemini Free Tier Limit: ~15 requests per minute.
        # We wait 4 seconds to stay safe (60s / 15 = 4s).
        print("   ⏳ Cooling down for 4 seconds...")
        time.sleep(4)

if __name__ == "__main__":
    main()
