import os
import sys
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
)

# ---------------- LOAD ENV ----------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ---------------- MAIN ----------------
def main():
    token = os.getenv("ESCROW_BOT_TOKEN")
    if not token:
        print("❌ ESCROW_BOT_TOKEN not set")
        sys.exit(1)

    print("✅ PagaL Escrow Bot (@PagaLEscrowBot) - Starting...")

    import escrow_bot

    app = ApplicationBuilder().token(token).build()

    # -------- HANDLERS --------
    app.add_handler(CommandHandler("start", escrow_bot.start_command))
    app.add_handler(CommandHandler("menu", escrow_bot.menu_command))
    app.add_handler(CommandHandler("escrow", escrow_bot.escrow_command))
    app.add_handler(CommandHandler("dispute", escrow_bot.dispute_command))
    app.add_handler(CommandHandler("dd", escrow_bot.dd_command))
    app.add_handler(CommandHandler("buyer", escrow_bot.buyer_command))
    app.add_handler(CommandHandler("seller", escrow_bot.seller_command))
    app.add_handler(CommandHandler("token", escrow_bot.token_command))
    app.add_handler(CommandHandler("deposit", escrow_bot.deposit_command))

    app.add_handler(CallbackQueryHandler(escrow_bot.button_callback))
    app.add_handler(
        ChatMemberHandler(
            escrow_bot.track_chat_members,
            ChatMemberHandler.CHAT_MEMBER,
        )
    )


    # -------- CONFIG DIAGNOSTICS --------
    bsc = os.getenv("BSCSCAN_API_KEY")
    tron = os.getenv("TRONGRID_API_KEY")
    logs = os.getenv("LOGS_CHANNEL_ID")

    if bsc and tron:
        print("✅ Blockchain monitoring enabled (BSC & TRON)")
    else:
        print("⚠️ Blockchain monitoring disabled")

    if logs:
        print(f"✅ Logs channel configured: {logs}")
    else:
        print("⚠️ Logs channel not configured")

    print("✅ Bot is now polling for updates...")

    # 🔥 THIS LINE KEEPS THE PROCESS ALIVE
    app.run_polling(close_loop=False)


# ---------------- ENTRY ----------------
if __name__ == "__main__":
    main()

