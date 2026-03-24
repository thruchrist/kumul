import os
from datetime import datetime, timedelta
from tavily import TavilyClient
from langchain_core.tools import tool
from dotenv import load_dotenv
from database import update_user_profile 

load_dotenv()
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def search_png_jobs(role: str, location: str = "Papua New Guinea") -> str:
    """
    Searches specifically for job vacancies in Papua New Guinea using advanced filtering.
    Use this ONLY when the user explicitly asks to find jobs.
    """
    # Calculate date for "recent" jobs (last 30 days)
    date_threshold = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Construct high-precision query
    # We prioritize LinkedIn and local PNG job boards
    query = (
        f"{role} job vacancy {location} PNG "
        f"site:linkedin.com/jobs OR site:pngjobseek.com OR site:pg.Indeed.com"
    )
    
    try:
        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=8,
            include_raw_content=False,
            days=30 # Look back 30 days
        )
        
        if not response.get('results'):
            return "ZERO_RESULTS: No recent jobs found."

        formatted_results = []
        for item in response['results']:
            title = item.get('title', 'Job Opening')
            url = item.get('url', '')
            # Filter out non-job links (common in web search noise)
            if "job" in title.lower() or "vacancy" in title.lower() or "career" in title.lower():
                formatted_results.append(f"👉 *{title}*\n🔗 {url}")
        
        if not formatted_results:
            return "ZERO_RESULTS: Found pages but no direct job listings."

        return "\n\n".join(formatted_results)

    except Exception as e:
        return f"SEARCH_ERROR: {str(e)}"

@tool
def save_user_profile(phone_number: str, profession: str = None, location: str = None) -> str:
    """
    Saves the user's professional details to permanent memory.
    Call this immediately when the user mentions their job or location.
    """
    try:
        update_user_profile(phone_number=phone_number, profession=profession, location=location)
        return "SUCCESS: Profile saved."
    except Exception as e:
        return f"ERROR: Failed to save profile: {str(e)}"