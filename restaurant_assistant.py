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
EXTRACTION_PROMPT = (
    "You are a JSON extraction assistant. From the user’s message, extract ONLY these fields and their values as JSON: "
    + ", ".join(REQUIRED_FIELDS.keys()) + ". "
    "Map 'small' or any similar word->'S', 'medium' or any similar word->'M', 'large' or any similar word->'L' for restaurantSize. "
    "Format dates/times as 'YYYY-MM-DDThh:mm:ss' (no timezone). "
    "Booleans must be true or false, numbers as floats. "
    "Respond with strictly valid JSON and omit missing fields."
    "distanceHD is always a string"
)

# --- Helpers ---
def normalize_datetime(val: str) -> str:
    dt = dateparser.parse(val)
    # Drop any timezone info for LocalDateTime
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.isoformat()

# --- LLM extraction ---
def extract_structured_data(user_input: str, history: list) -> dict:
    endpoint = f"{GROQ_BASE_URL}/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": history + [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user",   "content": user_input}
        ],
        "temperature": 0.0
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(endpoint, headers=headers, json=payload)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    extracted = json.loads(raw)

    # Normalize datetime fields
    for dtf in ("calculationDateTime", "openLocalDateTime", "closeLocalDateTime"):
        if dtf in extracted:
            extracted[dtf] = normalize_datetime(extracted[dtf])
    return extracted

# --- Drools interaction ---
def send_to_next_step(data: dict) -> int:
    if not DROOLS_URL:
        raise RuntimeError("DROOLS_URL is not set. Cannot call Drools server.")
    drools_payload = {
        "lookup": "ResRecommsKIESession",
        "commands": [
            {
                "insert": {
                    "object": {"com.myspace.restopsrecomms.RestaurantData": data},
                    "out-identifier": "restaurantInput"
                }
            },
            {"fire-all-rules": {"max": -1, "out-identifier": "fired"}},
            {"get-objects": {"out-identifier": "results", "return-object": True}}
        ]
    }
    auth = (DROOLS_USER, DROOLS_PASS) if DROOLS_USER and DROOLS_PASS else None
    resp = requests.post(
        DROOLS_URL,
        json=drools_payload,
        auth=auth,
        headers={"Content-Type": "application/json"}
    )
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

# --- Follow-up prompting ---
def build_followup_message(missing_fields: list) -> str:
    prompts = {
        "restaurantSize": "Could you tell me the restaurant size (small, medium, or large)?",
        "hasAutoking": "Does this restaurant use Autoking? (true/false)",
        "totalExpectedSales": "What are the total expected sales? (e.g., 1234.56)",
        "timeSlotExpectedSales": "What sales do you expect during this time slot?",
        "companyId": "Please provide the company ID.",
        "restaurantId": "What is the restaurant ID?",
        "previousDaySales": "How much sales did you make yesterday?",
        "distanceHD": "How far is the restaurant from HQ in km?",
        "calculationDateTime": "When should I run this calculation?",
        "openLocalDateTime": "What is the restaurant opening time?",
        "closeLocalDateTime": "What is the closing time?"
    }
    return prompts[missing_fields[0]]

# --- Main handler ---
restaurant_data = {}
history = []

def handle_user_message(user_input: str) -> dict:
    global restaurant_data, history
    history.append({"role": "user", "content": user_input})

    # Extract all fields via LLM
    extracted = extract_structured_data(user_input, history)
    restaurant_data.update(extracted)

    # Check for missing
    missing = [k for k in REQUIRED_FIELDS if k not in restaurant_data]
    if missing:
        return {"status": "incomplete", "assistant": build_followup_message(missing)}

    # All data present: send to Drools
    num = send_to_next_step(restaurant_data)
    captured = json.dumps(restaurant_data, indent=2)
    assistant_reply = (
        "✅ All required restaurant data has been collected. Proceeding with recommendation…\n"
        f"Captured data:\n{captured}\n"
        f"Recommended employees: {num}"
    )
    history.append({"role": "assistant", "content": assistant_reply})
    restaurant_data.clear()
    return {"status": "complete", "assistant": assistant_reply}

# --- Tests ---
if __name__ == "__main__":
    # Incomplete if nothing given
    assert handle_user_message("")["status"] == "incomplete"
    # Example full run
    full = (
        "We run a large restaurant today for SunSipCo (R789), Autoking true, "
        "totalExpectedSales 18000, timeSlotExpectedSales 6000, yesterday sales 15000, distanceHD 3, "
        "calculationDateTime July 15 2025 11:30 AM, openLocalDateTime 09:00 AM, closeLocalDateTime 11:00 PM"
    )
    res = handle_user_message(full)
    assert res["status"] == "complete"
    assert "Captured data" in res["assistant"]
    print("All tests passed.")
