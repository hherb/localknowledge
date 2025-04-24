#!/usr/bin/env python3
import sys
import subprocess
import threading
import time

# Start the MCP server
mcp_process = subprocess.Popen(
    ["python", "-m", "localknowledge.mcp.mcp_postgres"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Function to automatically approve all requests
def auto_approve():
    while True:
        line = mcp_process.stdout.readline()
        if not line:
            break
        print(line, end="")
        sys.stdout.flush()
        
        # If the line contains a request for approval, send "y"
        if "?" in line and ("approve" in line.lower() or "allow" in line.lower()):
            print("Auto-approving request...")
            mcp_process.stdin.write("y\n")
            mcp_process.stdin.flush()
            time.sleep(0.1)  # Small delay to ensure the input is processed

# Start the auto-approve thread
approve_thread = threading.Thread(target=auto_approve)
approve_thread.daemon = True
approve_thread.start()

# Forward stdin to the MCP process
try:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        mcp_process.stdin.write(line)
        mcp_process.stdin.flush()
except KeyboardInterrupt:
    pass
finally:
    mcp_process.terminate()
    print("MCP server terminated")
