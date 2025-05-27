# app/main.py
print("--- app/main.py: TOP OF FILE (HTML Serving Test) ---")

from fastapi import FastAPI
from fastapi.responses import FileResponse
import os # Keep os for path joining, though we might simplify the path first

print("--- app/main.py: Basic imports DONE (HTML Serving Test) ---")

app = FastAPI(title="SPAI - HTML Test")
print("--- app/main.py: FastAPI INSTANCE CREATED (HTML Serving Test) ---")

# --- Serve Static HTML File for the Root Path ---
@app.get("/", response_class=FileResponse)
async def read_index():
    print("--- app/main.py: / endpoint CALLED (HTML Serving Test) ---")
    # Assuming uvicorn is run from the project root (where 'app' folder is)
    # and htmlsim.html is in 'app/static/htmlsim.html'
    html_file_path = "app/static/htmlsim.html"
    try:
        # Basic check if file exists, though FileResponse will also error if not found
        if not os.path.exists(html_file_path):
            print(f"--- app/main.py: ERROR - {html_file_path} NOT FOUND ---")
            # This error won't be sent to client here, FileResponse will handle it
            # For a proper error response, you'd raise HTTPException
        print(f"--- app/main.py: Attempting to serve {html_file_path} ---")
        return FileResponse(html_file_path)
    except Exception as e:
        print(f"--- app/main.py: ERROR in / endpoint: {e} ---")
        # In a real scenario, you might return an HTML error page or a JSON error
        # For now, let it raise to see the error in logs if any.
        raise

@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED (HTML Serving Test) ---")
    return {"status": "ok_html_test"}

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED (HTML Serving Test) ---")