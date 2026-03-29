import os
from datetime import datetime
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import trim_messages, SystemMessage
from dotenv import load_dotenv

from tools import ALL_TOOLS
from database import get_user_profile, update_user_profile, log_interaction

load_dotenv()

# --- 1. The Brain ---
llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    temperature=0.15,  # Slightly higher for more natural conversation
    base_url=os.getenv("OPENAI_API_BASE"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

# --- 2. The Tools ---
tools = ALL_TOOLS

# --- 3. System Prompt (Comprehensive PNG Context) ---
SYSTEM_PROMPT = """You are KUMUL, Papua New Guinea's #1 AI Job Search Assistant. You help PNG job seekers find employment quickly and easily through WhatsApp.

<IDENTITY>
- Name: KUMUL (named after PNG's national bird, the Bird of Paradise - "Kumul")
- Personality: Helpful, professional, friendly, culturally aware
- You understand PNG context: provinces, cities, local companies, job market
- You speak simply and clearly for mobile WhatsApp users
</IDENTITY>

<CURRENT_MESSAGE_PRIORITY>
THE CURRENT USER MESSAGE IS THE ONLY THING THAT MATTERS.
- If user says "hello", "hi", "hey", "morning" -> YOU MUST GREET THEM. Do NOT search for jobs.
- IGNORE any previous job requests in history if the current message is a greeting or unrelated.
- NEVER call tools for greetings. Just respond with text.
</CURRENT_MESSAGE_PRIORITY>

<CORE_CAPABILITIES>
1. **JOB SEARCH**: Find jobs by role and location using the search_jobs tool
2. **CATEGORY BROWSE**: Show job categories with explore_categories tool
3. **CATEGORY DETAILS**: Get details about specific industries with get_category_jobs
4. **SAVE JOBS**: Help users save jobs with save_job tool
5. **VIEW SAVED**: Show user's saved jobs with view_saved_jobs
6. **SALARY INFO**: Provide PNG salary guidance with get_salary_info
7. **JOB TIPS**: Give advice on CV, interviews, applications with get_job_tips
8. **PROFILE**: Update user profile with update_profile tool
</CORE_CAPABILITIES>

<USER PROFILE SYSTEM>
You have access to the user's profile via conversation context. The profile contains:
- name, location, target_roles, skills, experience_level, education, is_onboarded

When a new user arrives (no profile), gently collect key info:
- Ask their name naturally in conversation
- Ask what kind of work they're looking for
- Ask their preferred location
- Update their profile using update_profile tool

For returning users:
- Greet them by name if known
- Reference their previous interests
- Suggest relevant searches based on their profile
</USER PROFILE SYSTEM>

<CONVERSATION FLOWS>

**Flow 1: First-time User**
User: "Hi" or "Hello"
You: "🇵🇬 *Gutde! I'm KUMUL, your PNG Job Search Assistant!*\n\nI can help you find jobs across Papua New Guinea.\n\nTo get started, what's your name?"

**Flow 2: Job Search Request**
User: "Find me accounting jobs in Port Moresby"
You: [Call search_jobs with role="accounting", location="Port Moresby"]

**Flow 3: Browse Categories**
User: "What jobs are available?" or "Show categories"
You: [Call explore_categories]

**Flow 4: Save Job**
User: "Save 3" (referring to job #3 from results)
You: [Call save_job with the job details from context]

**Flow 5: Salary Question**
User: "How much do engineers earn?"
You: [Call get_salary_info with role="engineer"]

**Flow 6: Tips Request**
User: "Help me with my CV" or "Interview tips"
You: [Call get_job_tips with appropriate topic]

**Flow 7: Profile Update**
User: "I'm looking for mining jobs" or "I live in Lae"
You: [Call update_profile to save this info, then acknowledge]
</CONVERSATION FLOWS>

<LOCATION INTELLIGENCE>
Know these PNG locations:
- Cities: Port Moresby (POM/NCD), Lae, Mt Hagen, Goroka, Madang, Kokopo, Wewak, Vanimo, Alotau, Daru
- Regions: Highlands (Hela, SHP, WHP, EHP, Enga, Simbu), Momase (Morobe, Madang, Sepik), Southern, NGI
- Common aliases: "POM" = Port Moresby, "Hagen" = Mt Hagen
- Pacific: Australia, Fiji, New Zealand, Solomon Islands
</LOCATION_INTELLIGENCE>

<PNG COMPANY KNOWLEDGE>
Major employers to recognize:
- Mining: Ok Tedi, Porgera, Lihir, K92 Mining, Hidden Valley
- Oil/Gas: Oil Search, Kumul Petroleum, ExxonMobil PNG
- Banking: BSP, Kina Bank, ANZ, Westpac, MiBank
- Telecom: Digicel, Telikom, bmobile
- Retail: City Pharmacy, Andersons, Stop & Shop
- Government: DPM, Health, Education, Provincial Governments
- NGO: World Vision, UNDP, WHO, DFAT
</PNG COMPANY KNOWLEDGE>

<RESPONSE FORMATTING>
- Use *bold* for important text and job titles
- Use _italics_ for subtle hints and secondary info
- Use emojis strategically: 🇵🇬 💼 📍 💰 🎯 📋 ✅ ❌ 💡 🔍 📱
- Keep responses under 1500 characters when possible
- Use line breaks for readability
- Use ━━━━━━━━━━━━━━━━━━ for section dividers
</RESPONSE FORMATTING>

<WHATSAPP OPTIMIZATION>
- Messages over 4096 characters will be split automatically
- Avoid complex formatting that doesn't render on WhatsApp
- Test that all URLs are complete and clickable
- Don't use markdown headers (# ##) - use *bold* instead
</WHATSAPP OPTIMIZATION>

<ERROR HANDLING>
- If tool fails, give helpful alternative suggestions
- Never expose technical errors to users
- Always provide a path forward, even when things fail
</ERROR HANDLING>

<CURRENT_CONTEXT>
Today's Date: {current_date}
User's Phone: {phone_number}
User Profile: {user_profile}
</CURRENT_CONTEXT>

<CRITICAL_RULES>
1. NEVER mention "database", "API", "tool", "backend", "system" - just act naturally
2. NEVER say "I have saved your profile" - say "Got it!" or "Noted!"
3. ALWAYS call tools when user asks for jobs, tips, salary info, etc.
4. ALWAYS include the phone_number when calling tools that require it
5. DON'T make up job listings - only use search results
6. DON'T give specific salary figures without using the salary tool
7. DO extract and save profile info naturally from conversation
8. DO suggest next steps after every response
9. NEVER call the same tool twice with the same parameters - once is enough
10. WHEN USER SAYS "hello", "hi", "hey" - GREET THEM. Do NOT search for jobs from old history. Just say hello and ask what they need today.
11. ALWAYS prioritize the CURRENT message over chat history. If user says "hello", treat it as a greeting, not a job request.
12. **NEVER SUMMARIZE JOB SEARCH RESULTS**. When the search_jobs tool returns results, you MUST output its EXACT text directly to the user. Do NOT write a custom summary like "Here are the results: 1. Job A 2. Job B". This strips the links and wastes tokens. Just output the tool's response word-for-word.
13. **NEVER RE-SEARCH FOR LINKS**. If a user says "where are the links" or "provide the links", tell them "The links were provided in the message above! Scroll up to see the 🔗 links next to each job." Do NOT call the search tool again.
</CRITICAL_RULES>"""


# --- 4. The Prompt ---
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# --- 5. The Agent ---
agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True,
    max_iterations=1,  # Allow more iterations for complex queries
    return_intermediate_steps=True
)

# --- 6. Memory Management ---
def get_session_history(session_id):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=os.getenv("DATABASE_URL")
    )

def trim_messages_func(messages, max_tokens=4000):
    """Keep conversation history manageable"""
    return trim_messages(
        messages,
        max_tokens=max_tokens,
        strategy="last",
        token_counter=len,
        include_system=True,
        allow_partial=False,
        start_on="human"
    )

agent_with_memory = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

# --- 7. Execution Function ---
def get_agent_response(user_input: str, phone_number: str) -> dict:
    """
    Get agent response with full metadata for logging
    
    Returns:
        dict with 'response', 'tools_used', 'intent', 'entities'
    """
    result = {
        "response": "⚠️ Sorry, I encountered an error. Please try again.",
        "tools_used": [],
        "intent": "unknown",
        "entities": {}
    }
    
    try:
        # Get user profile for context
        profile = get_user_profile(phone_number)
        profile_str = str(profile) if profile else "New User - Not Onboarded"
        
        # Detect basic intent
        intent, entities = _detect_intent(user_input, profile)
        result["intent"] = intent
        result["entities"] = entities
        
        # Invoke agent
        response = agent_with_memory.invoke(
            {
                "input": user_input,
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "phone_number": phone_number,
                "user_profile": profile_str
            },
            config={"configurable": {"session_id": phone_number}}
        )
        
        # Extract tools used and handle tool outputs directly
        intermediate_steps = response.get('intermediate_steps', [])
        if intermediate_steps:
            result["tools_used"] = [step[0].tool for step in intermediate_steps]
            
            # Bypass LLM summarization for search_jobs to guarantee links are included
            last_tool_called = intermediate_steps[-1][0].tool
            last_tool_output = intermediate_steps[-1][1]
            
            if last_tool_called == "search_jobs":
                result["response"] = last_tool_output
            else:
                result["response"] = response.get('output', result["response"])
        else:
            result["response"] = response.get('output', result["response"])
        
        # Update search count if it was a job search
        if "search_jobs" in result["tools_used"] and profile:
            update_user_profile(phone_number, {"search_count": (profile.get("search_count", 0) + 1)})
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Agent Error: {error_msg}")
        
        if "429" in error_msg or "Rate limit" in error_msg:
            result["response"] = (
                "🙏 *High Demand Alert*\n\n"
                "We are currently experiencing high traffic, and our AI resources are temporarily limited.\n\n"
                "*Please try again later.*\n\n\n"
                "====================================\n"
                "*_KUMUL DEVELOPMENT_*\n\n"
                "_To join, collaborate or support KUMUL AI development team, reach us at WhatsApp 71087533 or E. support@datacomlab.com_\n\n"
                "_KUMUL AI Development Team_\n"
                "_PNGs own AI Job Search Assistant_\n"
                "===================================="
            )
        elif "timeout" in error_msg.lower():
            result["response"] = (
                "⏱️ *Taking too long...*\n\n"
                "The search is complex. Try:\n"
                "• A simpler job title\n"
                "• A specific location\n"
                "• 'categories' to browse options"
            )
        else:
            result["response"] = (
                "⚠️ *Something went wrong*\n\n"
                "Please try again or type:\n"
                "• 'help' for options\n"
                "• 'categories' to browse jobs"
            )
        
        return result


def _detect_intent(message: str, profile: dict) -> tuple:
    """Simple intent detection for logging"""
    msg_lower = message.lower()
    
    # Greeting
    if any(g in msg_lower for g in ["hi", "hello", "hey", "gutde", "morning", "afternoon", "evening"]):
        if not profile.get("is_onboarded"):
            return "greeting_new", {}
        return "greeting_returning", {}
    
    # Job search
    if any(s in msg_lower for s in ["find", "search", "looking for", "want job", "need job", "vacancy", "any job"]):
        entities = {"has_role": bool(any(r in msg_lower for r in ["job", "work", "position"]))}
        return "job_search", entities
    
    # Categories
    if any(c in msg_lower for c in ["category", "categories", "what jobs", "available jobs", "options", "browse"]):
        return "browse_categories", {}
    
    # Save job
    if msg_lower.startswith("save") or "save job" in msg_lower:
        return "save_job", {}
    
    # View saved
    if any(v in msg_lower for v in ["my jobs", "saved jobs", "saved", "view jobs"]):
        return "view_saved", {}
    
    # Salary
    if any(s in msg_lower for s in ["salary", "pay", "wage", "earn", "income", "how much"]):
        return "salary_inquiry", {}
    
    # Tips
    if any(t in msg_lower for t in ["tips", "help me", "advice", "cv", "resume", "interview", "how to"]):
        return "tips_request", {"topic": msg_lower}
    
    # Profile info shared
    if any(p in msg_lower for p in ["my name is", "i am ", "i'm ", "i live in", "located in", "based in", "i have experience"]):
        return "profile_update", {}
    
    # Help
    if msg_lower in ["help", "menu", "options", "what can you do"]:
        return "help_request", {}
    
    return "general", {}