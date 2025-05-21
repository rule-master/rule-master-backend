# RuleMaster

A simple API that converts natural language rules into DMN format.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Mac/Linux:
```bash
source venv/bin/activate
```

3. Install packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your env variables:
```
GROQ_API_KEY=
DROOLS_URL=
DROOLS_USER=
DROOLS_PASS=
OPENAI_API_KEY=
QDRANT_API_KEY=
QDRANT_URL=
RULES_DIR=
JAVA_DIR=
```

## Running the Application

### Starting the Server

1. Make sure your virtual environment is activated

2. Start the server:
```bash
python server.py
```

3. The FastAPI server will start at `http://localhost:8000`

4. The Streamlit UI will automatically launch at `http://localhost:8501`
   - You can access the user interface by opening your browser and navigating to:
   ```
   http://localhost:8501
   ```
   - If you see any port conflicts, the server will attempt to resolve them automatically

### Testing the API Directly

You can test the API endpoint directly using the following:

Endpoint: `http://localhost:8000/generate-rule`

Request Type: `POST`

Headers:
```
Content-Type: application/json
```

Body:
```json
{
    "rule_text": "If restaurant size is small then assign 5 employees; if restaurant size is medium then assign 7 employees; if restaurant size is large then assign 10 employees.",
    "output_file": "restaurant_staffing.dmn"
}
```

Full curl command:
```bash
curl -X POST "http://localhost:8000/generate-rule" \
     -H "Content-Type: application/json" \
     -d '{
    "rule_text": "If restaurant size is small then assign 5 employees; if restaurant size is medium then assign 7 employees; if restaurant size is large then assign 10 employees.",
    "output_file": "restaurant_staffing.dmn"
}'
```

## Accessing the Application

When you run `server.py`, two services will start:

1. **FastAPI Backend Server**
   - URL: `http://localhost:8000`
   - Handles the API endpoints
   - Provides the rule generation service

2. **Streamlit User Interface**
   - URL: `http://localhost:8501`
   - Provides a user-friendly web interface
   - Automatically launches when you start the server
   - Use this for interactive rule creation and testing