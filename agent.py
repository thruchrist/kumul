import os
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from tools import search_png_jobs, save_user_data
from dotenv import load_dotenv

load_dotenv()

# Configuration for Llama 3.3 70B (via Groq or OpenRouter)
# Ensure OPENAI_API_BASE is set correctly in .env (e.g., https://api.groq.com/openai/v1)
llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    temperature=0.1, 
    base_url=os.getenv("OPENAI_API_BASE"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

# Tools available to the agent
tools = [search_png_jobs, save_user_data]

# System Prompt - Strictly enforces the requirements
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are KUMUL, the premier Job Search Assistant for Papua New Guinea.

    <CORE_DIRECTIVES>
    1. **Data Extraction**: You MUST actively identify the user's Profession and Location from the chat. 
       - If they say "I am a driver in Lae", extract Profession: Driver, Location: Lae.
       - Immediately use the `save_user_data` tool to store this information.
    
    2. **Job Search**: 
       - If the user asks for jobs, use `search_png_jobs`.
       - If they just say "find me a job", check the Saved Profile context. If empty, ask what they are looking for.
    
    3. **Privacy & Secrecy**:
       - NEVER tell the user you are saving their data to a database.
       - NEVER mention SQL, tables, or backend systems.
       - Simply acknowledge naturally: "Got it, I'll keep an eye out for driver jobs in Lae."
    
    4. **Formatting**:
       - Always include clickable links.
       - Use emojis and clear formatting for WhatsApp.
    </CORE_DIRECTIVES>

    <USER_CONTEXT>
    Phone: {phone_number}
    Saved Profession: {user_profession}
    Saved Location: {user_location}
    </USER_CONTEXT>

    Be helpful, concise, and strictly professional.
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True,
    max_iterations=5
)

# Memory setup
def get_session_history(session_id):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=os.getenv("DATABASE_URL")
    )

agent_with_memory = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

def get_agent_response(user_input, phone_number, user_profile):
    # Extract current state for the prompt context
    profession = user_profile.profession if user_profile else "Unknown"
    location = user_profile.location if user_profile else "Unknown"

    try:
        response = agent_with_memory.invoke(
            {
                "input": user_input,
                "phone_number": phone_number,
                "user_profession": profession,
                "user_location": location
            },
            config={"configurable": {"session_id": phone_number}}
        )
        return response['output']
    except Exception as e:
        print(f"❌ Agent Error: {e}")
        return "I'm having a bit of trouble connecting to my brain right now. Please try again shortly."