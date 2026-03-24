import os
import re
import time
import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response
from dotenv import load_dotenv

from agent import get_agent_response
from database import get_user_profile, update_user_data

load_dotenv()

# --- Configuration ---
BOT_NAME = os.getenv("BOT_NAME", "KUMUL")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN") # Meta Permanent Token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID") # Meta Phone Number ID
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") # The string you set in Meta Dashboard

# Meta API URL
META_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

app = FastAPI()

# --- Helper: Send WhatsApp Message ---
def send_whatsapp_message(to_number, body):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Split message if too long (Meta limit is 4096, but nice to keep it short)
    # We will just send the whole thing for now, Meta handles long texts better than Twilio
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": body}
    }
    
    try:
        resp = requests.post(META_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            print(f"❌ Error sending message: {resp.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

# --- Logic (Same as before) ---
def get_help_text():
    return f"""*Hi👋 I'm {BOT_NAME}*

Papua New Guinea's #1 Job Search Assistant.

How to use me:

1️⃣ *Tell me your job & location.*
_Eg: My profile is driver in Lae_
2️⃣ *Write: Find [job]*
_Eg: Find driver jobs_

🚀 *Let's get you a job!*
"""

def process_message_logic(phone_number, user_message, latitude=None, longitude=None):
    # Standardize phone number (Meta sends 1XXXXXXXXXX, Twilio sent whatsapp:1XXXXXXXXXX)
    # Your database expects the ID used in session. We will strip 'whatsapp:' if present.
    clean_phone = phone_number.replace("whatsapp:", "") 
    
    msg_clean = user_message.strip()
    msg_lower = msg_clean.lower()

    try:
        # 1. GPS HANDLING
        if latitude and longitude:
            update_user_data(clean_phone, lat=latitude, lon=longitude)
            send_whatsapp_message(phone_number, "📍 *Location Received!*\n\nI've saved your coordinates.")
            return

        # 2. COMMAND HANDLING
        if msg_lower in ['hi', 'hello', 'help', 'menu', 'start']:
            send_whatsapp_message(phone_number, get_help_text())
            return

        if msg_lower == 'profile':
            user = get_user_profile(clean_phone)
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
            update_user_data(clean_phone, profession="", skills="", location="", lat=None, lon=None)
            send_whatsapp_message(phone_number, "🗑️ Your profile has been deleted. Let's start fresh!")
            return

        # 3. AI AGENT HANDLING
        user = get_user_profile(clean_phone)
        ai_response = get_agent_response(msg_clean, clean_phone, user)
        send_whatsapp_message(phone_number, ai_response)

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        send_whatsapp_message(phone_number, "⚠️ Sorry, I encountered an error. Please try again.")

# --- Webhook Endpoints ---

# 1. Verification Endpoint (Required by Meta)
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ WEBHOOK_VERIFIED")
        return Response(content=challenge, status_code=200)
    else:
        print("❌ Verification Failed")
        return Response(content="Forbidden", status_code=403)

# 2. Message Handler (Receives JSON from Meta)
@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    # Check if this is a message event
    if payload.get("object") == "whatsapp_business_account":
        try:
            entry = payload["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            # Ignore status updates (delivered, read, etc.)
            if "messages" in value:
                message = value["messages"][0]
                phone_number = message["from"] # Format: 1XXXXXXXXXX
                
                # Handle Text Messages
                if message["type"] == "text":
                    user_message = message["text"]["body"]
                    background_tasks.add_task(process_message_logic, phone_number, user_message)
                
                # Handle Location Messages (optional)
                elif message["type"] == "location":
                    loc = message["location"]
                    lat, lon = loc["latitude"], loc["longitude"]
                    background_tasks.add_task(process_message_logic, phone_number, "", lat, lon)

        except Exception as e:
            print(f"Error parsing webhook: {e}")
            # Always return 200 OK to Meta so they don't retry
            return Response(status_code=200)

    return Response(status_code=200)

@app.get("/")
async def root():
    return {"message": "Kumul Bot is running on Meta Cloud API!"}