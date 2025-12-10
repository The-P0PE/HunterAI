import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client
from pypdf import PdfReader

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
            "match_threshold": 0.50,
            "match_count": 15
        }).execute()
        return response.data
    except Exception as e:
        st.error(f"Search Error: {e}")
        return []

# --- EVOLVED GHOSTWRITER (Adversarial Loop) ---
def generate_essay(user_profile, scholarship_title, scholarship_data):
    model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
    
    # STEP 1: The Forger (Drafting)
    draft_prompt = f"""
    ROLE: You are the candidate (Human).
    TASK: Write a raw, first-draft Statement of Purpose (350 words).
    
    CANDIDATE PROFILE:
    {user_profile}
    
    SCHOLARSHIP GOAL:
    {scholarship_title}
    
    CONTEXT (Source Material):
    {scholarship_data[:5000]}
    
    INSTRUCTIONS:
    1. Be specific. Use the candidate's REAL experiences from the profile.
    2. Do NOT use fancy AI words like "delve", "tapestry", "realm", or "underscores".
    3. Write simply and directly. Connect the candidate's history to the scholarship's mission.
    """
    
    with st.spinner("✍️ Phase 1: Drafting initial thoughts..."):
        try:
            draft = model.generate_content(draft_prompt).text
        except Exception as e:
            return f"Error in drafting: {e}"

    # STEP 2: The Detective (Critique)
    critique_prompt = f"""
    ROLE: AI Detection Algorithm & Writing Critic.
    TASK: Analyze the text below. Identify sentences that sound robotic, generic, or cliché.
    
    TEXT TO ANALYZE:
    {draft}
    
    CRITIQUE INSTRUCTIONS:
    1. Identify phrases that lack specific detail.
    2. Flag words that are too formal or "flowery" (e.g., "It is with great enthusiasm").
    3. Output ONLY the critique instructions for the re-writer.
    """
    
    try:
        critique = model.generate_content(critique_prompt).text
    except:
        critique = "Make it more conversational and specific."

    # STEP 3: The Humanizer (Evolution)
    humanize_prompt = f"""
    ROLE: Professional Editor.
    TASK: Rewrite the draft to pass an AI Detector and sound completely human.
    
    ORIGINAL DRAFT:
    {draft}
    
    CRITIQUE TO FIX:
    {critique}
    
    HUMANIZATION RULES (CRITICAL):
    1. "Burstiness": Vary sentence length. Mix short, punchy sentences with longer ones.
    2. "Perplexity": Use specific nouns/verbs, avoid generic adjectives.
    3. Remove all "AI transitions" (e.g., "Furthermore", "In conclusion", "Moreover").
    4. Start paragraphs abruptly, like a human would.
    5. The final output must be the essay ONLY.
    """
    
    with st.spinner("🧬 Phase 2: Evolving & Humanizing..."):
        try:
            final_essay = model.generate_content(humanize_prompt).text
            return final_essay
        except Exception as e:
            return f"Error in humanizing: {e}"

# --- VAULT FUNCTIONS ---
def save_to_vault(scholarship_id):
    try:
        # Check if already saved
        existing = supabase.table("saved_scholarships").select("*").eq("scholarship_id", scholarship_id).execute()
        if not existing.data:
            supabase.table("saved_scholarships").insert({"scholarship_id": scholarship_id}).execute()
            st.toast("✅ Saved to Vault!")
            
            # THE FIX: Force the app to refresh immediately so the Sidebar updates
            st.rerun()
        else:
            st.toast("⚠️ Already in Vault")
    except Exception as e:
        st.error(f"Save Error: {e}")

def get_vault_items():
    try:
        response = supabase.table("saved_scholarships").select("id, created_at, scholarships (id, title, url, full_text)").execute()
        return response.data
    except:
        return []

def delete_from_vault(saved_id):
    try:
        supabase.table("saved_scholarships").delete().eq("id", saved_id).execute()
        st.rerun()
    except Exception as e:
        st.error(f"Delete Error: {e}")

def get_stats():
    try:
        response = supabase.table("scholarships").select("id", count="exact").execute()
        return response.count
    except:
        return 0

# --- 3. UI ---

st.title("🎓 Scholarship Discovery Engine")

# SESSION STATE
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "user_profile" not in st.session_state:
    st.session_state.user_profile = ""

# --- SIDEBAR: THE VAULT & STATS ---
with st.sidebar:
    st.header("HunterAI 🎯")
    st.metric("Database Size", get_stats())
    
    st.divider()
    st.subheader("📂 My Vault")
    vault_items = get_vault_items()
    
    if vault_items:
        for saved in vault_items:
            sch = saved['scholarships']
            if sch:
                with st.expander(f"📌 {sch['title'][:25]}..."):
                    st.markdown(f"[🔗 Link]({sch['url']})")
                    if st.button("🗑️ Remove", key=f"del_{saved['id']}"):
                        delete_from_vault(saved['id'])
                    
                    if st.button("✍️ Draft", key=f"vault_draft_{saved['id']}"):
                        if st.session_state.user_profile:
                            draft = generate_essay(st.session_state.user_profile, sch['title'], sch['full_text'] or "")
                            st.subheader("Draft:")
                            st.text_area("Copy:", value=draft, height=200)
                        else:
                            st.error("Please fill your profile/resume first!")
    else:
        st.info("No saved scholarships yet.")

# --- MAIN AREA ---

# RESUME UPLOADER
uploaded_resume = st.file_uploader("📂 Upload your Resume/CV (PDF)", type="pdf")
if uploaded_resume:
    if "last_uploaded" not in st.session_state or st.session_state.last_uploaded != uploaded_resume.name:
        resume_text = extract_text_from_pdf(uploaded_resume)
        if len(resume_text) > 50:
            st.session_state.user_profile = resume_text
            st.session_state.last_uploaded = uploaded_resume.name
            st.success("✅ Resume parsed!")

user_query = st.text_area(
    "Your Profile (Auto-filled from Resume)", 
    value=st.session_state.user_profile,
    placeholder="Or type manually: I am a Ghanaian Aerospace Engineer...",
    height=150
)

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
                
                # ACTION BUTTONS ROW
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✍️ Write Application", key=f"btn_{item['id']}"):
                        db_data = supabase.table("scholarships").select("full_text").eq("id", item['id']).execute()
                        full_text = db_data.data[0]['full_text'] if db_data.data else ""
                        if full_text:
                            draft = generate_essay(st.session_state.user_profile, item['title'], full_text)
                            st.subheader("Stealth Draft:")
                            st.text_area("Copy this:", value=draft, height=400)
                        else:
                            st.error("Text not found.")
                with btn_col2:
                    if st.button("💾 Save to Vault", key=f"save_{item['id']}"):
                        save_to_vault(item['id'])
                        
            with col2:
                st.metric("Relevance", f"{int(item['similarity']*100)}%")

elif user_query and not st.session_state.search_results:
    st.info("Click 'Find Matches' to search.")


