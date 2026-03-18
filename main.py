import os
import re
import time
from fastapi import FastAPI, Request, BackgroundTasks
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv

from agent import get_agent_response
from database import get_user_profile, update_user_data
#from extractor import extract_profile_data

load_dotenv()

BOT_NAME = os.getenv("BOT_NAME", "KUMUL")
BOT_DESCRIPTION = os.getenv("BOT_DESCRIPTION", "Papua New Guinea's #1 Job Search Assistant.")
BOT_WEBSITE = os.getenv("BOT_WEBSITE")
BOT_EMAIL = os.getenv("BOT_EMAIL")
BOT_ADDRESS = os.getenv("BOT_ADDRESS")

app = FastAPI()

# --- Configuration ---
WHATSAPP_CHAR_LIMIT = 1500
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# --- Helper Functions ---

def send_whatsapp_message(to_number, body):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    if len(body) <= WHATSAPP_CHAR_LIMIT:
        client.messages.create(body=body, from_=TWILIO_NUMBER, to=to_number)
        return

    lines = body.split('\n')
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > WHATSAPP_CHAR_LIMIT:
            client.messages.create(body=current_chunk.strip(), from_=TWILIO_NUMBER, to=to_number)
            time.sleep(0.5)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk.strip():
        client.messages.create(body=current_chunk.strip(), from_=TWILIO_NUMBER, to=to_number)

def get_help_text():
    description = BOT_DESCRIPTION if BOT_DESCRIPTION else "I help you find work in PNG fast and free."
    return f"""*Hi👋 I'm {BOT_NAME}*

{description}

How to use me:

1️⃣ *Tell me your job & location.*
_Eg: My profile is driver in Lae_
️⃣ *Write: Find [job]*
_Eg: Find driver jobs_

🚀 *Let's get you a job!*

_KUMUL is still in development — support and feedback are welcome._
_📞 Contact Jesse at 71087533._
"""

def process_message_logic(phone_number, user_message, latitude=None, longitude=None):
    msg_clean = user_message.strip()
    msg_lower = msg_clean.lower()

    try:
        # --- 1. GPS HANDLING ---
        if latitude and longitude:
            update_user_data(phone_number, lat=latitude, lon=longitude)
            send_whatsapp_message(phone_number, "📍 *Location Received!*\n\nI've saved your coordinates. Tell me to 'Find jobs nearby'!")
            return

        # --- 2. COMMAND HANDLING ---
        # Catch basic commands early to save LLM costs
        if msg_lower in ['hi', 'hello', 'help', 'menu', 'start']:
            send_whatsapp_message(phone_number, get_help_text())
            return

        if msg_lower == 'profile':
            user = get_user_profile(phone_number)
            if user and (user.profession or user.skills or user.location):
                gps_info = f"🌍 GPS: {user.latitude}, {user.longitude}" if user.latitude else ""
                reply = (f"📄 *Your Saved Profile:*\n\n"
                         f"👷 Profession: {user.profession or 'N/A'}\n"
                         f"🛠️ Skills: {user.skills or 'N/A'}\n"
                         f"📍 Location: {user.location or 'N/A'}\n"
                         f"{gps_info}")
            else:
                reply = "I haven't figured out your profile yet. Tell me about your job or skills!"
            send_whatsapp_message(phone_number, reply)
            return
        
        if msg_lower == 'reset':
            update_user_data(phone_number, profession="", skills="", location="", lat=None, lon=None)
            send_whatsapp_message(phone_number, "🗑️ Your profile has been deleted. Let's start fresh!")
            return

        # --- 3. AI AGENT HANDLING ---
        # The agent now handles chatting, searching, AND saving profile data.
        user = get_user_profile(phone_number)
        ai_response = get_agent_response(msg_clean, phone_number, user)
        send_whatsapp_message(phone_number, ai_response)

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        send_whatsapp_message(phone_number, "⚠️ Sorry, I encountered an error. Please try again.")

# --- Webhook Endpoint ---
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    form_data = await request.form()
    phone_number = form_data.get("From")
    user_message = form_data.get("Body", "")
    latitude = form_data.get("Latitude")
    longitude = form_data.get("Longitude")
    
    print(f"📥 Received: From={phone_number}, Msg={user_message}")

    background_tasks.add_task(process_message_logic, phone_number, user_message, latitude, longitude)

    resp = MessagingResponse()
    return str(resp)

@app.get("/")
async def root():
    return {"message": "Kumul Bot is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)