import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import time
import random

# Database connection
DB_PATH = "admissions_structured.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.ucas.com/'
}

def scrape_ucas_course_details(ucas_code, university_name):
    """
    Searches UCAS for a specific course code and university, extracting
    A-Level grade requirements and tuition fee figures.
    """
    search_query = f"{ucas_code} {university_name}".replace(" ", "%20")
    search_url = f"https://digital.ucas.com/coursedisplay/results/courses?searchTerm={search_query}"
    
    a_level = None
    uk_fee = None
    intl_fee = None
    
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            
            # Extract A-Level Requirement Pattern (e.g., A*AA, AAB, BBB)
            a_level_match = re.search(r'A\s*level[s]?[:\s]*([A-E\*]{3})', text, re.IGNORECASE)
            if a_level_match:
                a_level = a_level_match.group(1).upper()
                
            # Extract Fee Figures
            fee_matches = re.findall(r'£([0-9,]+)', text)
            for match in fee_matches:
                amount = int(match.replace(',', ''))
                if 9000 <= amount <= 9500:
                    uk_fee = f"£{amount:,}"
                elif amount > 10000:
                    intl_fee = f"£{amount:,}"
    except Exception as e:
        print(f"⚠️ Error scraping UCAS for {ucas_code} ({university_name}): {e})")
        
    return a_level, uk_fee, intl_fee

def run_ucas_enrichment():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Select records requiring verification
    cursor.execute("""
        SELECT id, ucas_code, university 
        FROM course_facts 
        WHERE ucas_code IS NOT NULL AND ucas_code != 'N/A'
        AND (alevel_requirement = 'Needs verification' OR tuition_fee_uk = 'Not published centrally')
    """)
    records = cursor.fetchall()
    
    print(f"🔍 Found {len(records)} records needing admission & fee details...")
    
    for row_id, ucas_code, university in records:
        # Clean potential float trailing zeros from the UCAS string (e.g. '3792.0' -> '3792')
        clean_ucas = str(ucas_code).split('.')[0] if ucas_code else ""
        
        print(f"Scraping [{clean_ucas}] for {university}...")
        a_level, uk_fee, intl_fee = scrape_ucas_course_details(clean_ucas, university)
        
        # SQL Update execution
        if a_level:
            cursor.execute("UPDATE course_facts SET alevel_requirement = ? WHERE id = ?", (a_level, row_id))
        if uk_fee:
            cursor.execute("UPDATE course_facts SET tuition_fee_uk = ? WHERE id = ?", (uk_fee, row_id))
        if intl_fee:
            cursor.execute("UPDATE course_facts SET tuition_fee_intl = ? WHERE id = ?", (intl_fee, row_id))
            
        conn.commit()
        # Sleep to comply with polite web scraping standards
        time.sleep(random.uniform(1.5, 3.0))
        
    conn.close()
    print("✅ UCAS scraping and database update complete.")

if __name__ == "__main__":
    run_ucas_enrichment()