import uvicorn
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

if __name__ == "__main__":
    # Load env vars if needed, though app.py does it too
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
    
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting Web UI at http://{host}:{port}")
    uvicorn.run("src.web.app:app", host=host, port=port, reload=True)
