import os
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import trim_messages
from tools import search_png_jobs, save_user_profile
from dotenv import load_dotenv

load_dotenv()

# --- 1. The Brain (Llama 3.3 70B) ---
llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    temperature=0.1, # Low temp for logic, high temp for creativity. We want logic here.
    base_url=os.getenv("OPENAI_API_BASE"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

# --- 2. The Tools ---
tools = [search_png_jobs, save_user_profile]

# --- 3. The "Mindscape" (System Prompt) ---
# This prompt is engineered to prevent hallucination and enforce intelligence.
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are KUMUL, the most advanced Job Search AI in Papua New Guinea.

    <CORE_IDENTITY>
    You are professional, concise, and deeply knowledgeable about the PNG job market.
    You understand locations like Port Moresby, Lae, Mt Hagen, and industries like Mining, Healthcare, and Driving.
    You can understand Tok Pisin context if used.
    </CORE_IDENTITY>

    < STRICT_RULES >
    1. **NO HALLUCINATIONS**:
       - You do NOT invent jobs.
       - If the `search_png_jobs` tool returns "ZERO_RESULTS", you politely tell the user no jobs were found and suggest they try a different keyword. You do NOT apologize excessively.
    
    2. **DATA EXTRACTION**:
       - You must identify the user's Profession and Location.
       - If the user says "I am a driver in Lae", you MUST call the `save_user_profile` tool.
       - If the user's profile (below) is empty, ask for their profession before searching.

    3. **SEARCH LOGIC**:
       - ONLY call `search_png_jobs` when explicitly asked.
       - Always pass the detected Location and Profession to the tool.
       - **CRITICAL**: When the tool returns a list, you must output the EXACT list to the user. Do not summarize the list into a sentence. The user needs the links.

    4. **PRIVACY**:
       - NEVER mention "database", "SQL", or "saving to backend".
       - Just say "I've noted that you are a [Profession]."

    5. **WHATSAPP_FORMATTING**:
       - Use bold *text* for titles.
       - Use emojis (🇵🇬, 💼, 📍).
       - Keep responses short enough for a phone screen.
    </STRICT_RULES>

    <USER_CONTEXT>
    Phone: {phone_number}
    Current Profession: {user_profession}
    Current Location: {user_location}
    </USER_CONTEXT>

    <CURRENT_DATE>
    Today's Date: {current_date}
    </CURRENT_DATE>
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# --- 4. The Agent ---
agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True,
    max_iterations=5 # Prevent infinite loops
)

# --- 5. Memory Management (Prevent Bloating) ---
# We trim old messages to keep the bot fast and cheap
def get_session_history(session_id):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=os.getenv("DATABASE_URL")
    )

# Logic to trim history to last 10 messages (5 turns)
def trim_history(messages):
    return trim_messages(
        messages,
        max_tokens=2000,
        strategy="last",
        token_counter=llm,
        include_system=True
    )

agent_with_memory = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

# --- 6. The Execution Function ---
def get_agent_response(user_input, phone_number, user_profile):
    from datetime import datetime
    
    profession = user_profile.profession if user_profile and user_profile.profession else "Unknown"
    location = user_profile.location if user_profile and user_profile.location else "Unknown"

    try:
        response = agent_with_memory.invoke(
            {
                "input": user_input,
                "phone_number": phone_number,
                "user_profession": profession,
                "user_location": location,
                "current_date": datetime.now().strftime("%Y-%m-%d")
            },
            config={"configurable": {"session_id": phone_number}}
        )
        return response['output']
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Agent Error: {error_msg}")
        
        # For ANY error (Rate limit, API issue, etc), we return the polite donation message.
        # This ensures the user always sees a professional response if the bot's brain fails.
        return (
            "🙏 *High Demand Alert*\n\n"
            "We are currently experiencing high traffic, and our AI resources are temporarily limited.\n\n"
            "To keep *KUMUL* running smoothly and helping Papua New Guineans find jobs, we need your support!\n\n"
            "☕ *Support us here:*\n"
            "https://ko-fi.com/kumulbot/goal?g=4\n\n" 
            "Please try again later.\n\n"
            "====================================\n"
            "*_KUMUL DEVELOPMENT_*\n\n"
            "_To join, collaborate or support KUMUL AI development team, reach us at WhatsApp 71087533 or E. support@datacomlab.com_\n\n"
            "_KUMUL AI Development Team_\n"
            "_PNGs own AI Job Search Assistant_\n"
            "===================================="
        )