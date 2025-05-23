import os
import subprocess
import sys
import socket

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
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            if not is_port_available(port):
                print(f"Port {port} is in use. Attempting to free it...")
                kill_port(port)
                if not is_port_available(port):
                    print(f"Could not free port {port}, trying again...")
                    retry_count += 1
                    continue
            break
            
        if retry_count == max_retries:
            print(f"Failed to free port {port} after {max_retries} attempts")
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
                "--server.address", "localhost",
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Wait a bit longer for startup and check process status
        try:
            # Wait up to 5 seconds to see if process dies immediately
            process.wait(timeout=5)
            if process.returncode is not None:
                print("\nStreamlit failed to start. Error output:")
                error_output = process.stderr.read().decode()
                print(error_output)
                return
        except subprocess.TimeoutExpired:
            # Process is still running after 5 seconds, which is good
            print(f"\nStreamlit is running successfully!")
            print(f"Open your browser and navigate to: http://localhost:{port}")
            print(f"{'='*50}")
            
    except Exception as e:
        print(f"Error starting Streamlit: {str(e)}")
        if 'process' in locals():
            try:
                process.kill()
            except:
                pass

if __name__ == "__main__":
    start_streamlit()
    # Keep the main process running
    try:
        while True:
            input()
    except KeyboardInterrupt:
        print("\nShutting down...")
