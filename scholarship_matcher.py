import os
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client

# Load secrets
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

def get_embedding(text):
    clean_text = text.replace("\n", " ")
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=clean_text,
        task_type="retrieval_query" # Note: 'query' type for the search side
    )
    return result['embedding']

def find_matches(user_query):
    print(f"\n🔍 Analyzing Query: '{user_query}'")
    
    # 1. Turn user text into a vector
    try:
        query_vector = get_embedding(user_query)
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return

    # 2. Call the Supabase function (RPC)
    print("📡 Consulting the database...")
    try:
        response = supabase.rpc("match_scholarships", {
            "query_embedding": query_vector,
            "match_threshold": 0.5, # Lower this if you get no results (e.g. 0.3)
            "match_count": 5
        }).execute()
        
        matches = response.data
        
        if not matches:
            print("⚠️ No strong matches found. Try a broader query.")
            return

        print(f"✅ Found {len(matches)} Relevant Opportunities:\n")
        print("-" * 50)
        
        for i, match in enumerate(matches):
            print(f"{i+1}. {match['title']}")
            print(f"   🎯 Relevance: {int(match['similarity'] * 100)}%")
            print(f"   🔗 Link: {match['url']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Database Error: {e}")

if __name__ == "__main__":
    # You can change this string to test different profiles!
    print("🎓 Welcome to HunterAI Matcher")
    user_input = input("Tell me about yourself (e.g., 'Ghanaian Civil Engineer looking for Masters'): ")
    find_matches(user_input)