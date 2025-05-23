from fastapi import FastAPI, HTTPException
from rule_agent import export_rule_to_xml
import os
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import subprocess
import sys
import socket

app = FastAPI(
    title="RuleMaster API",
    description="API for generating DMN rules from natural language",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def kill_port(port: int) -> bool:
    """Kill any process using the specified port."""
    try:
        # Windows specific command to find and kill process on port
        cmd = f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /F /PID %a'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except:
            return False

def start_streamlit():
    """Launch the Streamlit chat interface in a separate process."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), "RuleAgent_app.py")
        if not os.path.exists(script_path):
            print(f"Error: Could not find script at {script_path}")
            return

        port = 8501
        if not is_port_available(port):
            print(f"Port {port} is in use. Attempting to free it...")
            kill_port(port)
            if not is_port_available(port):
                print(f"Could not free port {port}")
                return

        print(f"\n{'='*50}")
        print(f"Starting Streamlit server...")
        print(f"Once started, you can access the UI at:")
        print(f"http://localhost:{port}")
        print(f"{'='*50}\n")
        
        # Run streamlit with minimal output
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                script_path,
                "--server.port", str(port),
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Brief check for immediate startup errors
        try:
            process.wait(timeout=1)
            if process.returncode is not None:
                print("\nStreamlit failed to start")
            else:
                print(f"\nStreamlit is running!")
                print(f"Open your browser and navigate to: http://localhost:{port}")
        except subprocess.TimeoutExpired:
            print(f"\nStreamlit is running successfully!")
            print(f"Open your browser and navigate to: http://localhost:{port}")
            print(f"{'='*50}")
            
    except Exception as e:
        print(f"Error starting Streamlit: {str(e)}")

@app.post("/generate-rule")
async def generate_rule(request: Dict[str, Any]):
    """
    Generate a DMN rule from natural language text.

    Args:
        request: Dictionary containing:
            - rule_text: The natural language rule to convert to DMN
            - output_file: The name of the output file (default: rule.dmn)

    Returns:
        The generated DMN file
    """
    try:
        # Validate request
        if "rule_text" not in request:
            raise HTTPException(status_code=400, detail="rule_text is required")

        rule_text = request["rule_text"]
        output_file = request.get("output_file", "rule.dmn")

        # Generate the rule and get the file path
        file_path = export_rule_to_xml(rule_text, output_file)

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail="Failed to generate rule file")

        # Return the file
        return FileResponse(
            path=file_path, filename=output_file, media_type="application/xml"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
def on_startup():
    start_streamlit()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
