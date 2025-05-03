from fastapi import FastAPI, HTTPException
from rule_agent import export_rule_to_xml
import os
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import subprocess

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

# Startup event to launch Streamlit UI
def start_streamlit():
    """
    Launch the Streamlit chat interface in a separate process.
    """
    script_path = os.path.join(os.path.dirname(__file__), "streamlit_app.py")
    if os.path.exists(script_path):
        subprocess.Popen(
            ["streamlit", "run", script_path, "--server.port", "8501"],
            cwd=os.path.dirname(__file__),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

# @app.on_event("startup")
# def on_startup():
#     start_streamlit()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
