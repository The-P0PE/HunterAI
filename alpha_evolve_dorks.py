import os
import google.generativeai as genai
from dotenv import load_dotenv
from googleapiclient.discovery import build
from supabase import create_client, Client

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Config
SEARCH_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ID = os.getenv("SEARCH_ENGINE_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def find_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferences = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        for pref in preferences:
            if pref in models: return pref
        return models[0] if models else 'models/gemini-pro'
    except:
        return 'models/gemini-pro'

ACTIVE_MODEL_NAME = find_best_model()

def google_search_count(query):
    try:
        service = build("customsearch", "v1", developerKey=SEARCH_KEY)
        res = service.cse().list(q=query, cx=SEARCH_ID, num=1).execute()
        total = int(res.get("searchInformation", {}).get("totalResults", "0"))
        return total
    except:
        return 0

def mutate_templates(current_templates):
    model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
    prompt = f"""
    ROLE: Elite Search Engineer.
    TASK: Create 3 NEW, SIMPLIFIED Google Dork templates for finding 2025/2026 scholarships.
    
    CURRENT TEMPLATES:
    {current_templates}
    
    INSTRUCTIONS:
    1. Keep the {{topic}} placeholder.
    2. Focus on: 'site:.edu', 'filetype:pdf', 'intitle:application'.
    3. Make them distinct from the current ones.
    4. Return ONLY a python list of strings.
    """
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```python", "").replace("```", "").strip()
        return eval(clean_text)
    except:
        return []

def get_existing_dorks():
    try:
        # Get dorks stored in DB
        res = supabase.table("search_dorks").select("dork_template").execute()
        return [row['dork_template'] for row in res.data]
    except:
        return []

def save_survivor(template):
    try:
        # Check if exists
        existing = supabase.table("search_dorks").select("id").eq("dork_template", template).execute()
        if not existing.data:
            supabase.table("search_dorks").insert({"dork_template": template}).execute()
            print(f"   💾 Saved to Memory: {template}")
    except Exception as e:
        print(f"   ⚠️ Save Error: {e}")

def main():
    print(f"🧬 AlphaEvolve ({ACTIVE_MODEL_NAME}): Automated Cycle Starting...")
    
    # 1. Load Ancestors (Base + DB)
    base_ancestors = [
        'site:.edu "{topic}" scholarship 2025 international',
        'filetype:pdf "{topic}" scholarship application 2025'
    ]
    db_ancestors = get_existing_dorks()
    ancestors = list(set(base_ancestors + db_ancestors))[-5:] # Keep last 5 to keep prompt short
    
    # 2. Mutate
    mutants = mutate_templates(ancestors)
    if not mutants: return

    # 3. Test & Save
    test_topic = "Civil Engineering"
    for template in mutants:
        try:
            query = template.format(topic=test_topic)
            score = google_search_count(query)
            
            # Selection Logic: Must find at least 5 results
            if score > 5:
                print(f"   ✅ Survivor Found ({score} hits): {template}")
                save_survivor(template)
            else:
                print(f"   ❌ Died ({score} hits): {template}")
        except:
            pass

if __name__ == "__main__":
    main()