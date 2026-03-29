import os
import requests
import time
from fastapi import FastAPI, Request, BackgroundTasks, Response
from dotenv import load_dotenv
from agent import get_agent_response
from database import log_interaction

load_dotenv()

# --- Configuration ---
BOT_NAME = os.getenv("BOT_NAME", "KUMUL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "prod").lower()

# Meta (Production) Config
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
META_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# Twilio (Development) Config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_API_URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

# WhatsApp Limits
WHATSAPP_CHAR_LIMIT = 1600 # META LIMIT 4096, TWILIO LIMIT 1600
MESSAGE_DELAY = 1.0  # Seconds between chunked messages

app = FastAPI()


# ==========================================
# MESSAGE CHUNKING
# ==========================================

def chunk_message(message: str, limit: int = WHATSAPP_CHAR_LIMIT) -> list:
    """Split long messages into WhatsApp-safe chunks"""
    if len(message) <= limit:
        return [message]
    
    chunks = []
    current_chunk = ""
    
    # Split by double newline first to keep paragraphs together
    paragraphs = message.split("\n\n")
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= limit:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # If single paragraph is too long, split by single newline
            if len(para) > limit:
                lines = para.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= limit:
                        current_chunk += line + "\n"
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                        
                        # CRITICAL FIX: If a single line is STILL too long (e.g. a massive URL), 
                        # force-split it by character count to prevent API rejection
                        if len(line) > limit:
                            for i in range(0, len(line), limit):
                                hard_chunk = line[i:i+limit]
                                if hard_chunk:
                                    chunks.append(hard_chunk)
                        else:
                            current_chunk = line + "\n"
            else:
                current_chunk = para + "\n\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


# ==========================================
# WHATSAPP MESSAGE HELPERS
# ==========================================

def send_meta_message(to_number: str, body: str, is_interactive: dict = None):
    """Send message via Meta WhatsApp API with interactive support"""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    clean_number = to_number.replace("whatsapp:", "").replace("+", "")
    
    # Handle interactive messages (list, buttons)
    if is_interactive:
        data = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "interactive",
            "interactive": is_interactive
        }
    else:
        data = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "text",
            "text": {"body": body}
        }
    
    try:
        resp = requests.post(META_API_URL, headers=headers, json=data, timeout=30)
        if resp.status_code != 200:
            print(f"❌ [META] Error {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ [META] Request failed: {e}")
        return False


def send_meta_typing_indicator(to_number: str, is_typing: bool = True):
    """Send typing indicator to show bot is working"""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    clean_number = to_number.replace("whatsapp:", "").replace("+", "")
    
    data = {
        "messaging_product": "whatsapp",
        "to": clean_number,
        "type": "status",
        "status": {"type": "typing" if is_typing else "available"}
    }
    
    try:
        requests.post(META_API_URL, headers=headers, json=data, timeout=10)
    except:
        pass  # Don't fail on typing indicator


def send_twilio_message(to_number: str, body: str):
    """Send message via Twilio"""
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"
    
    data = {
        "From": TWILIO_PHONE_NUMBER,
        "To": to_number,
        "Body": body
    }
    
    try:
        resp = requests.post(TWILIO_API_URL, auth=auth, data=data, timeout=30)
        if resp.status_code != 201:
            print(f"❌ [TWILIO] Error {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ [TWILIO] Request failed: {e}")
        return False


def create_list_message(header: str, body: str, button_text: str, sections: list) -> dict:
    """Create WhatsApp List Message format"""
    return {
        "type": "list",
        "header": {
            "type": "text",
            "text": header[:60]  # Max 60 chars for header
        },
        "body": {
            "text": body
        },
        "footer": {
            "text": "🇵🇬 KUMUL Job Search"
        },
        "action": {
            "button": button_text[:20],  # Max 20 chars
            "sections": sections[:10]  # Max 10 sections
        }
    }


# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================

def process_message_logic(phone_number: str, user_message: str, client_ip: str, 
                          incoming_channel: str = "meta", lat: float = None, lon: float = None):
    """Main message processing with full feature support"""
    
    # Channel override for dev
    active_channel = "twilio" if ENVIRONMENT == "dev" else incoming_channel
    
    print(f"\n{'='*10} NEW INTERACTION {'='*10}", flush=True)
    print(f"📞 Phone: {phone_number}", flush=True)
    print(f"💬 Message: {user_message[:100]}...", flush=True)
    
    # Send typing indicator (Meta only)
    if active_channel == "meta":
        send_meta_typing_indicator(phone_number, is_typing=True)
    
    try:
        # 1. Get AI Response
        print("🧠 Thinking...")
        start_time = time.time()
        
        agent_result = get_agent_response(user_message, phone_number)
        ai_response = agent_result["response"]
        tools_used = agent_result.get("tools_used", [])
        intent = agent_result.get("intent", "unknown")
        entities = agent_result.get("entities", {})
        
        processing_time = time.time() - start_time
        print(f"🤖 Response ready ({processing_time:.1f}s)")
        print(f"🔧 Tools used: {tools_used}")
        
        # 2. Stop typing indicator
        if active_channel == "meta":
            send_meta_typing_indicator(phone_number, is_typing=False)
        
        # 3. Send Response (with chunking if needed)
        chunks = chunk_message(ai_response)
        
        for i, chunk in enumerate(chunks):
            if active_channel == "twilio":
                send_twilio_message(phone_number, chunk)
            else:
                send_meta_message(phone_number, chunk)
            
            # Delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                time.sleep(MESSAGE_DELAY)
        
        # 4. Log Interaction
        log_interaction(
            phone_number=phone_number,
            user_message=user_message,
            bot_response=ai_response,
            interaction_type=intent,
            tools_used=tools_used,
            intent=intent,
            entities=entities,
            processing_time_ms=int(processing_time * 1000),
            client_ip=client_ip,
            channel=active_channel
        )
        
        print(f"✅ Completed - {len(chunks)} message(s) sent")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}", flush=True)
        
        error_message = "⚠️ *Something went wrong*\n\nPlease try again or type *'help'* for options."
        
        if active_channel == "twilio":
            send_twilio_message(phone_number, error_message)
        else:
            send_meta_message(phone_number, error_message)
        
        # Log the error
        log_interaction(
            phone_number=phone_number,
            user_message=user_message,
            bot_response=error_message,
            interaction_type="error",
            error_message=str(e),
            client_ip=client_ip,
            channel=active_channel
        )


# ==========================================
# WEBHOOK ENDPOINTS
# ==========================================

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Meta webhook verification"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ META WEBHOOK VERIFIED")
        return Response(content=challenge, status_code=200)
    
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def meta_webhook(request: Request, background_tasks: BackgroundTasks):
    """Meta WhatsApp webhook"""
    payload = await request.json()
    client_host = request.client.host if request.client else "Unknown"
    
    # Handle webhook verification echo
    if payload.get("object") == "whatsapp_business_account":
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            
            # Handle messages
            if "messages" in value:
                message = value["messages"][0]
                phone_number = message.get("from", "")
                user_message = ""
                lat, lon = None, None
                
                msg_type = message.get("type", "")
                
                if msg_type == "text":
                    user_message = message.get("text", {}).get("body", "")
                elif msg_type == "location":
                    lat = message.get("location", {}).get("latitude")
                    lon = message.get("location", {}).get("longitude")
                    user_message = f"📍 Location shared: {lat}, {lon}"
                elif msg_type == "interactive":
                    # Handle list/button responses
                    interactive = message.get("interactive", {})
                    if interactive.get("type") == "list_reply":
                        user_message = interactive.get("list_reply", {}).get("title", "")
                    elif interactive.get("type") == "button_reply":
                        user_message = interactive.get("button_reply", {}).get("title", "")
                elif msg_type == "button":
                    user_message = message.get("button", {}).get("text", "")
                
                if user_message:
                    background_tasks.add_task(
                        process_message_logic,
                        phone_number,
                        user_message,
                        client_host,
                        "meta",
                        lat,
                        lon
                    )
                    
        except Exception as e:
            print(f"❌ Meta payload error: {e}")
    
    return Response(status_code=200)


@app.post("/twilio")
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks):
    """Twilio WhatsApp webhook"""
    form_data = await request.form()
    client_host = request.client.host if request.client else "Unknown"
    
    phone_number = form_data.get("From", "")
    user_message = form_data.get("Body", "")
    lat = form_data.get("Latitude")
    lon = form_data.get("Longitude")
    
    # Handle media messages
    media_url = form_data.get("MediaUrl0")
    if media_url and not user_message:
        user_message = "📎 Media file received"
    
    if not user_message:
        user_message = "⚠️ Empty message"
    
    background_tasks.add_task(
        process_message_logic,
        phone_number,
        user_message,
        client_host,
        "twilio",
        lat,
        lon
    )
    
    return Response(status_code=200)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "bot": BOT_NAME,
        "environment": ENVIRONMENT,
        "version": "2.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "checks": {
            "meta_token": bool(WHATSAPP_TOKEN),
            "twilio_configured": bool(TWILIO_ACCOUNT_SID),
            "database": "configured"
        }
    }