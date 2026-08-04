import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import time

DB_PATH = "admissions_structured.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
}

def fetch_cug_rankings():
    """Scrapes Complete University Guide overall league table ranks."""
    url = "https://www.thecompleteuniversityguide.co.uk/league-tables/rankings"
    ranks = {}
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for row in soup.find_all('tr'):
                text = row.get_text(separator='|', strip=True)
                parts = text.split('|')
                if len(parts) >= 2 and parts[0].isdigit():
                    rank = int(parts[0])
                    uni_name = parts[1]
                    ranks[uni_name] = rank
    except Exception as e:
        print(f"⚠️ Error scraping Complete University Guide: {e}")
    return ranks

def update_rankings_in_db(cug_data=None, guardian_data=None, qs_data=None):
    """Updates the guardian_rank, cug_rank, and qs_rank columns in SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT pubukprn, university FROM course_facts")
    universities = cursor.fetchall()
    
    for pubukprn, uni_name in universities:
        cug_rank = None
        guardian_rank = None
        qs_rank = None
        
        # Match scraped rankings to DB university names
        if cug_data:
            for scraped_name, rank in cug_data.items():
                if scraped_name.lower() in uni_name.lower() or uni_name.lower() in scraped_name.lower():
                    cug_rank = rank
                    break
                    
        # Apply updates where ranking values were found
        if cug_rank:
            cursor.execute("UPDATE course_facts SET cug_rank = ? WHERE pubukprn = ?", (cug_rank, pubukprn))
        if guardian_rank:
            cursor.execute("UPDATE course_facts SET guardian_rank = ? WHERE pubukprn = ?", (guardian_rank, pubukprn))
        if qs_rank:
            cursor.execute("UPDATE course_facts SET qs_rank = ? WHERE pubukprn = ?", (qs_rank, pubukprn))
            
    conn.commit()
    conn.close()
    print("✅ Ranking updates applied to admissions_structured.db")

if __name__ == "__main__":
    print("🔍 Fetching CUG League Table rankings...")
    cug_ranks = fetch_cug_rankings()
    update_rankings_in_db(cug_data=cug_ranks)