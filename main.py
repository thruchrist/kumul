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
ADMIN_PHONE = os.getenv("ADMIN_PHONE") # FOR TESTING PURPOSE
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
META_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

app = FastAPI()

# FOR TESTING WHILE APP IS RUNNING

def process_message_logic(phone_number, user_message, client_ip):
    # Clean the phone number format to match your .env
    clean_phone = phone_number.replace("whatsapp:", "")
    
    # --- SPLIT LOGIC ---
    if clean_phone == ADMIN_PHONE:
        # --- DEVELOPER TESTING MODE ---
        print(f"🛠️ DEV MODE: Testing new features for {clean_phone}")
        
        # OPTION A: Call a completely different agent file
        # response = get_dev_agent_response(user_message, clean_phone, user)
        
        # OPTION B: Just run the new logic directly here
        # Example: Test a new prompt or tool
        response = "🧪 This is a test response from the new code version!" 
        
        # You can even bypass the agent to test specific blocks
        # if "test" in user_message.lower():
        #     response = "Test successful."
        
    else:
        # --- PRODUCTION MODE (Normal Users) ---
        # This runs the stable code you committed earlier
        user = get_user_profile(clean_phone)
        response = get_agent_response(user_message, clean_phone, user)

    # Log everything (even tests)
    log_interaction(clean_phone, user_message, response, client_ip)
    
    # Send the response
    send_whatsapp_message(phone_number, response)
    

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
        requests.post(META_API_URL, headers=headers, json=data)
    except Exception as e:
        print(f"❌ Send Error: {e}")

def process_message_logic(phone_number, user_message, client_ip):
    # 1. Get User Profile (Context)
    user = get_user_profile(phone_number)
    
    # 2. Get AI Response (Agent handles extraction and search internally)
    ai_response = get_agent_response(user_message, phone_number, user)
    
    # 3. PERMANENT LOGGING (Requirement 5)
    # Note: We log the interaction here to ensure EVERYTHING is saved.
    log_interaction(
        phone_number=phone_number,
        ip_address=client_ip,
        user_message=user_message,
        bot_response=ai_response,
        # We log the profile state *before* this message potentially updates it,
        # or rely on the agent's internal tool calls to update the profile table.
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
        return Response(content=challenge, status_code=200)
    return Response(content="Forbidden", status_code=403)

@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    # Capture Client IP (Note: WhatsApp usually hides user IP, this will be Meta's server IP)
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
                    # Process in background to return 200 OK immediately
                    background_tasks.add_task(
                        process_message_logic, 
                        phone_number, 
                        user_message, 
                        client_host
                    )
                
                elif message["type"] == "location":
                    # Handle location sharing if needed
                    pass

        except Exception as e:
            print(f"Error parsing webhook: {e}")

    return Response(status_code=200)

@app.get("/")
async def root():
    return {"status": "online", "model": "Llama-3.3-70B"}