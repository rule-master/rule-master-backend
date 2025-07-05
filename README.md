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
source venv/Scripts/activate
```
- Mac/Linux:
```bash
source venv/bin/activate
```

3. Install packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your env variables, for this you can copy paste the .env.example file:
```
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

3. The Streamlit UI will automatically launch at `http://localhost:8501`
   - You can access the user interface by opening your browser and navigating to:
   ```
   http://localhost:8501
   ```
   - If you see any port conflicts, the server will attempt to resolve them automatically

## Accessing the Application

When you run `server.py`, two services will start:

1. **Streamlit User Interface**
   - URL: `http://localhost:8501`
   - Provides a user-friendly web interface
   - Use this for interactive UI yo test creating, editing, searching and deleting rules
   
### You can also try out the live environment on https://capstone.burhan.ai