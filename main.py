import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response
from dotenv import load_dotenv
from agent import get_agent_response
from database import get_user_profile, log_interaction

load_dotenv()

# --- Configuration ---
BOT_NAME = os.getenv("BOT_NAME", "KUMUL")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
META_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

app = FastAPI()

# --- Helper: Send WhatsApp Message ---
def send_whatsapp_message(to_number, body):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
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

# --- Main Logic ---
def process_message_logic(phone_number, user_message, client_ip):
    # 1. Get User Profile (Context)
    # Since you are testing locally, this will use your local DB
    user = get_user_profile(phone_number)
    
    # 2. Get AI Response
    # This runs your new agent code with the new tools
    ai_response = get_agent_response(user_message, phone_number, user)
    
    # 3. PERMANENT LOGGING
    # This saves to your local database
    log_interaction(
        phone_number=phone_number,
        ip_address=client_ip,
        user_message=user_message,
        bot_response=ai_response
    )

    # 4. Send Reply
    send_whatsapp_message(phone_number, ai_response)

# --- Webhook Endpoints ---

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ WEBHOOK_VERIFIED")
        return Response(content=challenge, status_code=200)
    print("❌ Verification Failed")
    return Response(content="Forbidden", status_code=403)

@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    # Capture Client IP
    client_host = request.client.host if request.client else "Unknown"

    if payload.get("object") == "whatsapp_business_account":
        try:
            entry = payload["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            if "messages" in value:
                message = value["messages"][0]
                phone_number = message["from"]
                
                if message["type"] == "text":
                    user_message = message["text"]["body"]
                    background_tasks.add_task(
                        process_message_logic, 
                        phone_number, 
                        user_message, 
                        client_host
                    )
                
                elif message["type"] == "location":
                    # Handle location sharing if needed in future
                    pass

        except Exception as e:
            print(f"Error parsing webhook: {e}")

    return Response(status_code=200)

@app.get("/")
async def root():
    return {"status": "online", "model": "Llama-3.3-70B"}