from telethon import TelegramClient
import asyncio
import sys
import os
import json

async def main():
    # Ensure sessions directory exists
    os.makedirs("sessions", exist_ok=True)
    
    # Load API credentials from config.json
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            API_ID = config['api_id']
            API_HASH = config['api_hash']
    except FileNotFoundError:
        print("Error: config.json not found. Please create it with your API credentials.")
        sys.exit(1)
    except KeyError:
        print("Error: config.json must contain 'api_id' and 'api_hash' fields.")
        sys.exit(1)
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python create_session.py <session_name>")
        sys.exit(1)
    
    session_name = sys.argv[1]
    
    try:
        # Create Telegram client
        client = TelegramClient(f"sessions/{session_name}", API_ID, API_HASH)
        
        # Start the client and handle authentication
        await client.start()
        
        print(f"Session file created successfully: sessions/{session_name}.session")
    
    except Exception as e:
        print(f"Error creating session: {e}")
        sys.exit(1)
    
    finally:
        # Ensure client is disconnected
        if 'client' in locals():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())