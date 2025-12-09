import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client
from pypdf import PdfReader # We use this to read the uploaded resume

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
    """Auto-detects the best available Gemini model"""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferences = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-pro']
        for pref in preferences:
            if pref in models: return pref
        return models[0] if models else 'gemini-pro'
    except:
        return 'gemini-pro'

ACTIVE_MODEL_NAME = find_best_model()

def extract_text_from_pdf(uploaded_file):
    """Reads the uploaded PDF and returns text"""
    try:
        pdf_reader = PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"

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
            "match_threshold": 0.60, 
            "match_count": 15
        }).execute()
        return response.data
    except Exception as e:
        st.error(f"Search Error: {e}")
        return []

def generate_essay(user_profile, scholarship_title, scholarship_data):
    model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
    prompt = f"""
    ROLE: Expert Academic Career Coach.
    TASK: Write a strong, tailored Statement of Purpose (300-400 words).
    
    CANDIDATE RESUME/PROFILE:
    {user_profile}
    
    SCHOLARSHIP CONTEXT:
    Title: {scholarship_title}
    Details: {scholarship_data[:6000]}
    
    INSTRUCTIONS:
    1. Extract specific achievements from the Candidate Profile to prove they fit the Scholarship.
    2. Do not just summarize; argue why they are the perfect candidate.
    3. Maintain a professional, ambitious tone.
    """
    with st.spinner(f"✍️ Ghostwriter is analyzing your resume..."):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error: {e}"

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
    st.info("💡 Upload your Resume to unlock 'Deep Match' mode.")

st.title("🎓 Scholarship Discovery Engine")

# SESSION STATE
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "user_profile" not in st.session_state:
    st.session_state.user_profile = ""

# --- NEW: RESUME UPLOADER ---
uploaded_resume = st.file_uploader("📂 Upload your Resume/CV (PDF)", type="pdf")

if uploaded_resume:
    # Extract text immediately when uploaded
    resume_text = extract_text_from_pdf(uploaded_resume)
    if len(resume_text) > 50:
        st.session_state.user_profile = resume_text
        st.success("✅ Resume parsed! I have extracted your experience.")
    else:
        st.warning("⚠️ Could not read text from this PDF (it might be an image).")

# Input Area (Auto-filled by Resume)
user_query = st.text_area(
    "Your Profile (Auto-filled from Resume)", 
    value=st.session_state.user_profile,
    placeholder="Or type manually: I am a Ghanaian Aerospace Engineer...",
    height=200 # Made taller for resumes
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
                
                if st.button("✍️ Write Application", key=f"btn_{item['id']}"):
                    db_data = supabase.table("scholarships").select("full_text").eq("id", item['id']).execute()
                    full_text = db_data.data[0]['full_text'] if db_data.data else ""
                    
                    if full_text:
                        draft = generate_essay(st.session_state.user_profile, item['title'], full_text)
                        st.subheader("Draft Application:")
                        st.text_area("Copy this:", value=draft, height=400)
                    else:
                        st.error("Text not found. Run Scraper.")     
            with col2:
                st.metric("Relevance", f"{int(item['similarity']*100)}%")

elif user_query and not st.session_state.search_results:
    st.info("Click 'Find Matches' to search.")

