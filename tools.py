import os
from datetime import datetime
from tavily import TavilyClient
from langchain_core.tools import tool
from dotenv import load_dotenv

# Import your database function
from database import update_user_data 

load_dotenv()
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def search_png_jobs(role: str, location: str = "Papua New Guinea") -> str:
    """
    Searches the web for recent job vacancies.
    Args:
        role: The specific job title or industry (e.g., "Driver", "Accountant").
        location: The specific city or province in PNG (e.g., "Lae", "Port Moresby"). Defaults to "Papua New Guinea" if unknown.
    """
    current_year = datetime.now().year
    # Highly optimized search string for PNG
    search_query = f"{role} job vacancies in {location} {current_year} site:pg OR site:linkedin.com"
    
    try:
        response = tavily.search(
            query=search_query,
            search_depth="advanced",
            max_results=5, # Reduced from 10 to keep WhatsApp messages readable
            days=30,
            include_raw_content=False,
        )
        
        if not response.get('results'):
            return f"I couldn't find any recent postings for {role} in {location}. Try broadening the search."

        formatted_results = []
        for item in response['results']:
            title = item.get('title', 'No Title')
            url = item.get('url', '')
            formatted_results.append(f"📌 *{title}*\n🔗 {url}\n---")
        
        return "\n".join(formatted_results)

    except Exception as e:
        return f"Search Error: {str(e)}"

@tool
def save_user_profile(phone_number: str, profession: str = None, skills: str = None, location: str = None) -> str:
    """
    Saves or updates the user's professional profile in the database.
    Call this whenever the user shares their job, skills, or city.
    """
    try:
        update_user_data(
            phone_number=phone_number,
            profession=profession,
            skills=skills,
            location=location
        )
        saved_items = [k for k, v in {"profession": profession, "skills": skills, "location": location}.items() if v]
        return f"Successfully saved {', '.join(saved_items)} to the database."
    except Exception as e:
        return f"Failed to save profile: {str(e)}"