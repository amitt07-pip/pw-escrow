#!/usr/bin/env python3
"""
Telegram Account Login Script
Run this in the shell to authenticate your Telegram account for group creation.

Make sure you have set these secrets:
- TELEGRAM_API_ID
- TELEGRAM_API_HASH
- TELEGRAM_PHONE
"""
import os
import sys
import asyncio
from pyrogram import Client

def main():
    # Get credentials from environment
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    
    if not api_id or not api_hash or not phone:
        print("❌ ERROR: Missing required environment variables!")
        print("\nPlease set these secrets:")
        print("  - TELEGRAM_API_ID")
        print("  - TELEGRAM_API_HASH")
        print("  - TELEGRAM_PHONE")
        print("\nGet API credentials from: https://my.telegram.org")
        sys.exit(1)
    
    print("🔐 Telegram Account Login")
    print("=" * 50)
    print(f"Phone: {phone}")
    print(f"API ID: {api_id}")
    print("=" * 50)
    print()
    
    async def login():
        # Create client with the same session name as the bot uses
        client = Client(
            "escrow_user_session",
            api_id=int(api_id),
            api_hash=api_hash,
            phone_number=phone
        )
        
        try:
            print("📱 Starting Telegram authentication...")
            await client.start()
            
            me = await client.get_me()
            print()
            print("✅ Successfully logged in!")
            print(f"👤 Name: {me.first_name} {me.last_name or ''}")
            print(f"🆔 User ID: {me.id}")
            print(f"📞 Phone: {me.phone_number}")
            print()
            print("✅ Session file created: escrow_user_session.session")
            print()
            print("You can now restart the bot - it will use this session for group creation!")
            
            await client.stop()
            
        except Exception as e:
            print(f"\n❌ Login failed: {e}")
            sys.exit(1)
    
    # Run the async login
    asyncio.run(login())

if __name__ == "__main__":
    main()
