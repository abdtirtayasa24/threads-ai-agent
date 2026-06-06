import asyncio
import httpx
import os
from app.config import settings

THREADS_API_BASE = "https://graph.threads.net"
ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

def update_env_file(key: str, value: str):
    """Safely updates a key-value pair in the .env file."""
    if not os.path.exists(ENV_FILE_PATH):
        print(f"Warning: .env file not found at {ENV_FILE_PATH}")
        return

    with open(ENV_FILE_PATH, "r") as file:
        lines = file.readlines()

    key_found = False
    with open(ENV_FILE_PATH, "w") as file:
        for line in lines:
            if line.strip().startswith(f"{key}="):
                file.write(f"{key}={value}\n")
                key_found = True
            else:
                file.write(line)
        
        # If the key wasn't found in the file, append it
        if not key_found:
            if lines and not lines[-1].endswith('\n'):
                file.write('\n')
            file.write(f"{key}={value}\n")

async def refresh_long_lived_token():
    """
    Refreshes the Threads long-lived access token.
    Meta requires refreshing the token before it expires (valid for 60 days).
    """
    print("Starting Threads token refresh...")
    url = f"{THREADS_API_BASE}/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": settings.THREADS_ACCESS_TOKEN
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        
        if response.status_code != 200:
            print(f"Failed to refresh token: {response.text}")
            return None
            
        data = response.json()
        new_token = data.get("access_token")
        expires_in = data.get("expires_in")
        
        print(f"Token refreshed successfully. Expires in {expires_in} seconds.")
        
        # 1. Update the .env file so it persists across restarts
        update_env_file("THREADS_ACCESS_TOKEN", new_token)
        print("Successfully updated THREADS_ACCESS_TOKEN in .env file.")
        
        # 2. Update the running application's settings in memory
        settings.THREADS_ACCESS_TOKEN = new_token
        
        return new_token

if __name__ == "__main__":
    asyncio.run(refresh_long_lived_token())