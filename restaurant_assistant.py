import os
import json
import requests
from datetime import datetime
import dateutil.parser as dateparser

# Configuration for Groq API
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise RuntimeError("GROQ_API_KEY is not set. Please export your key before running.")
GROQ_API_KEY = groq_api_key
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# Configuration for Drools endpoint
DROOLS_URL = os.getenv("DROOLS_URL")
DROOLS_USER = os.getenv("DROOLS_USER")
DROOLS_PASS = os.getenv("DROOLS_PASS")

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
You’re a friendly assistant who speaks and writes in plain English. Always be concise and conversational.
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
- Remember each answer and don’t ask it again.
- Ask only about the first missing or wrongly formatted field in plain English.
- Once all 11 are correct, reply only with the JSON object (no extra text).
""")

# --- Helpers ---
def normalize_datetime(val: str) -> str:
    dt = dateparser.parse(val)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.isoformat()

# --- LLM extraction ---
def extract_structured_data(user_input: str, history: list) -> dict:
    # Build full message history: system prompt, prior chat, then user
    messages = (
        [{"role": "system", "content": EXTRACTION_PROMPT}]
        + history
        + [{"role": "user", "content": user_input}]
    )
    payload = {"model": MODEL_NAME, "messages": messages, "temperature": 0.2}
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(f"{GROQ_BASE_URL}/chat/completions", headers=headers, json=payload)
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"].strip()
    # Try to parse JSON directly
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from within text
        if "{" in raw and "}" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            snippet = raw[start:end]
            try:
                data = json.loads(snippet)
            except json.JSONDecodeError:
                return {"_followup": raw}
        else:
            return {"_followup": raw}

    # Normalize datetime fields if present
    for dtf in ("calculationDateTime", "openLocalDateTime", "closeLocalDateTime"):
        if dtf in data:
            data[dtf] = normalize_datetime(data[dtf])
    return data

# --- Drools interaction ---
def send_to_next_step(data: dict) -> int:
    if not DROOLS_URL:
        raise RuntimeError("DROOLS_URL is not set. Cannot call Drools server.")
    drools_payload = {
        "lookup": "ResRecommsKIESession",
        "commands": [
            {"insert": {"object": {"com.myspace.restopsrecomms.RestaurantData": data}, "out-identifier": "restaurantInput"}},
            {"fire-all-rules": {"max": -1, "out-identifier": "fired"}},
            {"get-objects": {"out-identifier": "results", "return-object": True}}
        ]
    }
    auth = (DROOLS_USER, DROOLS_PASS) if DROOLS_USER and DROOLS_PASS else None
    resp = requests.post(DROOLS_URL, json=drools_payload, auth=auth, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    result = resp.json()
    entries = result.get("result", {}).get("execution-results", {}).get("results", [])
    for entry in entries:
        if entry.get("key") == "results":
            for obj in entry.get("value", []):
                if "com.myspace.restopsrecomms.EmployeeRecommendation" in obj:
                    rec = obj["com.myspace.restopsrecomms.EmployeeRecommendation"]
                    return rec.get("restaurantEmployees")
    raise RuntimeError("No EmployeeRecommendation returned from Drools.")

# --- Main handler ---
restaurant_data = {}
history = []

def handle_user_message(user_input: str) -> dict:
    global restaurant_data, history
    # 1) Append user query to history
    history.append({"role": "user", "content": user_input})

    # 2) Extract or ask follow-up
    extracted = extract_structured_data(user_input, history)
    if "_followup" in extracted:
        question = extracted["_followup"]
        history.append({"role": "assistant", "content": question})
        return {"status": "incomplete", "assistant": question}

    # 3) We got valid data fields
    restaurant_data.update(extracted)

    # 4) Once data is complete (11 fields), call Drools
    if len(restaurant_data) >= len(REQUIRED_FIELDS):
        data_copy = restaurant_data.copy()
        num = send_to_next_step(restaurant_data)
        reply = f"✅ All data collected! Recommended employees: {num}"
        history.append({"role": "assistant", "content": reply})
        restaurant_data.clear()
        return {"status": "complete", "assistant": reply, "data": data_copy}

    # 5) Fallback (should not reach here): ask next missing field
    missing = [f for f in REQUIRED_FIELDS if f not in restaurant_data]
    prompt = f"Could you please tell me the {missing[0]}?"
    history.append({"role": "assistant", "content": prompt})
    return {"status": "incomplete", "assistant": prompt}
