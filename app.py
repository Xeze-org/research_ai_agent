import streamlit as st
import os
import asyncio
import markdown
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from mistralai import Mistral
from duckduckgo_search import DDGS
from xhtml2pdf import pisa
from io import BytesIO

# Load environment variables
load_dotenv()

# Page Config
st.set_page_config(page_title="Mistral Research Agent", page_icon="🕵️", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .report-font {
        font-family: 'Helvetica', sans-serif;
    }
    .stDownloadButton {
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)

# --- Database Functions ---
DB_FILE = "research_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_research(topic, content):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO history (topic, content) VALUES (?, ?)', (topic, content))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, topic, timestamp, content FROM history ORDER BY timestamp DESC')
    data = c.fetchall()
    conn.close()
    return data

def get_research_by_id(r_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT topic, content FROM history WHERE id = ?', (r_id,))
    data = c.fetchone()
    conn.close()
    return data

# Initialize DB on load
init_db()

# --- Helper Functions ---
def clean_markdown(text):
    """Removes markdown code blocks if present."""
    if text.startswith("```markdown"):
        text = text.replace("```markdown", "", 1)
    elif text.startswith("```"):
        text = text.replace("```", "", 1)
    
    if text.endswith("```"):
        text = text[:-3]
        
    return text.strip()

def search_web(query, max_results=5):
    """Searches the web using DuckDuckGo."""
    try:
        results = DDGS().text(query, max_results=max_results)
        return results
    except Exception as e:
        st.error(f"Search error: {e}")
        return []

async def get_mistral_response(api_key, topic, context):
    client = Mistral(api_key=api_key)
    model = "mistral-medium-latest"
    
    system_prompt = (
        "You are an expert career researcher. "
        "Create a visually appealing, easy-to-read report. " 

        "Use structure with clear H1, H2, and H3 markdown headings. "
        "Use bold text for key points. "
        "Use EMOJIS liberally to make it engaging! 🚀"
        "IMPORTANT: Format checklists with each item on a NEW LINE starting with '- [ ]'. Do NOT condense them into a single paragraph."
        "Do not wrap the output in markdown code blocks."
    )

    user_prompt = (
        f"Write a comprehensive report on: {topic}\n\n"
        f"CONTEXT FROM WEB SEARCH:\n{context}\n\n"
        "Provide actionable advice and avoid generic fluff."
    )

    try:
        response = await client.chat.complete_async(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        if response and response.choices:
            return clean_markdown(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Mistral API Error: {e}")
        return None

def create_pdf(markdown_text):
    """Converts Markdown to a styled PDF using xhtml2pdf."""
    
    # Pre-process checkers for PDF compatibility (basic text)
    pdf_text = markdown_text.replace("- [ ]", "- [ ]").replace("- [x]", "- [x]")
    
    html_content = markdown.markdown(pdf_text, extensions=['tables'])
    
    full_html = f"""
    <html>
    <head>
        <style>
            @page {{
                size: A4;
                margin: 2.5cm;
                @frame footer_frame {{
                    -pdf-frame-content: footerContent;
                    bottom: 1cm;
                    margin-left: 1cm;
                    margin-right: 1cm;
                    height: 1cm;
                }}
            }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #333; }}
            h1 {{ color: #2c3e50; font-size: 24pt; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-top: 30px; margin-bottom: 20px; }}
            h2 {{ color: #2c3e50; font-size: 18pt; margin-top: 25px; margin-bottom: 15px; border-left: 5px solid #3498db; padding-left: 10px; }}
            h3 {{ color: #2c3e50; font-size: 14pt; margin-top: 20px; margin-bottom: 10px; font-weight: bold; }}
            p {{ margin-bottom: 10px; text-align: justify; }}
            strong {{ color: #000; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; margin-top: 10px; }}
            th {{ background-color: #f2f2f2; color: #333; font-weight: bold; padding: 8px; border: 1px solid #ddd; text-align: left; }}
            td {{ padding: 8px; border: 1px solid #ddd; }}
            ul {{ margin-bottom: 10px; margin-left: 0; padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            .footer {{ text-align: center; color: #7f8c8d; font-size: 9pt; }}
        </style>
    </head>
    <body>
        <div id="footerContent" class="footer">Generated by Mistral Research Agent</div>
        {html_content}
    </body>
    </html>
    """
    
    pdf_file = BytesIO()
    pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)
    if pisa_status.err: return None
    return pdf_file.getvalue()

# --- UI Layout ---
st.title("🤖 Mistral Research Agent")

# Sidebar for History
with st.sidebar:
    st.header("📜 Past Research")
    history = get_history()
    if st.button("➕ New Research"):
        st.session_state.current_report = None
        st.session_state.current_topic = ""
        st.rerun()
    
    st.divider()
    
    for r_id, r_topic, r_time, _ in history:
        # Display simplified date/time
        dt = datetime.strptime(r_time, '%Y-%m-%d %H:%M:%S')
        date_str = dt.strftime("%b %d")
        if st.button(f"{date_str}: {r_topic}", key=f"hist_{r_id}"):
            # Load from DB
            data = get_research_by_id(r_id)
            if data:
                st.session_state.current_topic = data[0]
                st.session_state.current_report = data[1]
                st.rerun()

# Main Content
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    api_key = st.text_input("Enter Mistral API Key", type="password")

# Input Area (Only show if not viewing a report or if explicitly starting new)
if "current_report" not in st.session_state or st.session_state.current_report is None:
    topic_input = st.text_input("Enter Research Topic", "Common Tech Profession & Job Mistakes")
    
    if st.button("🚀 Start Research"):
        if not api_key:
            st.error("Please provide an API Key.")
        else:
            with st.status("🕵️ Researching...", expanded=True) as status:
                st.write("Searching DuckDuckGo...")
                results = search_web(topic_input)
                context = ""
                for r in results:
                    context += f"- {r['title']}: {r['body']} ({r['href']})\n"
                
                st.write("Analyzing with Mistral AI...")
                report_text = asyncio.run(get_mistral_response(api_key, topic_input, context))
                
                if report_text:
                    save_research(topic_input, report_text)
                    st.session_state.current_topic = topic_input
                    st.session_state.current_report = report_text
                    status.update(label="Complete!", state="complete", expanded=False)
                    st.rerun()

# Display Report (if available)
if "current_report" in st.session_state and st.session_state.current_report:
    st.divider()
    
    # Top Bar: Topic on Left, PDF Button on Right
    col_header, col_btn = st.columns([3, 1])
    
    with col_header:
        st.markdown(f"<h2 style='color: #4A90E2;'>Results for: {st.session_state.current_topic}</h2>", unsafe_allow_html=True)
        
    with col_btn:
        pdf_bytes = create_pdf(st.session_state.current_report)
        if pdf_bytes:
            st.download_button(
                label="📄 Download PDF",
                data=pdf_bytes,
                file_name=f"Report_{st.session_state.current_topic[:10].replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
    
    st.markdown("---")
    
    # Render with custom styling
    st.markdown(
        f"""
        <div style="
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            font-size: 16px;
        ">
        {markdown.markdown(st.session_state.current_report, extensions=['tables'])}
        </div>
        """, 
        unsafe_allow_html=True
    )
