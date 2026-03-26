import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response
from dotenv import load_dotenv
from agent import get_agent_response
from database import get_user_profile, log_interaction, update_user_profile

load_dotenv()

# --- Configuration ---
BOT_NAME = os.getenv("BOT_NAME", "KUMUL")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# --- SMART LOGIC: SWITCH CREDENTIALS ---
ENV = os.getenv("ENVIRONMENT", "prod").lower()

if ENV == "dev":
    print("🛠️ RUNNING IN DEVELOPMENT MODE (Test App)")
    PHONE_NUMBER_ID = os.getenv("TEST_PHONE_NUMBER_ID")
    WHATSAPP_TOKEN = os.getenv("TEST_WHATSAPP_TOKEN")
else:
    print("🚀 RUNNING IN PRODUCTION MODE")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")

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
        else:
            print(f"✅ Message sent successfully to {to_number}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

# --- Main Logic ---
def process_message_logic(phone_number, user_message, client_ip, lat=None, lon=None):
    """
    Core logic to handle incoming messages.
    Accepts optional lat/lon for location pins.
    """
    # LOG: Start of process
    print(f"\n{'='*10} NEW INTERACTION {'='*10}")
    print(f"📞 Phone: {phone_number}")
    print(f"💬 Message: {user_message}")
    if lat and lon:
        print(f"📍 Location Pin: {lat}, {lon}")
    
    # Initialize variables for logging
    ai_response = "⚠️ Sorry, I encountered an error."
    detected_profession = None
    detected_location_text = None

    try:
        # 1. Handle Location Update (if provided via pin)
        if lat and lon:
            update_user_profile(phone_number, lat=lat, lon=lon)
            print("💾 Location coordinates saved to user profile.")

        # 2. Get User Profile (Context)
        user = get_user_profile(phone_number)
        if user:
            print(f"👤 Profile Found: {user.profession} in {user.location}")
        else:
            print(f"👤 Profile: New User (No profile found)")

        # 3. Get AI Response
        print("🧠 Thinking...")
        ai_response = get_agent_response(user_message, phone_number, user)
        print(f"🤖 Response: {ai_response}")
        
        # 4. POST-PROCESSING
        updated_user = get_user_profile(phone_number)
        if updated_user:
            detected_profession = updated_user.profession
            detected_location_text = updated_user.location

        # 5. PERMANENT LOGGING
        log_interaction(
            phone_number=phone_number,
            ip_address=client_ip,
            user_message=user_message,
            bot_response=ai_response,
            detected_profession=detected_profession,
            detected_location=detected_location_text
        )
        print("💾 Interaction logged to permanent database.")

        # 6. Send Reply
        send_whatsapp_message(phone_number, ai_response)
        print(f"{'='*10} END INTERACTION {'='*10}\n")

    except Exception as e:
        print(f"❌ CRITICAL ERROR in process_message_logic: {e}")
        send_whatsapp_message(phone_number, "⚠️ Sorry, a server error occurred. Please try again later.")

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
    
    client_host = request.client.host if request.client else "Unknown"

    if payload.get("object") == "whatsapp_business_account":
        try:
            entry = payload["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            # --- FIX: STRICT NUMBER CHECK ---
            # 1. Get the Phone Number ID the message was sent TO (from Meta payload)
            incoming_id = value.get("metadata", {}).get("phone_number_id")
            
            # 2. Compare with OUR configured ID
            if incoming_id != PHONE_NUMBER_ID:
                print(f"⏩ Ignoring message for different Number ID: {incoming_id}")
                return Response(status_code=200)
            # --------------------------------

            if "messages" in value:
                message = value["messages"][0]
                phone_number = message["from"]
                
                # --- Handle Text Messages ---
                if message["type"] == "text":
                    user_message = message["text"]["body"]
                    background_tasks.add_task(
                        process_message_logic, 
                        phone_number, 
                        user_message, 
                        client_host,
                        None, 
                        None
                    )
                
                # --- Handle Location Pins ---
                elif message["type"] == "location":
                    loc = message["location"]
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    user_message = "📍 User shared a location pin."
                    
                    background_tasks.add_task(
                        process_message_logic, 
                        phone_number, 
                        user_message, 
                        client_host,
                        lat,
                        lon
                    )

        except Exception as e:
            print(f"❌ Error parsing webhook payload: {e}")

    return Response(status_code=200)

@app.get("/")
async def root():
    return {"status": "online", "mode": ENV, "model": "Llama-3.3-70B"}