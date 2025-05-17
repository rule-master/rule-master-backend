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

## Running the Server

1. Make sure your virtual environment is activated

2. Start the server:
```bash
python server.py
```

3. The server will start at `http://localhost:8000`

4. Test it with this example:

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