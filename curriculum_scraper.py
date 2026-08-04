import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import time
import random

DB_PATH = "admissions_structured.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
}

def extract_curriculum_info(ucas_code, course_title, university):
    """
    Searches web pages/UCAS course structure for final year project and dissertation details.
    """
    query = f"{university} {course_title} {ucas_code} final year project credits module structure".replace(" ", "%20")
    search_url = f"https://digital.ucas.com/coursedisplay/results/courses?searchTerm={query}"
    
    project_credits = "Not found"
    
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            
            # Pattern matching for project / dissertation credits
            credit_match = re.search(r'(\b\d{2}\b)[\s-]*credit[s]?\s*(?:final year project|dissertation|individual project|capstone)', text, re.IGNORECASE)
            if credit_match:
                project_credits = f"{credit_match.group(1)} credits"
            elif "dissertation" in text.lower() or "final year project" in text.lower():
                project_credits = "Compulsory Project (Credits unlisted)"
    except Exception as e:
        print(f"⚠️ Error scraping curriculum for {course_title}: {e}")
        
    return project_credits

def run_curriculum_enrichment():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, ucas_code, course_title, university 
        FROM course_facts 
        WHERE final_year_project_credits = 'Not found'
    """)
    records = cursor.fetchall()
    
    print(f"🔍 Found {len(records)} course records needing curriculum details...")
    
    for row_id, ucas_code, title, university in records:
        # Clean potential float trailing zeros from the UCAS string (e.g. '3792.0' -> '3792')
        clean_ucas = str(ucas_code).split('.')[0] if ucas_code else ""
        
        print(f"Analyzing curriculum for: {title} ({university})...")
        credits_info = extract_curriculum_info(clean_ucas, title, university)
        
        if credits_info != "Not found":
            cursor.execute("UPDATE course_facts SET final_year_project_credits = ? WHERE id = ?", (credits_info, row_id))
            conn.commit()
            
        time.sleep(random.uniform(1.0, 2.5))
        
    conn.close()
    print("✅ Curriculum details updated in database.")

if __name__ == "__main__":
    run_curriculum_enrichment()