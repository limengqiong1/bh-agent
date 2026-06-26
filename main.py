import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("AGENT_HOST", "0.0.0.0"),
        port=int(os.getenv("AGENT_PORT", "8081")),
        reload=os.getenv("AGENT_RELOAD", "0") == "1",
    )
