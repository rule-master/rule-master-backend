import os
import json
import requests
from datetime import datetime
import dateutil.parser as dateparser
from logger_utils import logger, log_operation

# Configuration for Groq API
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    logger.error("GROQ_API_KEY is not set")
    raise RuntimeError("GROQ_API_KEY is not set. Please export your key before running.")

GROQ_API_KEY = groq_api_key
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# Configuration for Drools endpoint
DROOLS_URL = os.getenv("DROOLS_URL")
DROOLS_USER = os.getenv("DROOLS_USER")
DROOLS_PASS = os.getenv("DROOLS_PASS")

logger.info("Restaurant Assistant Configuration:")
logger.info(f"Using Groq API at: {GROQ_BASE_URL}")
logger.info(f"Drools URL configured: {'Yes' if DROOLS_URL else 'No'}")

# LLM model name
MODEL_NAME = "llama3-8b-8192"

# Required restaurant fields schema
REQUIRED_FIELDS = {
    "restaurantSize":       {"type": "enum",     "values": ["S", "M", "L"],   "example": "M"},
    "hasAutoking":          {"type": "bool",     "example": "true"},
    "totalExpectedSales":   {"type": "number",   "example": 12345.67},
    "timeSlotExpectedSales": {"type": "number",  "example": 6789.01},
    "companyId":            {"type": "string",   "example": "company_123"},
    "restaurantId":         {"type": "string",   "example": "rest_456"},
    "previousDaySales":     {"type": "number",   "example": 9876.54},
    "distanceHD":           {"type": "string",   "example": "3KM"},
    "calculationDateTime":  {"type": "datetime", "example": "2025-04-18T09:45:00"},
    "openLocalDateTime":    {"type": "datetime", "example": "2025-04-18T08:00:00"},
    "closeLocalDateTime":   {"type": "datetime", "example": "2025-04-18T22:00:00"},
}

# System prompt for LLM extraction
EXTRACTION_PROMPT = ("""
You're a friendly assistant who speaks and writes in plain English. Always be concise and conversational.
Your job is to collect exactly these 11 details and then output one clean JSON object with all of them.

**The 11 required details:**
1. restaurantSize – one of 'S','M','L' (map words like 'small','little'->S; 'medium','mid'->M; 'large','big'->L).
2. hasAutoking – true or false
3. totalExpectedSales – number (e.g. 12345.67)
4. timeSlotExpectedSales – number (e.g. 6789.01)
5. companyId – text identifier
6. restaurantId – text identifier
7. previousDaySales – number
8. distanceHD – text (e.g. '3KM')
9. calculationDateTime – 'YYYY-MM-DDThh:mm:ss'
10. openLocalDateTime – 'YYYY-MM-DDThh:mm:ss'
11. closeLocalDateTime – 'YYYY-MM-DDThh:mm:ss'

**Important rules:**
- Remember each answer and don't ask it again.
- Ask only about the first missing or wrongly formatted field in plain English.
- Once all 11 are correct, reply only with the JSON object (no extra text).
""")

# --- Helpers ---
def normalize_datetime(val: str) -> str:
    try:
        dt = dateparser.parse(val)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt.isoformat()
    except Exception as e:
        logger.error(f"Failed to normalize datetime '{val}': {str(e)}")
        raise

# --- LLM extraction ---
def extract_structured_data(user_input: str, history: list) -> dict:
    logger.debug(f"Extracting structured data from input: {user_input[:100]}...")
    
    try:
        # Build full message history: system prompt, prior chat, then user
        messages = (
            [{"role": "system", "content": EXTRACTION_PROMPT}]
            + history
            + [{"role": "user", "content": user_input}]
        )
        
        payload = {"model": MODEL_NAME, "messages": messages, "temperature": 0.2}
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        
        logger.debug("Sending request to Groq API...")
        resp = requests.post(f"{GROQ_BASE_URL}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()

        raw = resp.json()["choices"][0]["message"]["content"].strip()
        logger.debug(f"Received raw response: {raw[:200]}...")  # Log first 200 chars
        
        # Try to parse JSON directly
        try:
            data = json.loads(raw)
            logger.debug("Successfully parsed JSON response")
        except json.JSONDecodeError:
            logger.debug("Direct JSON parse failed, attempting to extract JSON from text")
            # Attempt to extract JSON object from within text
            if "{" in raw and "}" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                snippet = raw[start:end]
                try:
                    data = json.loads(snippet)
                    logger.debug("Successfully extracted and parsed JSON from text")
                except json.JSONDecodeError:
                    logger.debug("Failed to parse extracted JSON, returning followup")
                    return {"_followup": raw}
            else:
                logger.debug("No JSON found in response, returning followup")
                return {"_followup": raw}

        # Normalize datetime fields if present
        for dtf in ("calculationDateTime", "openLocalDateTime", "closeLocalDateTime"):
            if dtf in data:
                data[dtf] = normalize_datetime(data[dtf])
        
        log_operation('data_extraction', {
            'fields_found': list(data.keys()),
            'is_followup': '_followup' in data
        })
        
        return data
        
    except Exception as e:
        logger.error("Error in extract_structured_data", exc_info=True)
        log_operation('data_extraction', {'user_input': user_input}, error=e)
        raise

# --- Drools interaction ---
def send_to_next_step(data: dict) -> int:
    logger.debug("Sending data to Drools server...")
    
    if not DROOLS_URL:
        error_msg = "DROOLS_URL is not set. Cannot call Drools server."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    try:
        drools_payload = {
            "lookup": "ResRecommsKIESession",
            "commands": [
                {"insert": {"object": {"com.myspace.restopsrecomms.RestaurantData": data}, "out-identifier": "restaurantInput"}},
                {"fire-all-rules": {"max": -1, "out-identifier": "fired"}},
                {"get-objects": {"out-identifier": "results", "return-object": True}}
            ]
        }
        
        auth = (DROOLS_USER, DROOLS_PASS) if DROOLS_USER and DROOLS_PASS else None
        logger.debug("Making request to Drools server...")
        resp = requests.post(DROOLS_URL, json=drools_payload, auth=auth, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        
        result = resp.json()
        entries = result.get("result", {}).get("execution-results", {}).get("results", [])
        
        for entry in entries:
            if entry.get("key") == "results":
                for obj in entry.get("value", []):
                    if "com.myspace.restopsrecomms.EmployeeRecommendation" in obj:
                        rec = obj["com.myspace.restopsrecomms.EmployeeRecommendation"]
                        employees = rec.get("restaurantEmployees")
                        
                        log_operation('drools_recommendation', {
                            'input_data': data,
                            'recommended_employees': employees
                        })
                        
                        return employees
                        
        error_msg = "No EmployeeRecommendation returned from Drools."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    except Exception as e:
        logger.error("Error in send_to_next_step", exc_info=True)
        log_operation('drools_recommendation', {'input_data': data}, error=e)
        raise

# --- Main handler ---
restaurant_data = {}
history = []

def handle_user_message(user_input: str) -> dict:
    logger.info(f"Handling user message: {user_input[:100]}...")  # Log first 100 chars
    
    global restaurant_data, history
    try:
        # 1) Append user query to history
        history.append({"role": "user", "content": user_input})

        # 2) Extract or ask follow-up
        extracted = extract_structured_data(user_input, history)
        if "_followup" in extracted:
            question = extracted["_followup"]
            history.append({"role": "assistant", "content": question})
            logger.debug("Requesting follow-up information")
            return {"status": "incomplete", "assistant": question}

        # 3) We got valid data fields
        restaurant_data.update(extracted)
        logger.debug(f"Updated restaurant data, now have {len(restaurant_data)} fields")

        # 4) Once data is complete (11 fields), call Drools
        if len(restaurant_data) >= len(REQUIRED_FIELDS):
            logger.info("All required fields collected, calling Drools")
            data_copy = restaurant_data.copy()
            num = send_to_next_step(restaurant_data)
            reply = f"✅ All data collected! Recommended employees: {num}"
            history.append({"role": "assistant", "content": reply})
            restaurant_data.clear()
            
            log_operation('conversation_complete', {
                'collected_data': data_copy,
                'recommendation': num
            })
            
            return {"status": "complete", "assistant": reply, "data": data_copy}

        # 5) Fallback (should not reach here): ask next missing field
        missing = [f for f in REQUIRED_FIELDS if f not in restaurant_data]
        prompt = f"Could you please tell me the {missing[0]}?"
        history.append({"role": "assistant", "content": prompt})
        logger.debug(f"Missing fields: {missing}")
        return {"status": "incomplete", "assistant": prompt}
        
    except Exception as e:
        logger.error("Error in handle_user_message", exc_info=True)
        log_operation('message_handling', {'user_input': user_input}, error=e)
        raise
