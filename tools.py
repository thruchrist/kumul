import os
import json
from datetime import datetime, timedelta
from functools import lru_cache
from tavily import TavilyClient
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Import database helpers
from database import save_job_for_user, get_saved_jobs, update_user_profile, get_user_profile


# ==========================================
# PNG JOB MARKET DATABASE
# ==========================================

PNG_JOB_CATEGORIES = {
    "Mining & Resources": {
        "roles": ["Mining Engineer", "Geologist", "Heavy Equipment Operator", "Surveyor", 
                  "HSE Officer", "Maintenance Technician", "Processing Plant Operator"],
        "companies": ["Ok Tedi Mining", "Porgera Joint Venture", "Lihir Gold", "Hidden Valley", 
                      "Ramu NiCo", "Wafi-Golpu", "Frieda River", "K92 Mining"],
        "locations": ["Tabubil", "Porgera", "Lihir", "Wau", "Madang", "Enga"]
    },
    "Oil & Gas": {
        "roles": ["Petroleum Engineer", "Process Operator", "Pipeline Technician", "Welders",
                  "QA/QC Inspector", "Project Manager"],
        "companies": ["Oil Search", "Kumul Petroleum", "ExxonMobil PNG", "Santos",
                      "TotalEnergies", "JX Nippon"],
        "locations": ["Port Moresby", "Hiri", "Kikori", "Gulf Province"]
    },
    "Banking & Finance": {
        "roles": ["Bank Teller", "Accountant", "Loan Officer", "Financial Analyst",
                  "Branch Manager", "Credit Analyst", "Risk Manager"],
        "companies": ["Bank South Pacific (BSP)", "Kina Bank", "ANZ PNG", "Westpac PNG",
                      "MiBank", "PNG Microfinance", "Nasfund"],
        "locations": ["Port Moresby", "Lae", "Mt Hagen", "Goroka", "Madang", "Kokopo"]
    },
    "Government & Public Service": {
        "roles": ["Policy Officer", "Administrator", "Teacher", "Nurse", "Police Officer",
                  "Customs Officer", "Immigration Officer", "District Administrator"],
        "departments": ["DPM", "Treasury", "Health", "Education", "Justice", "Foreign Affairs",
                        "Provincial Governments", "District Development Authorities"],
        "locations": ["All Provinces", "Port Moresby", "Provincial Capitals"]
    },
    "Telecommunications": {
        "roles": ["Network Engineer", "IT Support", "Sales Agent", "Customer Service",
                  "Retail Manager", "Technical Officer"],
        "companies": ["Digicel PNG", "Telikom PNG", "bmobile", "DataCo"],
        "locations": ["Port Moresby", "Lae", "Mt Hagen", "All major centres"]
    },
    "Construction & Infrastructure": {
        "roles": ["Civil Engineer", "Project Manager", "Carpenter", "Electrician",
                  "Plumber", "Site Supervisor", "Quantity Surveyor"],
        "companies": ["CCL Group", "Hegarty Builders", "Lamana Development", "Niugini Builders",
                      " Curtain Bros", "JM McCarthy", "China Harbour"],
        "locations": ["Port Moresby", "Lae", "Mt Hagen", "All provinces"]
    },
    "Retail & Hospitality": {
        "roles": ["Store Manager", "Sales Assistant", "Chef", "Waiter", "Housekeeper",
                  "Front Desk Agent", "Events Coordinator"],
        "companies": ["City Pharmacy", "Andersons Foodland", "Stop & Shop", "RH Hypermart",
                      "Crowne Plaza", "Holiday Inn", "Airways Hotel", "Grand Papua"],
        "locations": ["Port Moresby", "Lae", "Mt Hagen", "Major towns"]
    },
    "Healthcare": {
        "roles": ["Medical Officer", "Registered Nurse", "Community Health Worker",
                  "Pharmacist", "Lab Technician", "Hospital Administrator"],
        "employers": ["Port Moresby General Hospital", "Angau Hospital", "Goroka Hospital",
                      "St John PNG", "Pacific International Hospital", "Health Departments"],
        "locations": ["All provinces", "Major hospitals", "Rural health centres"]
    },
    "IT & Technology": {
        "roles": ["Software Developer", "System Administrator", "Database Administrator",
                  "IT Manager", "Helpdesk Support", "Cybersecurity Specialist"],
        "companies": ["Datec", "Digicel", "Telikom", "Bank South Pacific", "Oil Search IT",
                      "FlexCustomer", "PNG Digital", "Government ICT"],
        "locations": ["Port Moresby", "Lae", "Mt Hagen"]
    },
    "Transport & Logistics": {
        "roles": ["Truck Driver", "Forklift Operator", "Logistics Coordinator",
                  "Customs Broker", "Shipping Clerk", "Warehouse Manager"],
        "companies": ["Air Niugini", "PNG Air", "LAE Shipping", "Swift Shipping",
                      "Pacific Express", "Garamut Transport", "Mayfair Transport"],
        "locations": ["Port Moresby", "Lae", "Mt Hagen", "Coastal ports"]
    },
    "NGO & Development": {
        "roles": ["Project Officer", "Program Manager", "Monitoring & Evaluation Specialist",
                  "Community Development Officer", "Gender Specialist", "Research Officer"],
        "organizations": ["World Vision", "UNDP", "WHO", "UNICEF", "AusAid/DFAT",
                         "Care International", "Oxfam", "Red Cross", "MSI"],
        "locations": ["Port Moresby", "Provincial locations", "Remote communities"]
    },
    "Agriculture": {
        "roles": ["Agriculture Officer", "Extension Worker", "Farm Manager",
                  "Quality Control Officer", "Research Scientist"],
        "companies": ["NARI", "Rural Development", "Oil Palm Estates", "Coffee Industry",
                      "PNG Coffee Exports", "Trukai Farms", "SP Brewery (Barley)"],
        "locations": ["Highlands", "Momase", "Southern regions", "Rural PNG"]
    }
}

# Common PNG Location Aliases
LOCATION_ALIASES = {
    "pom": "Port Moresby",
    "pOM": "Port Moresby",
    "port moresby": "Port Moresby",
    "moresby": "Port Moresby",
    "ncd": "Port Moresby",
    "lae": "Lae",
    "hagen": "Mt Hagen",
    "mt hagen": "Mt Hagen",
    "mount hagen": "Mt Hagen",
    "goroka": "Goroka",
    "madang": "Madang",
    "kokopo": "Kokopo",
    "rabaul": "Rabaul",
    "enb": "East New Britain",
    "wewak": "Wewak",
    "vanimo": "Vanimo",
    "daru": "Daru",
    "alotau": "Alotau",
    "milne bay": "Milne Bay",
    "hiri": "Hiri",
    "central": "Central Province",
    "highlands": "Highlands Region",
    "momase": "Momase Region",
    "southern": "Southern Region",
    "new guinea islands": "New Guinea Islands",
    "ngi": "New Guinea Islands",
    "png": "Papua New Guinea",
    "papua new guinea": "Papua New Guinea",
    "anywhere": "Papua New Guinea",
    "all": "Papua New Guinea"
}

# Salary Ranges in PGK (Approximate)
SALARY_RANGES = {
    "entry": {"range": "15,000 - 35,000 PGK", "note": "0-2 years experience"},
    "mid": {"range": "35,000 - 80,000 PGK", "note": "2-5 years experience"},
    "senior": {"range": "80,000 - 150,000 PGK", "note": "5-10 years experience"},
    "executive": {"range": "150,000 - 500,000+ PGK", "note": "10+ years experience"},
    "specialized": {"range": "100,000 - 300,000 PGK", "note": "Mining/Oil/Gas expats or highly specialized"},
    "government": {"range": "20,000 - 100,000 PGK", "note": "Based on grade level"}
}


# ==========================================
# DOMAIN LISTS (Optimized)
# ==========================================

PNG_JOB_DOMAINS = [
    "pngjobseek.com", "pngwork.com", "findajobpng.com", "careerspng.com",
    "jobspng.com", "pngjobs.com", "employmentpng.com"
]

PNG_COMPANY_CAREERS = [
    "bsp.com.pg/careers", "kina.com.pg/careers", "oilsearch.com/careers",
    "digicel.com.pg/careers", "datec.com.pg/careers", "airniugini.com.pg/careers",
    "oktedi.com/careers", "newcrest.com/careers"
]

PNG_GOVERNMENT = [
    "dpm.gov.pg", "parliament.gov.pg", "psdm.gov.pg", "treasury.gov.pg"
]

PACIFIC_DOMAINS = [
    "seek.com.au", "au.indeed.com", "jora.com", "careerone.com.au",
    "seek.co.nz", "nz.indeed.com", "trademe.co.nz/jobs",
    "myjobfiji.com", "fijitimes.com/classifieds"
]

GLOBAL_DOMAINS = [
    "linkedin.com/jobs", "indeed.com", "glassdoor.com", "ziprecruiter.com",
    "weworkremotely.com", "remoteok.com", "unjobs.org", "reliefweb.int"
]


def _normalize_location(location: str) -> str:
    """Convert location aliases to standard names"""
    if not location:
        return "Papua New Guinea"
    loc_lower = location.lower().strip()
    return LOCATION_ALIASES.get(loc_lower, location)


def _detect_scope(location: str) -> dict:
    """Detect search scope based on location"""
    loc_lower = (location or "").lower()
    
    scopes = {
        "png": False,
        "pacific": False,
        "global": False,
        "specific_city": None
    }
    
    # PNG cities
    png_cities = ["port moresby", "lae", "mt hagen", "goroka", "madang", "kokopo", 
                  "wewak", "vanimo", "alotau", "daru", "hagen", "moresby", "pom", "ncd"]
    
    for city in png_cities:
        if city in loc_lower:
            scopes["png"] = True
            scopes["specific_city"] = _normalize_location(location)
            return scopes
    
    # Pacific
    if any(k in loc_lower for k in ["australia", "nz", "new zealand", "fiji", "samoa", 
                                      "vanuatu", "solomon", "pacific", "sydney", "auckland",
                                      "brisbane", "melbourne"]):
        scopes["pacific"] = True
        return scopes
    
    # Global
    if any(k in loc_lower for k in ["global", "remote", "international", "worldwide", "usa", "uk"]):
        scopes["global"] = True
        return scopes
    
    # Default to PNG
    scopes["png"] = True
    return scopes


def _is_valid_job_title(title: str) -> bool:
    """Filter out non-job listings"""
    if not title:
        return False
    
    title_lower = title.lower()
    
    # Skip non-job pages
    skip_words = ["login", "sign up", "register", "privacy", "terms of", "cookie", 
                  "about us", "contact us", "home page", "404", "not found",
                  "how it works", "pricing", "blog", "news", "sitemap"]
    
    if any(word in title_lower for word in skip_words):
        return False
    
    # Must contain job-related words
    job_words = ["job", "vacancy", "career", "position", "role", "opportunity",
                 "hiring", "recruit", "officer", "manager", "engineer", "driver",
                 "nurse", "doctor", "teacher", "developer", "assistant", "specialist",
                 "director", "analyst", "consultant", "scientist", "coordinator",
                 "supervisor", "technician", "administrator", "accountant", "clerk",
                 "executive", "intern", "graduate", "apprentice", "tradesman"]
    
    return any(word in title_lower for word in job_words)


def _extract_domain(url: str) -> str:
    """Extract clean domain from URL"""
    try:
        return url.split("/")[2].replace("www.", "")
    except:
        return ""


def _format_job_result(item: dict, index: int) -> str:
    """Format a single job result"""
    title = item.get('title', 'Unknown Position')
    url = item.get('url', '')
    domain = _extract_domain(url)
    snippet = item.get('content', '')[:100] if item.get('content') else ''
    
    # Clean up snippet
    if snippet:
        snippet = snippet.replace("\n", " ").strip()
        if len(snippet) > 100:
            snippet = snippet[:100] + "..."
    
    result = f"*{index}. {title}*\n"
    result += f"📁 Source: {domain}\n"
    if snippet:
        result += f"📝 {snippet}\n"
    result += f"🔗 {url}"
    
    return result


# ==========================================
# TOOL 1: SEARCH JOBS (Enhanced)
# ==========================================

@tool
def search_jobs(role: str, location: str = "Papua New Guinea") -> str:
    """
    Search for jobs based on role and location. Use this when user wants to find jobs.
    
    Args:
        role: The job title or role to search for (e.g., "Accountant", "Mining Engineer")
        location: Where to search (e.g., "Port Moresby", "Lae", "Papua New Guinea", "Australia")
    
    Returns:
        Formatted list of job listings with links
    """
    if not role:
        return "⚠️ Please specify what job role you're looking for."
    
    normalized_location = _normalize_location(location)
    scopes = _detect_scope(location)
    
    all_results = []
    seen_urls = set()
    
    # Build search queries
    search_queries = [
        f"{role} job vacancy {normalized_location}",
        f"{role} employment {normalized_location}",
        f"hire {role} {normalized_location}"
    ]
    
    # Tier 1: PNG Search
    if scopes["png"]:
        print(f"🔍 [PNG] Searching for: {role} in {normalized_location}")
        
        for query in search_queries[:2]:  # Use first 2 queries
            try:
                res = tavily.search(
                    query=query,
                    search_depth="advanced",
                    include_domains=PNG_JOB_DOMAINS + PNG_COMPANY_CAREERS + PNG_GOVERNMENT,
                    max_results=10
                )
                
                for item in res.get('results', []):
                    url = item.get('url', '')
                    if url not in seen_urls and _is_valid_job_title(item.get('title', '')):
                        seen_urls.add(url)
                        all_results.append(item)
            except Exception as e:
                print(f"❌ PNG search error: {e}")
        
        # General PNG search if limited results
        if len(all_results) < 3:
            try:
                res = tavily.search(
                    query=f"{role} jobs PNG Papua New Guinea 2024",
                    search_depth="basic",
                    max_results=10
                )
                for item in res.get('results', []):
                    url = item.get('url', '')
                    if url not in seen_urls and _is_valid_job_title(item.get('title', '')):
                        seen_urls.add(url)
                        all_results.append(item)
            except Exception as e:
                print(f"❌ General PNG search error: {e}")
    
    # Tier 2: Pacific Search
    if scopes["pacific"]:
        print(f"🔍 [PACIFIC] Searching for: {role}")
        try:
            res = tavily.search(
                query=f"{role} job vacancy Pacific Australia New Zealand",
                search_depth="basic",
                include_domains=PACIFIC_DOMAINS,
                max_results=8
            )
            for item in res.get('results', []):
                url = item.get('url', '')
                if url not in seen_urls and _is_valid_job_title(item.get('title', '')):
                    seen_urls.add(url)
                    all_results.append(item)
        except Exception as e:
            print(f"❌ Pacific search error: {e}")
    
    # Tier 3: Global Search
    if scopes["global"]:
        print(f"🔍 [GLOBAL] Searching for: {role}")
        try:
            res = tavily.search(
                query=f"{role} remote jobs international",
                search_depth="basic",
                include_domains=GLOBAL_DOMAINS,
                max_results=8
            )
            for item in res.get('results', []):
                url = item.get('url', '')
                if url not in seen_urls and _is_valid_job_title(item.get('title', '')):
                    seen_urls.add(url)
                    all_results.append(item)
        except Exception as e:
            print(f"❌ Global search error: {e}")
    
    # Format results
    if not all_results:
        return (
            f"🤷 *No jobs found for '{role}' in {normalized_location}*\n\n"
            "💡 *Try these tips:*\n"
            "• Use different keywords (e.g., 'Accountant' vs 'Finance Officer')\n"
            "• Try a broader location (e.g., 'Papua New Guinea')\n"
            "• Check spelling of job title\n\n"
            "🔍 *Popular searches:* Accounting, Mining, Nursing, IT, Teaching, Driving"
        )
    
    # Limit to top 7 results
    all_results = all_results[:7]
    
    # Build response
    location_label = normalized_location if scopes["specific_city"] else "Papua New Guinea"
    if scopes["pacific"]:
        location_label = "Pacific Region"
    if scopes["global"]:
        location_label = "Global/Remote"
    
    response = f"🇵🇬 *JOBS: {role.upper()}*\n"
    response += f"📍 *Location: {location_label}*\n"
    response += f"📋 *Found: {len(all_results)} results*\n"
    response += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, item in enumerate(all_results, 1):
        response += _format_job_result(item, i)
        response += "\n\n"
    
    response += "━━━━━━━━━━━━━━━━━━━\n"
    response += "💾 Reply *'save [number]'* to save a job\n"
    response += "🔄 Reply *'more'* for additional results"
    
    return response


# ==========================================
# TOOL 2: EXPLORE CATEGORIES
# ==========================================

@tool
def explore_categories() -> str:
    """
    Show all available job categories in PNG. Use when user asks what jobs are available
    or wants to explore options.
    """
    response = "📋 *PNG JOB CATEGORIES*\n"
    response += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, (category, info) in enumerate(PNG_JOB_CATEGORIES.items(), 1):
        roles_preview = ", ".join(info["roles"][:3])
        response += f"*{i}. {category}*\n"
        response += f"   _{roles_preview}..._\n\n"
    
    response += "━━━━━━━━━━━━━━━━━━━\n"
    response += "💡 *Reply with a category number or name to see jobs*\n"
    response += "🔍 Or tell me your role (e.g., 'Find me mining jobs')"
    
    return response


# ==========================================
# TOOL 3: GET CATEGORY JOBS
# ==========================================

@tool
def get_category_jobs(category_name: str) -> str:
    """
    Get detailed info about a specific job category including sample roles and companies.
    Use when user selects a category or asks about a specific industry.
    
    Args:
        category_name: Name of the category (e.g., "Mining", "Banking", "Healthcare")
    """
    # Find matching category
    matched_category = None
    for cat in PNG_JOB_CATEGORIES:
        if category_name.lower() in cat.lower() or cat.lower() in category_name.lower():
            matched_category = cat
            break
    
    if not matched_category:
        # Try partial match
        for cat in PNG_JOB_CATEGORIES:
            words = category_name.lower().split()
            if any(word in cat.lower() for word in words if len(word) > 3):
                matched_category = cat
                break
    
    if not matched_category:
        return f"❌ Category '{category_name}' not found.\n\nReply *'categories'* to see all options."
    
    info = PNG_JOB_CATEGORIES[matched_category]
    
    response = f"💼 *{matched_category.upper()}*\n"
    response += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Sample Roles
    response += "*📌 Common Roles:*\n"
    for role in info["roles"][:5]:
        response += f"   • {role}\n"
    response += "\n"
    
    # Key Employers
    employers = info.get("companies") or info.get("departments") or info.get("organizations") or info.get("employers") or []
    if employers:
        response += "*🏢 Key Employers:*\n"
        for emp in employers[:5]:
            response += f"   • {emp}\n"
        response += "\n"
    
    # Locations
    if info.get("locations"):
        response += f"*📍 Locations:*\n   {', '.join(info['locations'][:5])}\n\n"
    
    response += "━━━━━━━━━━━━━━━━━━━\n"
    response += f"🔍 *Want to search {matched_category} jobs?*\n"
    response += f"   Reply: *'find [role] in [location]'*\n"
    response += f"   Example: *'find mining engineer in Port Moresby'*"
    
    return response


# ==========================================
# TOOL 4: SAVE JOB
# ==========================================

@tool
def save_job(phone_number: str, job_number: int, job_url: str, job_title: str) -> str:
    """
    Save a job for the user to view later. User specifies job number from search results.
    
    Args:
        phone_number: User's phone number
        job_number: The number of the job from search results
        job_url: The URL of the job posting
        job_title: The title of the job
    """
    job_data = {
        "title": job_title,
        "url": job_url,
        "source": _extract_domain(job_url) if job_url else "Unknown"
    }
    
    result = save_job_for_user(phone_number, job_data)
    
    if result > 0:
        return (
            f"✅ *Job Saved!*\n\n"
            f"📌 *{job_title}*\n"
            f"📁 Saved to your list\n\n"
            f"💡 Reply *'my jobs'* to see all saved jobs\n"
            f"💡 Reply *'apply {job_number}'* when you've applied"
        )
    elif result == -1:
        return "⚠️ This job is already saved in your list."
    else:
        return "❌ Could not save job. Please try again."


# ==========================================
# TOOL 5: VIEW SAVED JOBS
# ==========================================

@tool
def view_saved_jobs(phone_number: str) -> str:
    """
    Show all jobs the user has saved. Use when user asks 'my jobs' or 'saved jobs'.
    
    Args:
        phone_number: User's phone number
    """
    jobs = get_saved_jobs(phone_number)
    
    if not jobs:
        return (
            "📂 *No saved jobs yet*\n\n"
            "💡 When you search for jobs, reply *'save [number]'* to save them here.\n\n"
            "🔍 Ready to search? Tell me what job you're looking for!"
        )
    
    response = f"📂 *YOUR SAVED JOBS ({len(jobs)})*\n"
    response += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, job in enumerate(jobs[:10], 1):
        status = "✅ Applied" if job.get("is_applied") else "📋 Pending"
        response += f"*{i}. {job['title']}*\n"
        response += f"   📁 {job.get('source', 'Unknown')} • {status}\n"
        response += f"   📅 Saved: {job['saved_at']}\n"
        response += f"   🔗 {job['url']}\n\n"
    
    response += "━━━━━━━━━━━━━━━━━━━\n"
    response += "💡 Reply *'apply [number]'* to mark as applied\n"
    response += "💡 Reply *'clear jobs'* to remove all saved jobs"
    
    return response


# ==========================================
# TOOL 6: GET SALARY INFO
# ==========================================

@tool
def get_salary_info(role: str = None, experience_level: str = None) -> str:
    """
    Get salary information for PNG jobs. Use when user asks about pay, salary, or wages.
    
    Args:
        role: Optional specific role to estimate salary for
        experience_level: Optional - 'entry', 'mid', 'senior', 'executive'
    """
    response = "💰 *PNG SALARY GUIDE*\n"
    response += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    if role and experience_level:
        # Specific estimate
        level_data = SALARY_RANGES.get(experience_level.lower(), SALARY_RANGES["mid"])
        response += f"*{role}* ({experience_level})\n\n"
        response += f"💵 Estimated: *{level_data['range']}* per year\n"
        response += f"📝 {level_data['note']}\n\n"
        response += "⚠️ Note: Actual salaries vary by employer, qualifications, and negotiation."
    else:
        # General guide
        response += "*By Experience Level:*\n\n"
        
        for level, data in SALARY_RANGES.items():
            response += f"📌 *{level.upper()}*\n"
            response += f"   💵 {data['range']}/year\n"
            response += f"   📝 {data['note']}\n\n"
        
        response += "━━━━━━━━━━━━━━━━━━━\n"
        response += "💡 *For specific role estimates, tell me:*\n"
        response += "   'Salary for [role] at [level]'\n"
        response += "   Example: 'Salary for engineer at senior level'"
    
    return response


# ==========================================
# TOOL 7: GET JOB SEARCH TIPS
# ==========================================

@tool
def get_job_tips(topic: str = "general") -> str:
    """
    Provide job search tips and advice for PNG job seekers. 
    Use when user asks for help with job hunting, CV, interviews, etc.
    
    Args:
        topic: The topic - 'cv', 'interview', 'application', 'general', 'linkedin'
    """
    tips = {
        "cv": (
            "📝 *CV/RESUME TIPS FOR PNG*\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *DO:*\n"
            "• Keep it to 2-3 pages maximum\n"
            "• Include your phone number and email\n"
            "• List education with institution names\n"
            "• Show specific achievements with numbers\n"
            "• Include PNG-relevant skills (local languages, etc.)\n"
            "• Use a professional email address\n\n"
            "❌ *DON'T:*\n"
            "• Include photo (unless requested)\n"
            "• List every job - focus on recent/relevant\n"
            "• Use fancy fonts or colors\n"
            "• Include personal info (marital status, etc.)\n\n"
            "📱 *Need help?* Tell me your role and I can suggest what to highlight!"
        ),
        "interview": (
            "🎯 *INTERVIEW TIPS FOR PNG*\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "*Before the Interview:*\n"
            "• Research the company thoroughly\n"
            "• Prepare answers for common questions\n"
            "• Plan your travel - arrive 15 mins early\n"
            "• Dress professionally\n\n"
            "*During the Interview:*\n"
            "• Greet politely (PNG style matters!)\n"
            "• Maintain eye contact and sit straight\n"
            "• Answer questions clearly and concisely\n"
            "• Ask thoughtful questions about the role\n"
            "• Show enthusiasm for the position\n\n"
            "*Common Questions to Prepare:*\n"
            "• 'Tell me about yourself'\n"
            "• 'Why do you want this job?'\n"
            "• 'What are your strengths/weaknesses?'\n"
            "• 'Where do you see yourself in 5 years?'"
        ),
        "application": (
            "📋 *JOB APPLICATION TIPS*\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "*Where to Apply:*\n"
            "• Company websites (careers page)\n"
            "• PNG job sites (pngjobseek.com, etc.)\n"
            "• Email directly to HR departments\n"
            "• Walk-in applications (common in PNG)\n"
            "• Government jobs: psdm.gov.pg\n\n"
            "*Application Tips:*\n"
            "• Customize your CV for each application\n"
            "• Write a tailored cover letter\n"
            "• Follow application instructions exactly\n"
            "• Apply early - don't wait for deadlines\n"
            "• Follow up after 1-2 weeks\n\n"
            "*Documents to Have Ready:*\n"
            "• Updated CV/Resume\n"
            "• Cover Letter\n"
            "• Certificates & Transcripts\n"
            "• ID/Passport\n"
            "• Reference contacts"
        ),
        "linkedin": (
            "💼 *LINKEDIN TIPS FOR PNG*\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "*Why LinkedIn Matters:*\n"
            "• Many PNG companies now recruit on LinkedIn\n"
            "• Connect with recruiters directly\n"
            "• See unlisted job opportunities\n"
            "• Build your professional brand\n\n"
            "*Profile Tips:*\n"
            "• Use a professional headshot\n"
            "• Write a compelling headline (not just job title)\n"
            "• Summary should tell your story\n"
            "• List all relevant experience\n"
            "• Get recommendations from colleagues\n"
            "• Add skills and get endorsements\n\n"
            "*Networking Tips:*\n"
            "• Connect with PNG professionals\n"
            "• Follow companies you want to work for\n"
            "• Engage with posts (comment thoughtfully)\n"
            "• Share relevant content\n"
            "• Use 'Open to Work' feature"
        ),
        "general": (
            "🚀 *JOB SEARCH STRATEGY FOR PNG*\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "*1. Know What You Want*\n"
            "   • Define your target role\n"
            "   • Know your preferred location\n"
            "   • Be clear on salary expectations\n\n"
            "*2. Prepare Your Materials*\n"
            "   • Update your CV\n"
            "   • Prepare cover letter template\n"
            "   • Gather certificates\n\n"
            "*3. Search Strategically*\n"
            "   • Check job sites daily\n"
            "   • Network with contacts\n"
            "   • Follow company social media\n"
            "   • Attend job fairs\n\n"
            "*4. Apply Effectively*\n"
            "   • Tailor each application\n"
            "   • Apply to 5-10 jobs per week\n"
            "   • Follow up on applications\n\n"
            "*5. Stay Positive*\n"
            "   • Job search takes time\n"
            "   • Learn from rejections\n"
            "   • Keep improving your skills"
        )
    }
    
    topic_lower = topic.lower()
    
    if "cv" in topic_lower or "resume" in topic_lower:
        return tips["cv"]
    elif "interview" in topic_lower:
        return tips["interview"]
    elif "apply" in topic_lower or "application" in topic_lower:
        return tips["application"]
    elif "linkedin" in topic_lower:
        return tips["linkedin"]
    else:
        return tips["general"]


# ==========================================
# TOOL 8: UPDATE PROFILE
# ==========================================

@tool
def update_profile(phone_number: str, field: str, value: str) -> str:
    """
    Update user profile information. Use when user shares info about themselves
    like their name, location, skills, or job preferences.
    
    Args:
        phone_number: User's phone number
        field: What to update - 'name', 'location', 'role', 'skills', 'experience', 'education'
        value: The new value for the field
    """
    field_mapping = {
        "name": "name",
        "location": "location",
        "role": "target_roles",
        "skills": "skills",
        "experience": "experience_level",
        "education": "education",
        "qualification": "qualifications"
    }
    
    db_field = field_mapping.get(field.lower())
    if not db_field:
        return f"❌ Unknown field: {field}\n\nValid fields: name, location, role, skills, experience, education"
    
    # Handle list fields
    if db_field in ["target_roles", "skills", "qualifications"]:
        # Get existing values and append
        profile = get_user_profile(phone_number)
        existing = profile.get(db_field, [])
        if value not in existing:
            existing.append(value)
        updates = {db_field: existing}
    else:
        updates = {db_field: value}
    
    success = update_user_profile(phone_number, updates)
    
    if success:
        field_names = {
            "name": "Name",
            "location": "Location", 
            "target_roles": "Target Roles",
            "skills": "Skills",
            "experience_level": "Experience Level",
            "education": "Education",
            "qualifications": "Qualifications"
        }
        display_name = field_names.get(db_field, field)
        return f"✅ *Updated!* {display_name} has been saved.\n\n💡 This helps me find better jobs for you!"
    else:
        return "⚠️ Could not save update. Please try again."


# Export all tools
ALL_TOOLS = [
    search_jobs,
    explore_categories,
    get_category_jobs,
    save_job,
    view_saved_jobs,
    get_salary_info,
    get_job_tips,
    update_profile
]