import os
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from tools import search_png_jobs, save_user_profile
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    temperature=0.2, # Slightly bumped for more natural chat, but low enough for logic
    base_url=os.getenv("OPENAI_API_BASE"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    request_timeout=60 
)

# --- 2. Upgraded System Prompt ---
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are {bot_name}, Papua New Guinea's friendly and highly intelligent AI Job Search Assistant. 

    IDENTITY:
    - You are helpful, encouraging, and professional. 
    - Keep responses concise and formatted for WhatsApp (use emojis, bold text, and bullet points).

    USER CONTEXT (Phone: {phone_number}):
    - Saved Profession: {user_profession}
    - Saved Skills: {user_skills}
    - Saved Location: {user_location}

    YOUR CAPABILITIES & RULES:
    1. **Natural Chat**: If the user is just saying hi, asking general questions, or following up, chat with them normally based on conversation history. Do not use tools unless necessary.
    2. **Profile Building**: If the user mentions their job, skills, or where they live, use the `save_user_profile` tool immediately to remember it. ALWAYS pass the {phone_number} to this tool.
    3. **Job Hunting**: If the user wants to find a job, use the `search_png_jobs` tool. 
       - PRO TIP: If they just say "Find me a job" without specifying, look at their "Saved Profession" and "Saved Location" to run the search. If their profile is empty, ask them what kind of job they want first.
    4. **WhatsApp Formatting**: Never send massive walls of text. Keep links clean.
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# --- 3. Create the Agent ---
tools = [search_png_jobs, save_user_profile]
agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True,
    max_iterations=5
)

def get_session_history(session_id):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection_string=os.getenv("DATABASE_URL")
    )

agent_with_memory = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

def get_agent_response(user_input, phone_number, user_data=None):
    profession = user_data.profession if user_data and user_data.profession else "Not Provided"
    skills = user_data.skills if user_data and user_data.skills else "Not Provided"
    location = user_data.location if user_data and user_data.location else "Not Provided"

    try:
        response = agent_with_memory.invoke(
            {
                "input": user_input,
                "bot_name": os.getenv("BOT_NAME", "KUMUL"),
                "phone_number": phone_number,
                "user_profession": profession,
                "user_skills": skills,
                "user_location": location
            },
            config={"configurable": {"session_id": phone_number}}
        )
        return response['output']
    except Exception as e:
        print(f"❌ Agent Execution Error: {e}")
        return "⚠️ Sorry, my systems had a quick hiccup. Could you say that again?"