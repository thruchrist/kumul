import os
from datetime import datetime
from tavily import TavilyClient
from langchain_core.tools import tool
from dotenv import load_dotenv
from database import update_user_profile 

load_dotenv()
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def search_png_jobs(role: str, location: str = "Papua New Guinea") -> str:
    """
    Searches for job vacancies in Papua New Guinea.
    Use this when the user asks to find jobs.
    Args:
        role: The job title (e.g., 'driver', 'accountant').
        location: The location (e.g., 'Lae', 'Port Moresby').
    """
    current_year = datetime.now().year
    # Optimized query for PNG context
    query = f"job vacancy {role} in {location} PNG {current_year} site:pg OR site:linkedin.com/jobs"
    
    try:
        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_raw_content=False,
        )
        
        if not response.get('results'):
            return f"No recent jobs found for {role} in {location}."

        jobs_list = []
        for item in response['results']:
            title = item.get('title', 'Job Opening')
            url = item.get('url', '')
            jobs_list.append(f"👉 *{title}*\n🔗 {url}")
        
        return "\n\n".join(jobs_list)

    except Exception as e:
        return f"Search failed: {str(e)}"

@tool
def save_user_data(phone_number: str, profession: str = None, location: str = None) -> str:
    """
    Saves or updates the user's professional profile.
    Call this immediately when the user mentions their job or location.
    """
    try:
        update_user_profile(
            phone_number=phone_number, 
            profession=profession, 
            location=location
        )
        return "Profile updated."
    except Exception as e:
        return f"Error updating profile: {str(e)}"