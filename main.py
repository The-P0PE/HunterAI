import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="HunterAI", page_icon="🎓", layout="wide")
load_dotenv()

# Initialize connection
@st.cache_resource
def init_connections():
    try:
        sup_url = os.getenv("SUPABASE_URL")
        sup_key = os.getenv("SUPABASE_KEY")
        gem_key = os.getenv("GEMINI_API_KEY")
        
        if not sup_url or not sup_key or not gem_key:
            st.error("❌ Missing API Keys in .env file!")
            return None, None
            
        sup = create_client(sup_url, sup_key)
        genai.configure(api_key=gem_key)
        return sup, genai
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None, None

supabase, ai = init_connections()

# --- 2. LOGIC ---

@st.cache_data
def find_best_model():
    """
    Automatically finds a working model name for this API Key.
    """
    try:
        # Get all models that support generating content
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Priority list (Fastest/Newest first)
        preferences = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-pro',
            'models/gemini-pro'
        ]
        
        # Check for matches
        for pref in preferences:
            if pref in models:
                return pref
        
        # Fallback: Just take the first valid one we found
        if models:
            return models[0]
            
    except Exception as e:
        st.warning(f"⚠️ Could not auto-detect models: {e}. Defaulting to 'gemini-pro'.")
    
    return 'gemini-pro' # Safe fallback

# Detect model once on startup
ACTIVE_MODEL_NAME = find_best_model()

def get_embedding(text):
    clean_text = text.replace("\n", " ")
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=clean_text,
        task_type="retrieval_query" 
    )
    return result['embedding']

def semantic_search(query_text):
    try:
        query_vector = get_embedding(query_text)
        response = supabase.rpc("match_scholarships", {
            "query_embedding": query_vector,
            "match_threshold": 0.40,
            "match_count": 15
        }).execute()
        return response.data
    except Exception as e:
        st.error(f"Search Error: {e}")
        return []

def generate_essay(user_profile, scholarship_title, scholarship_data):
    # Use the auto-detected model
    model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
    
    prompt = f"""
    ROLE: Academic career coach.
    TASK: Write a 300-word scholarship application essay.
    CANDIDATE: {user_profile}
    SCHOLARSHIP: {scholarship_title}
    CONTEXT: {scholarship_data[:6000]}
    
    OUTPUT: Professional, persuasive, matching candidate skills to scholarship needs.
    """
    with st.spinner(f"✍️ Ghostwriter ({ACTIVE_MODEL_NAME.replace('models/', '')}) is thinking..."):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating essay: {e}"

def get_stats():
    try:
        response = supabase.table("scholarships").select("id", count="exact").execute()
        return response.count
    except:
        return 0

# --- 3. UI ---

with st.sidebar:
    st.header("HunterAI 🎯")
    st.metric("Database Size", get_stats())
    st.caption(f"🤖 Model: {ACTIVE_MODEL_NAME.replace('models/', '')}")
    st.info("💡 Results are now saved in memory.")

st.title("🎓 Scholarship Discovery Engine")

# SESSION STATE MANAGEMENT
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "user_profile" not in st.session_state:
    st.session_state.user_profile = ""

# Input Area
user_query = st.text_area(
    "Your Profile", 
    value=st.session_state.user_profile,
    placeholder="I am a Ghanaian Aerospace Engineer...",
    height=100
)

# Search Button
if st.button("Find Matches", type="primary"):
    if not user_query:
        st.warning("Please define your profile first.")
    else:
        st.session_state.user_profile = user_query
        st.session_state.search_results = semantic_search(user_query)

# Display Results
if st.session_state.search_results:
    st.success(f"Found {len(st.session_state.search_results)} opportunities.")
    
    for item in st.session_state.search_results:
        with st.expander(f"**{item['title']}** ({int(item['similarity']*100)}%)"):
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(item['content_snippet'])
                st.markdown(f"[🔗 Link]({item['url']})")
                
                # Essay Button
                if st.button("✍️ Write Draft", key=f"btn_{item['id']}"):
                    db_data = supabase.table("scholarships").select("full_text").eq("id", item['id']).execute()
                    full_text = db_data.data[0]['full_text'] if db_data.data else ""
                    
                    if full_text:
                        draft = generate_essay(st.session_state.user_profile, item['title'], full_text)
                        st.subheader("Draft Application:")
                        st.text_area("Copy this:", value=draft, height=300)
                    else:
                        st.error("Text not found. Run Scraper.")
                        
            with col2:
                st.metric("Relevance", f"{int(item['similarity']*100)}%")

elif user_query and not st.session_state.search_results:

    st.info("No matches in memory. Click 'Find Matches'.")
