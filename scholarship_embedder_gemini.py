import os
import time
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai

# Load secrets
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_embedding(text):
    """
    Uses Gemini's free 'text-embedding-004' model.
    """
    # Gemini prefers cleaner text, so we strip newlines
    clean_text = text.replace("\n", " ")
    
    # We use the specific model for embeddings
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=clean_text,
        task_type="retrieval_document" # optimizing for search later
    )
    return result['embedding']

def main():
    print("🧠 Gemini Embedder Initialized...")

    # 1. Fetch scholarships that have text but NO embedding
    response = supabase.table("scholarships") \
        .select("id, title, full_text") \
        .neq("full_text", "null") \
        .is_("embedding", "null") \
        .limit(10) \
        .execute()
    
    tasks = response.data

    if not tasks:
        print("✅ All readable scholarships have been memorized!")
        return

    print(f"📊 Found {len(tasks)} scholarships needing memory. Asking Gemini...")

    for item in tasks:
        print(f"   Thinking about: {item['title'][:30]}...")
        
        try:
            # Generate Embedding (Gemini is fast!)
            vector = get_gemini_embedding(item['full_text'][:9000])
            
            # Save back to Supabase
            supabase.table("scholarships") \
                .update({"embedding": vector}) \
                .eq("id", item['id']) \
                .execute()
                
            print(f"     ✨ Memorized.")
            
        except Exception as e:
            print(f"     ❌ Error: {e}")
            # If we hit a rate limit, wait a bit longer
            time.sleep(2)
            
        # Polite pause
        time.sleep(1)

if __name__ == "__main__":
    main()