from dotenv import load_dotenv
load_dotenv()

import sys
import types
if sys.version_info >= (3, 13):
    sys.modules["imghdr"] = types.ModuleType("imghdr")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ChatMemberHandler, MessageHandler, filters
from pyrogram import Client, enums
from pyrogram.errors import FloodWait
from pyrogram.types import ChatPrivileges
import os
import hashlib
import base64
import asyncio
import random
from datetime import datetime, timedelta, timezone, timedelta as td
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import json
import psycopg2
import psycopg2.extras
import pickle
from pyrogram import Client
from pyrogram.errors import RPCError

# ---------------- PYROGRAM CLIENT ----------------
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

pyro_app = Client(
    "escrow_user_session",
    api_id=API_ID,
    api_hash=API_HASH,
)

_pyro_started = False


async def ensure_pyrogram_started():
    global _pyro_started
    if not _pyro_started:
        await pyro_app.start()
        _pyro_started = True
        print("✅ Pyrogram user session started")

async def create_escrow_group(buyer_id: int, seller_id: int, title: str):
    await ensure_pyrogram_started()

    try:
        chat = await pyro_app.create_supergroup(
            title=title,
            description="🔐 PagaL Escrow Transaction Group"
        )

        await pyro_app.add_chat_members(
            chat_id=chat.id,
            user_ids=[buyer_id, seller_id]
        )

        print(f"✅ Escrow group created: {chat.id}")
        return chat.id

    except RPCError as e:
        print("❌ Pyrogram RPC error during group creation:", e)
        raise

    except Exception as e:
        print("❌ Unexpected error during group creation:", e)
        raise

# Bot token from environment variable
BOT_TOKEN = os.getenv("7951713514:AAFhCbUODodyJYyvJqnNJJWqyWMLozX0JBk", "")

# Pyrogram user client credentials
API_ID = os.getenv("26360975", "")
API_HASH = os.getenv("6de01e30d62ce2220eea62c17485e7f7", "")
PHONE = os.getenv("+919234993722", "")

# Admin user IDs (comma-separated)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "7472359048,7880967664,8453993167,2001575810,5825027777,6864194951,8093808661,5229586098,7422906767,7962772947,1166772148,7279906688,1870644348,7338429782,8034627772,7090417167,6526824979,8004116104,7715451354")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()]

# Blockchain API keys
BSCSCAN_API_KEY = os.getenv("1JPI1W7W26UICIYDQNAEE2M1D7A7B3IUIS", "")
TRONGRID_API_KEY = os.getenv("a1743d3b-46da-44b8-9a61-6934ffa7edfe", "")

# Logs channel ID (where group creation logs will be sent)
LOGS_CHANNEL_ID_STR = os.getenv("-1003266978268", "")
try:
    LOGS_CHANNEL_ID = int(LOGS_CHANNEL_ID_STR) if LOGS_CHANNEL_ID_STR else None
except (ValueError, TypeError):
    LOGS_CHANNEL_ID = None

# USDT contract addresses
BSC_USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
TRON_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# Initialize Pyrogram user client (for group creation)
user_client = None
if API_ID and API_HASH and PHONE:
    user_client = Client(
        "escrow_user_session",
        api_id=int(API_ID),
        api_hash=API_HASH,
        phone_number=PHONE
    )

# PostgreSQL database connection
def get_db_connection():
    """Get a connection to the PostgreSQL database"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return psycopg2.connect(db_url)

# Initialize PostgreSQL database
def init_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS escrow_data (
                chat_id BIGINT PRIMARY KEY,
                data BYTEA
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitored_data (
                address TEXT PRIMARY KEY,
                data BYTEA
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ PostgreSQL database initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")

# Load data from database
def load_escrow_roles():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT chat_id, data FROM escrow_data')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        escrow_roles = {}
        for chat_id, data in rows:
            escrow_roles[chat_id] = pickle.loads(data)
        return escrow_roles
    except Exception as e:
        print(f"❌ Failed to load escrow roles: {e}")
        return {}

def load_monitored_addresses():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT address, data FROM monitored_data')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        monitored_addresses = {}
        for address, data in rows:
            monitored_addresses[address] = pickle.loads(data)
        return monitored_addresses
    except Exception as e:
        print(f"❌ Failed to load monitored addresses: {e}")
        return {}

# Save data to database
def save_escrow_roles(escrow_roles):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for chat_id, data in escrow_roles.items():
            cursor.execute('''
                INSERT INTO escrow_data (chat_id, data) VALUES (%s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET data = EXCLUDED.data
            ''', (chat_id, psycopg2.Binary(pickle.dumps(data))))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Failed to save escrow roles: {e}")

def save_monitored_addresses(monitored_addresses):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for address, data in monitored_addresses.items():
            cursor.execute('''
                INSERT INTO monitored_data (address, data) VALUES (%s, %s)
                ON CONFLICT (address) DO UPDATE SET data = EXCLUDED.data
            ''', (address, psycopg2.Binary(pickle.dumps(data))))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Failed to save monitored addresses: {e}")

# Initialize database and load data
init_database()
escrow_roles = load_escrow_roles()  # {chat_id: {'buyer': {...}, 'seller': {...}}}
monitored_addresses = load_monitored_addresses()  # {address: {'chat_id': ..., 'network': ..., 'last_check': ..., 'total_balance': 0}}

# Track fakedepo pending selections (temporary storage for admin command)
fakedepo_pending = {}  # {admin_user_id: target_chat_id}

# Track release confirmations (temporary storage for confirmation workflow)
release_pending = {}  # {message_id: {'chat_id': ..., 'amount': ..., 'buyer_id': ..., 'seller_id': ..., 'buyer_confirmed': False, 'seller_confirmed': False, 'token': ..., 'network': ...}}

# Track refund confirmations (temporary storage for refund confirmation workflow)
refund_pending = {}  # {message_id: {'chat_id': ..., 'amount': ..., 'buyer_id': ..., 'seller_id': ..., 'buyer_confirmed': False, 'seller_confirmed': False, 'token': ..., 'network': ..., 'seller_address': ...}}

def generate_referral_code(user_id):
    """Generate a unique referral code for a user based on their ID"""
    hash_object = hashlib.sha256(str(user_id).encode())
    hash_bytes = hash_object.digest()
    b64_encoded = base64.b64encode(hash_bytes).decode('utf-8')
    referral_code = b64_encoded.replace('/', '').replace('+', '').replace('=', '')[:15].upper()
    return f"ref_{referral_code}"

async def send_group_creation_log(context, chat_id, buyer_username, seller_username, group_type="P2P"):
    """Send group creation log to logs channel"""
    if not LOGS_CHANNEL_ID:
        print(f"⚠️  LOGS_CHANNEL_ID not set - skipping group creation log for chat {chat_id}")
        return
    
    try:
        log_message = f"""📊 <b>NEW ESCROW GROUP CREATED</b>

🆔 <b>Chat ID:</b> <code>{chat_id}</code>
👤 <b>Buyer:</b> {buyer_username}
👤 <b>Seller:</b> {seller_username}
🔖 <b>Type:</b> {group_type}
📅 <b>Time:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}"""
        
        print(f"📤 Attempting to send group creation log to channel {LOGS_CHANNEL_ID}...")
        await context.bot.send_message(
            chat_id=LOGS_CHANNEL_ID,
            text=log_message,
            parse_mode='HTML'
        )
        print(f"✅ Sent group creation log to channel {LOGS_CHANNEL_ID} for chat {chat_id}")
    except Exception as e:
        print(f"❌ Failed to send log to channel {LOGS_CHANNEL_ID}: {type(e).__name__}: {e}")
        print(f"   Make sure the bot is added to the logs channel and is an admin!")

def generate_group_photo(buyer_username, seller_username):
    """Generate group photo with buyer and seller usernames"""
    try:
        # Open the template image
        img = Image.open("attached_assets/Untitled_1762800642304.jpeg")
        draw = ImageDraw.Draw(img)
        
        # Strip whitespace and @ symbol from usernames
        buyer_username = buyer_username.strip().lstrip('@')
        seller_username = seller_username.strip().lstrip('@')
        
        # Try to use fonts that match the template style (bold geometric sans)
        try:
            font = None
            font_paths = [
                "/nix/store/59p03gp3vzbrhd7xjiw3npgbdd68x3y0-dejavu-fonts-2.37/share/fonts/truetype/DejaVuSansCondensed-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
            
            for font_path in font_paths:
                try:
                    # Font size for 800×790 template
                    font = ImageFont.truetype(font_path, 48)
                    break
                except:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Positions for buyer and seller usernames (800×790 template)
        # Position text to the right of "BUYER:" and "SELLER:" labels
        buyer_position = (380, 522)
        seller_position = (380, 618)
        
        # Draw black shadow with 2px offset for depth
        shadow_offset = (2, 2)
        draw.text((buyer_position[0] + shadow_offset[0], buyer_position[1] + shadow_offset[1]), 
                  f"@{buyer_username}", fill="black", font=font)
        draw.text((seller_position[0] + shadow_offset[0], seller_position[1] + shadow_offset[1]), 
                  f"@{seller_username}", fill="black", font=font)
        
        # Draw white text on top
        draw.text(buyer_position, f"@{buyer_username}", fill="white", font=font)
        draw.text(seller_position, f"@{seller_username}", fill="white", font=font)
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        print(f"Error generating group photo: {e}")
        return None

from telegram.error import Forbidden

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
    except Forbidden:
        # User has blocked the bot — ignore silently
        print(f"⚠️ User {update.effective_user.id} has blocked the bot")

    """Handle /start command"""
    welcome_message = """💫 @PagaLEscrowBot 💫
Your Trustworthy Telegram Escrow Service

Welcome to @PagaLEscrowBot. This bot provides a reliable escrow service for your transactions on Telegram.
Avoid scams, your funds are safeguarded throughout your deals. If you run into any issues, simply type /dispute and an arbitrator will join the group chat within 24 hours.

🎟 ESCROW FEE:
1.0% for P2P and 1.0% for OTC Flat

🌐 [UPDATES](https://t.me/BSR_ShoppiE) - [VOUCHES](https://t.me/PagaL_Escrow_Vouches) ☑️

💬 Proceed with /escrow (to start with a new escrow)

⚠️ IMPORTANT - Make sure coin is same of Buyer and Seller else you may loose your coin.

💡 Type /menu to summon a menu with all bots features"""
    
    keyboard = [
        [InlineKeyboardButton("COMMANDS LIST 🤖", callback_data="commands_list")],
        [InlineKeyboardButton("☎️ CONTACT", callback_data="contact")],
        [InlineKeyboardButton("Updates 🔃", url="http://t.me/Escrow_PagaL"), 
         InlineKeyboardButton("Vouches ✔️", url="http://t.me/PagaL_Escrow_Vouches")],
        [InlineKeyboardButton("WHAT IS ESCROW ❔", callback_data="what_is_escrow"),
         InlineKeyboardButton("Instructions 🧑‍🏫", callback_data="instructions")],
        [InlineKeyboardButton("Terms 📝", callback_data="terms")],
        [InlineKeyboardButton("Invites 👤", callback_data="invites")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command - placeholder for now"""
    await update.message.reply_text("📋 Menu functionality coming soon...")

async def escrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /escrow command - show escrow type selection"""
    keyboard = [
        [InlineKeyboardButton("P2P", callback_data="escrow_p2p"),
         InlineKeyboardButton("Product Deal", callback_data="escrow_product")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Please select your escrow type from below.", reply_markup=reply_markup)

async def dispute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dispute command - notify admins and monitor group members"""
    chat = update.effective_chat
    
    # Only work in groups/supergroups
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in escrow groups.</b>",
            parse_mode='HTML'
        )
        return
    
    # Reply to the user
    await update.message.reply_text(
        "<b>ℹ️ Dispute has been raised, Kindly wait till our admin joins you.</b>",
        parse_mode='HTML'
    )
    
    # Make sure bot is in the group and has admin permissions
    try:
        # Check if bot is in the group
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        print(f"Bot status in chat {chat.id}: {bot_member.status}")
        
        # If bot is not admin, promote it
        if bot_member.status != 'administrator':
            print(f"Promoting bot to admin in chat {chat.id}")
            await context.bot.promote_chat_member(
                chat_id=chat.id,
                user_id=context.bot.id,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_post_messages=True
            )
            print(f"✅ Bot promoted to admin in chat {chat.id}")
    except Exception as bot_err:
        print(f"⚠️ Warning: Could not verify/promote bot admin status: {bot_err}")
    
    # Create an invite link for the group
    try:
        # Create invite link limited to 2 members (admins can still join)
        chat_invite = await context.bot.create_chat_invite_link(chat_id=chat.id, member_limit=2)
        invite_link = chat_invite.invite_link
        
        # Get group title
        group_title = chat.title or "Escrow Group"
        
        # Send invite link to all admins
        for admin_id in ADMIN_IDS:
            try:
                admin_message = f"""<b>🚨 DISPUTE RAISED</b>

<b>Group:</b> {group_title}
<b>Chat ID:</b> <code>{chat.id}</code>

<b>Join the group to resolve the dispute:</b>
{invite_link}"""
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"Failed to send dispute notification to admin {admin_id}: {e}")
                
    except Exception as e:
        print(f"Error creating invite link for dispute: {e}")
        await update.message.reply_text(
            "<b>⚠️ Failed to notify admins. Please contact support directly.</b>",
            parse_mode='HTML'
        )

async def dd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dd command - deal details form"""
    chat = update.effective_chat
    chat_id = chat.id
    
    # Reset deal_complete flag when /dd is used (starting a new deal)
    if chat_id in escrow_roles:
        escrow_roles[chat_id]['deal_complete'] = False
        save_escrow_roles(escrow_roles)
    
# Check if this is a group
if chat.type in ['group', 'supergroup']:
    try:
        # Generate random 8-digit number starting with 9
        random_number = random.randint(90000000, 99999999)

        # Get current title to determine group type
        current_title = chat.title

        # Only update if the title doesn't already have a number in parentheses
        if "(" not in current_title:
            # Determine escrow type based on current title
            if "P2P" in current_title:
                new_title = f"P2P Escrow By PAGAL Bot ({random_number})"
            elif "OTC" in current_title:
                new_title = f"OTC Escrow By PAGAL Bot ({random_number})"
            else:
                new_title = f"Product Deal Escrow By PAGAL Bot ({random_number})"

            # Rename the group
            await context.bot.set_chat_title(
                chat_id=chat.id,
                title=new_title
            )
            print(f"✓ Changed group title to: {new_title}")

    except Exception as e:
        print(f"✗ Failed to change group title: {e}")
    
    # Check if this is an OTC group
    is_otc_group = "OTC" in chat.title if chat.title else False
    
    if is_otc_group:
        dd_message = """Hello there,
Kindly tell deal details i.e.

Dealinfo -
Amount -
Conditions ( If Any ) - 

Once filled Seller will use <code>/seller</code> <b>[CRYPTO ADDRESS]</b> and <code>/buyer</code> <b>[CRYPTO ADDRESS]</b> to specify your roles, and start the deal."""
    else:
        dd_message = """Hello there,
Kindly tell deal details i.e.

<code>Quantity -
Rate -
Conditions (if any) -</code>

Remember without it disputes wouldn't be resolved. Once filled proceed with Specifications of the seller or buyer with /seller or /buyer <b>[CRYPTO ADDRESS]</b>"""
    
    await update.message.reply_text(dd_message, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "commands_list":
        commands_message = """📌 AVAILABLE COMMANDS

Here you have a full command list, incase you do like to move through the bot using commands instead of the buttons.

/start - A command to start interacting with the bot
/whatisescrow - A command to tell you more about escrow
/instructions - A command with text instructions
/terms - A command to bring out our TOS
/dispute - A command to contact the admins
/menu - A command to bring out a menu for the bot
/contact - A command to get admin's contact
/commands - A command to get commands list
/stats - A command to check user stats
/vouch - A command to vouch for the bot
/newdeal - A command to start a new deal
/tradeid - A command to get trade id for a chat
/dd - A command to add deal details
/escrow - A command to get a escrow group link
/token - A command to select token for the escrow
/deposit - A command to generate deposit address
/verify - A command to verify wallet address.
/dispute - A command to raise a dispute request
/balance - A command to check the balance of the escrow address
/release - A command to release the funds in the escrow
/refund - A command to refund the funds in the escrow
/seller - A command to set the seller
/buyer - A command to set the buyer
/setfee - A command to set custom trade fee
/save - A command to save default addresses for various chains.
/saved - A command to check saved addresses
/referral - A command to check your referrals"""
        
        keyboard = [[InlineKeyboardButton("BACK", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(commands_message, reply_markup=reply_markup)
    
    elif query.data == "contact":
        contact_message = """☎️ CONTACT ARBITRATOR

💬 Type /dispute

💡 Incase you're not getting a response can reach out to @bsr_official"""
        
        keyboard = [[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(contact_message, reply_markup=reply_markup)
    
    elif query.data == "what_is_escrow":
        await query.answer("**Coming Soon...**", show_alert=True)
    
    elif query.data == "instructions":
        instructions_message = """📘 GUIDE " HOW TO USE @PagaLEscrowBot ( Escrow Bot ) " FOR SAFE AND FASTEST HASSLE-FREE ESCROW 🚀  

Step 1 : Use /escrow command in the DM of the Bot.  
( It will auto-create a safe escrow group and drop the link so that buyer and seller can join via that link. ) 🔗👥  

Step 2 : Use /dd command to initiate the process of escrow where you will get the format to express your deal and info.  
( It will include quantity, rate, TnC's agreed upon by both parties. ) 📝🤝  

Step 3 : Use /buyer ( your address ) if you are a buyer 🛒 or /seller ( your address ) if you are a seller 🏪 to verify address and continue the deal.  
( Provide your crypto address which will be used in case of release or refund. ) 💳🔐  

Step 4 : Choose the token and network by /token command and then either party has to accept it. ✅💱  

Step 5 : Use /deposit command to deposit the asset within the bot.  
( Note : Bot will give the deposit address and it has a time limit to deposit ⏳, you have to deposit within that given time. ) ⏰💸  

Step 6 : Once verified by the bot, you can continue the deal.  
( Bot will send the real-time deposit details in the chat. ) 📊💬  

Step 7 : After a successful deal, you can release the asset to the party by using /release ( amount / all ).  
( Thus, the bot will itself release the asset to the party and send the verification in the chat. ) 🎉💼  

🚨 IN CASE OF ANY DISPUTE OR ISSUE, YOU CAN FEEL FREE TO USE /dispute COMMAND, AND SUPPORT WILL JOIN YOU SHORTLY. 🛎️👩‍💻"""
        
        keyboard = [[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(instructions_message, reply_markup=reply_markup)
    
    elif query.data == "terms":
        terms_message = """📜 TERMS

Our terms of usage are simple.

🎟 Fees
1.0% for P2P and 1.0% for OTC Flat.

Transactions fee will be applicable.

TAKE THIS INTO ACCOUNT WHEN DEPOSITING FUNDS

1️⃣ Record/screenshot the desktop while your perform any testing of logins or data, or recording of physcial items being opened, this is to provide evidence that the data does not work, if the data is working and you are happy to release the funds, you can delete the recording.

FAILURE TO PRODUCE SUFFICIENT EVIDENCE OF TESTING WILL RESULT IN LOSS OF FUNDS

2️⃣ Before you purchase any information, please take the time to learn what you are buying

IT IS NOT THE RESPONSIBILITY OF THE SELLER TO EXPLAIN HOW TO USE THE INFORMATION, ALTHOUGH IT MAY HELP MAKE TRANSACTIONS RUN SMOOTHER IF VENDORS HELP BUYERS

3️⃣ Buyer should ONLY EVER release funds when they RECEIVE WHAT YOU PAID FOR.

WE ARE NOT RESPONSIBLE FOR YOU RELEASING EARLY AND CAN NOT RETRIEVE FUNDS BACK

4️⃣ Users should use trusted local wallets such as electrum.org or exodus wallet to prevent any issues with KYC wallets like Coinbase or Paxful.

ONLINE WALLETS CAN BE SLOW AND BLOCK ACCOUNTS

5️⃣ Our fee's are taken from the balance in the wallet (1.0% for P2P and 1.0% for OTC), so make sure you take that into account when depositing funds.

WE ARE A SERVICE BARE THAT IN MIND

6️⃣ Make sure Coin and Netwwork are same for Buyer and Seller, else you may lose your funds."""
        
        keyboard = [[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(terms_message, reply_markup=reply_markup)
    
    elif query.data == "invites":
        user_id = query.from_user.id
        referral_code = generate_referral_code(user_id)
        
        invites_message = f"""📍 Total Invites: 0 👤  
📍 Tickets: 0 🎟  

💡 Note: Each voucher equals 25.0% off on fees!  

⚡️ For every new user you invite, you get 2 fee tickets.  
⚡️ For every old user (who has already interacted with the bot), you get 1 fee tickets, you can invite them via your referral link too—for the first time ! Yes, you heard it right! We value your previous invites and reward you for them as well.  

Send the link below to users and earn fee reduction tickets for free once they complete minimum $1 worth of Escrows.  

Your Invite Link: 
https://t.me/PagaLEscrowBot?start={referral_code}

Start sharing and enjoy CRAZY fee discounts! 🎉"""
        
        keyboard = [[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(invites_message, reply_markup=reply_markup)

            
            
            # Add the bot to the group
            bot_username = (await context.bot.get_me()).username
            await user_client.add_chat_members(supergroup.id, bot_username)
            
            # Store the group number as the transaction ID for this chat
            # Convert supergroup.id to the actual chat_id format used by bot
            # Pyrogram returns negative IDs, so we use abs() to get the positive part
            bot_chat_id = int(f"-100{abs(supergroup.id)}")
            if bot_chat_id not in escrow_roles:
                escrow_roles[bot_chat_id] = {}
            escrow_roles[bot_chat_id]['transaction_id'] = random_number
            

      )
   )
            
            # Promote user to anonymous admin temporarily to send message on behalf of group
            me = await user_client.get_me()
            await user_client.promote_chat_member(
                chat_id=supergroup.id,
                user_id=me.id,
                privileges=ChatPrivileges(
                    can_manage_chat=True,
                    can_delete_messages=True,
                    can_pin_messages=True,
                    is_anonymous=True
                )
            )
            
            # Small delay for promotion to take effect
            await asyncio.sleep(1)
            
            # Wait for bot admin permissions to propagate
            await asyncio.sleep(2)
            
            # Create invite link using Pyrogram (user client has immediate access)
            invite_link_obj = await user_client.create_chat_invite_link(
                chat_id=supergroup.id,
                member_limit=2
            )
            invite_link = invite_link_obj.invite_link
            print(f"✅ P2P Invite link created successfully: {invite_link}")
            
            # Send anonymous welcome message (appears from the group name)
            welcome_text = """📍 Hey there traders! Welcome to our escrow service.
✅ Please start with /dd command and fill the DealInfo Form"""
            
            sent_message = await user_client.send_message(
                chat_id=supergroup.id,
                text=f"<b>{welcome_text}</b>",
                parse_mode=enums.ParseMode.HTML
            )
            
            # Pin the welcome message
            await user_client.pin_chat_message(
                chat_id=supergroup.id,
                message_id=sent_message.id,
                disable_notification=True
            )
            
            # Delete service messages (join/leave notifications) BEFORE leaving
            try:
                # Get recent messages to find and delete service messages while still in group
                async for message in user_client.get_chat_history(supergroup.id, limit=10):
                    if message.service:
                        await user_client.delete_messages(supergroup.id, message.id)
            except Exception as e:
                print(f"Could not delete service messages: {e}")
            
            # Small delay before leaving
            await asyncio.sleep(1)
            
            # User account leaves the group (and won't rejoin)
            await user_client.leave_chat(supergroup.id)
            
            # Get user's full name
            user_full_name = user.first_name
            if user.last_name:
                user_full_name += f" {user.last_name}"
            
            # Use HTML formatting
            success_message = f"""<b><u>Escrow Group Created</u></b>

<b>Creator: {user_full_name}</b>

<b>Join this escrow group and share the link with the buyer and seller.</b>

<b>{invite_link}</b>

<blockquote>⚠️ Note: This link is for 2 members only—third parties are not allowed to join.</blockquote>"""
            
            await query.edit_message_text(success_message, parse_mode='HTML')
            
        except FloodWait as e:
            await query.edit_message_text(f"⏳ Rate limit hit. Please wait {e.value} seconds and try again.")
        except Exception as e:
            error_message = f"❌ Failed to create escrow group.\n\nPlease try again or contact support.\n\nError: {str(e)}"
            await query.edit_message_text(error_message)
async def button_callback(update, context):
    query = update.callback_query
    await query.answer()

# STEP-2    
if query.data == "escrow_p2p":
    try:
        await ensure_user_client()

        supergroup = await user_client.create_supergroup(
            title=group_name,
            description="PagaL Escrow P2P Group"
        )

    except Exception as e:
        await query.edit_message_text(
            f"❌ Group creation failed.\nPyrogram error: {e}"
        )
        return


lif query.data == "escrow_product":
    try:
        await ensure_user_client()

        supergroup = await user_client.create_supergroup(
            title=group_name,
            description="PagaL Escrow Product Group"
        )

    except Exception as e:
        await query.edit_message_text(
            f"❌ Group creation failed.\nPyrogram error: {e}"
        )
        return


    # continue group creation here

        await query.answer()
        await query.edit_message_text("**Creating a safe trading place for you please wait, please wait...**", parse_mode='Markdown')
        
        if not user_client:
            error_msg = "❌ Group creation is not configured. Please contact the bot administrator."
            await query.edit_message_text(error_msg)
            return
        
        try:
            # Start user client if not started
            if not user_client.is_connected:
                await user_client.start()
            
          
            
            # Generate random 8-digit number starting with 9 (will be added to title after /buyer or /seller)
            random_number = random.randint(90000000, 99999999)
            group_name = f"OTC Escrow By PAGAL Bot"
            
            # Create a supergroup (doesn't require initial members)
            supergroup = await user_client.create_supergroup(
                title=group_name,
                description=""
            )
            
            # Small delay to ensure group is fully created
            await asyncio.sleep(2)
            
            # Add the bot to the group
            bot_username = (await context.bot.get_me()).username
            await user_client.add_chat_members(supergroup.id, bot_username)
            
            # Store the group number as the transaction ID for this chat
            # Convert supergroup.id to the actual chat_id format used by bot
            # Pyrogram returns negative IDs, so we use abs() to get the positive part
            bot_chat_id = int(f"-100{abs(supergroup.id)}")
            if bot_chat_id not in escrow_roles:
                escrow_roles[bot_chat_id] = {}
            escrow_roles[bot_chat_id]['transaction_id'] = random_number
            
            # Small delay before promoting
            await asyncio.sleep(1)
            
            # Promote bot to admin with full permissions
            await user_client.promote_chat_member(
                chat_id=supergroup.id,
                user_id=bot_username,
                privileges=ChatPrivileges(
                    can_manage_chat=True,
                    can_delete_messages=True,
                    can_manage_video_chats=True,
                    can_restrict_members=True,
                    can_promote_members=True,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                    is_anonymous=False
                )
            )
            
            # Promote user to anonymous admin temporarily to send message on behalf of group
            me = await user_client.get_me()
            await user_client.promote_chat_member(
                chat_id=supergroup.id,
                user_id=me.id,
                privileges=ChatPrivileges(
                    can_manage_chat=True,
                    can_delete_messages=True,
                    can_pin_messages=True,
                    is_anonymous=True
                )
            )
            
            # Small delay for promotion to take effect
            await asyncio.sleep(1)
            
            # Wait for bot admin permissions to propagate
            await asyncio.sleep(2)
            
            # Create invite link using Pyrogram (user client has immediate access)
            invite_link_obj = await user_client.create_chat_invite_link(
                chat_id=supergroup.id,
                member_limit=2
            )
            invite_link = invite_link_obj.invite_link
            print(f"✅ Product Invite link created successfully: {invite_link}")
            
            # Send anonymous welcome message (appears from the group name)
            welcome_text = """📍 Hey there traders! Welcome to our escrow service.
✅ Please start with /dd command and fill the DealInfo Form"""
            
            sent_message = await user_client.send_message(
                chat_id=supergroup.id,
                text=f"<b>{welcome_text}</b>",
                parse_mode=enums.ParseMode.HTML
            )
            
            # Pin the welcome message
            await user_client.pin_chat_message(
                chat_id=supergroup.id,
                message_id=sent_message.id,
                disable_notification=True
            )
            
            # Delete service messages (join/leave notifications) BEFORE leaving
            try:
                # Get recent messages to find and delete service messages while still in group
                async for message in user_client.get_chat_history(supergroup.id, limit=10):
                    if message.service:
                        await user_client.delete_messages(supergroup.id, message.id)
            except Exception as e:
                print(f"Could not delete service messages: {e}")
            
            # Small delay before leaving
            await asyncio.sleep(1)
            
            # User account leaves the group (and won't rejoin)
            await user_client.leave_chat(supergroup.id)
            
            # Get user's full name
            user_full_name = user.first_name
            if user.last_name:
                user_full_name += f" {user.last_name}"
            
            # Use HTML formatting
            success_message = f"""<b><u>Escrow Group Created</u></b>

<b>Creator: {user_full_name}</b>

<b>Join this escrow group and share the link with the buyer and seller.</b>

<b>{invite_link}</b>

<blockquote>⚠️ Note: This link is for 2 members only—third parties are not allowed to join.</blockquote>"""
            
            await query.edit_message_text(success_message, parse_mode='HTML')
            
        except FloodWait as e:
            await query.edit_message_text(f"⏳ Rate limit hit. Please wait {e.value} seconds and try again.")
        except Exception as e:
            error_message = f"❌ Failed to create escrow group.\n\nPlease try again or contact support.\n\nError: {str(e)}"
            await query.edit_message_text(error_message)
    
    elif query.data.startswith("token_"):
        # Handle token selection
        await query.answer()
        
        token = query.data.replace("token_", "")
        chat_id = query.message.chat_id
        
        # Store selected token
        if chat_id not in escrow_roles:
            escrow_roles[chat_id] = {}
        escrow_roles[chat_id]['token'] = token
        save_escrow_roles(escrow_roles)
        
        print(f"Token selected: {token} for chat {chat_id}")
        
        # Show network selection based on token
        if token == "USDT":
            keyboard = [
                [InlineKeyboardButton("BSC[BEP20]", callback_data="network_BSC_USDT"),
                 InlineKeyboardButton("TRON[TRC20]", callback_data="network_TRON_USDT")],
                [InlineKeyboardButton("⬅️BACK", callback_data="back_to_token")]
            ]
        elif token == "BTC":
            keyboard = [
                [InlineKeyboardButton("BTC[BTC]", callback_data="network_BTC_BTC")],
                [InlineKeyboardButton("⬅️BACK", callback_data="back_to_token")]
            ]
        elif token == "LTC":
            keyboard = [
                [InlineKeyboardButton("LTC[LTC]", callback_data="network_LTC_LTC"),
                 InlineKeyboardButton("BSC[BEP20]", callback_data="network_BSC_LTC")],
                [InlineKeyboardButton("⬅️BACK", callback_data="back_to_token")]
            ]
        else:
            await query.answer("❌ Unknown token selected!", show_alert=True)
            return
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"""📍<b>ESCROW-CRYPTO DECLARATION</b>

✅ <b>CRYPTO</b>
{token}

<b>Choose network from the list below for {token}</b>"""
        
        await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=reply_markup)
    
    elif query.data.startswith("network_"):
        # Handle network selection
        try:
            parts = query.data.replace("network_", "").split("_")
            network = parts[0]
            token = parts[1]
            chat_id = query.message.chat_id
            
            print(f"Network selection: network={network}, token={token}, chat_id={chat_id}")
            
            # Get buyer and seller info
            if chat_id not in escrow_roles or 'buyer' not in escrow_roles[chat_id] or 'seller' not in escrow_roles[chat_id]:
                print(f"Error: Buyer or seller not set for chat {chat_id}")
                await query.answer("⚠️ Error: Buyer and seller must be set first! Use /buyer and /seller commands.", show_alert=True)
                return
            
            # Answer the callback query after validation
            await query.answer()
            
            buyer_info = escrow_roles[chat_id]['buyer']
            seller_info = escrow_roles[chat_id]['seller']
            token_initiator = escrow_roles[chat_id].get('token_initiator')
            
            print(f"Buyer: {buyer_info['username']}, Seller: {seller_info['username']}, Initiator: {token_initiator}")
            
            # Store token and network for later use
            escrow_roles[chat_id]['selected_token'] = token
            escrow_roles[chat_id]['selected_network'] = network
            save_escrow_roles(escrow_roles)
            
            # Determine who needs to accept/reject
            # If buyer initiated, show seller info and seller accepts/rejects
            # If seller initiated, show buyer info and buyer accepts/rejects
            if token_initiator == buyer_info['user_id']:
                # Buyer initiated, show seller info
                display_info = seller_info
                role_name = "Seller"
            else:
                # Seller initiated, show buyer info
                display_info = buyer_info
                role_name = "Buyer"
            
            # Format network name for display
            network_display = f"{network} NETWORK"
            
            message_text = f"""📍 <b>ESCROW DECLARATION</b>

⚡️ <b>{role_name} {display_info['username']} | Userid: [{display_info['user_id']}]</b>

✅<b>{token} CRYPTO</b>
✅<b>{network_display}</b>"""
            
            # Add Accept/Reject buttons
            keyboard = [
                [InlineKeyboardButton("Accept ✅", callback_data="accept_escrow"),
                 InlineKeyboardButton("Reject ❌", callback_data="reject_escrow")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=reply_markup)
        except Exception as e:
            print(f"Error in network selection: {e}")
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)
    
    elif query.data == "accept_escrow":
        # Handle escrow acceptance
        chat_id = query.message.chat_id
        user_id = query.from_user.id
        
        if chat_id not in escrow_roles:
            await query.answer("Error: Escrow data not found!", show_alert=True)
            return
        
        buyer_info = escrow_roles[chat_id].get('buyer')
        seller_info = escrow_roles[chat_id].get('seller')
        token = escrow_roles[chat_id].get('selected_token')
        network = escrow_roles[chat_id].get('selected_network')
        token_initiator = escrow_roles[chat_id].get('token_initiator')
        
        if not all([buyer_info, seller_info, token, network, token_initiator]):
            await query.answer("Error: Missing escrow information!", show_alert=True)
            return
        
        # Determine who should accept/reject
        # If buyer initiated, only seller can accept/reject
        # If seller initiated, only buyer can accept/reject
        if token_initiator == buyer_info['user_id']:
            # Buyer initiated, only seller can accept
            allowed_user_id = seller_info['user_id']
        else:
            # Seller initiated, only buyer can accept
            allowed_user_id = buyer_info['user_id']
        
        # Check if the person clicking is authorized
        if user_id != allowed_user_id:
            await query.answer("⚠️ Only the other party can accept or reject this escrow!", show_alert=True)
            return
        
        # Format network name for display
        network_display = f"{network} NETWORK"
        
        # Show full escrow declaration with both buyer and seller
        final_message = f"""📍 <b>ESCROW DECLARATION</b>

⚡️ <b>Buyer {buyer_info['username']} | Userid:[{buyer_info['user_id']}]</b>
⚡️ <b>Seller {seller_info['username']} | Userid: [{seller_info['user_id']}]</b>

✅<b>{token} CRYPTO</b>
✅<b>{network_display}</b>"""
        
        await query.edit_message_text(final_message, parse_mode='HTML')
        await query.answer("✅ Escrow accepted!")
        
        # Use existing transaction ID (from group number) or generate new one
        transaction_id = escrow_roles[chat_id].get('transaction_id')
        if not transaction_id:
            # Generate transaction ID (8-digit number starting with 9)
            transaction_id = random.randint(90000000, 99999999)
            escrow_roles[chat_id]['transaction_id'] = transaction_id
        
        # Get current timestamp + 1 minute for trade start time (IST timezone)
        ist = timezone(timedelta(hours=5, minutes=30))
        trade_start_time = (datetime.now(ist) + timedelta(minutes=1)).strftime("%d/%m/%y %H:%M:%S")
        
        # Store trade start time for later use in /deposit
        escrow_roles[chat_id]['trade_start_time'] = trade_start_time
        
        # Determine if OTC group
        chat = await context.bot.get_chat(chat_id=chat_id)
        is_otc_group = "OTC" in chat.title if chat.title else False
        
        # Set release/refund messages based on group type
        if is_otc_group:
            release_msg = "Will Release The Funds To Seller."
            refund_msg = "Will Refund The Funds To Buyer."
        else:
            release_msg = "Will Release The Funds To Buyer."
            refund_msg = "Will Refund The Funds To Seller."
        
        # First, update group photo with buyer and seller usernames
        try:
            print(f"Generating group photo for buyer: {buyer_info['username']}, seller: {seller_info['username']}")
            photo_buffer = generate_group_photo(buyer_info['username'], seller_info['username'])
            if photo_buffer:
                await context.bot.set_chat_photo(chat_id=chat_id, photo=photo_buffer)
                print("✅ Group photo updated successfully")
            else:
                print("⚠️ Photo buffer is None")
        except Exception as e:
            print(f"❌ Error setting chat photo: {e}")
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)
        
        # Check if both buyer and seller have @PagaLEscrowBot in their bio
        buyer_has_bot = buyer_info.get('has_bot_in_bio', False)
        seller_has_bot = seller_info.get('has_bot_in_bio', False)
        
        # Determine fee message
        if buyer_has_bot and seller_has_bot:
            fee_message = "<b>Your Fee is 0.5% as both buyer and seller are using @PagaLEscrowBot in your bio.</b>"
        else:
            fee_message = "<b>Your Fee is 1.0% as both buyer and seller are not using @PagaLEscrowBot in your bio.</b>"
        
        # Send fee message independently
        try:
            await context.bot.send_message(chat_id=chat_id, text=fee_message, parse_mode='HTML')
            print("✅ Fee message sent successfully")
        except Exception as e:
            print(f"❌ Error sending fee message: {e}")
        
        # Small delay
        await asyncio.sleep(0.5)
        
        # Send transaction information message independently (not as a reply)
        transaction_message = f"""📍 <b>TRANSACTION INFORMATION [{transaction_id}]</b>

⚡️ <b>SELLER</b>
<b>{seller_info['username']} | [{seller_info['user_id']}]</b>
{seller_info['address']} <b>[{token}] [{network}]</b>

⚡️ <b>BUYER</b>
<b>{buyer_info['username']} | [{buyer_info['user_id']}]</b>
{buyer_info['address']} <b>[{token}] [{network}]</b>

⏰ <b>Trade Start Time: {trade_start_time}</b>


⚠️ <b>IMPORTANT: Make sure to finalise and agree each-others terms before depositing.</b>

🗒 <b>Please use /deposit command to generate a deposit address for your trade.</b>

<b>Useful commands:</b>
🗒 <code>/release</code> = {release_msg}
🗒 <code>/refund</code> = {refund_msg}"""
        
        try:
            sent_transaction_msg = await context.bot.send_message(
                chat_id=chat_id, 
                text=transaction_message, 
                parse_mode='HTML',
                read_timeout=60,
                write_timeout=60
            )
            print("✅ Transaction message sent successfully")
            
            # Pin the transaction information message
            try:
                await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent_transaction_msg.message_id, disable_notification=True)
                print("✅ Transaction message pinned successfully")
            except Exception as e:
                print(f"⚠️ Error pinning message: {e}")
        except Exception as e:
            print(f"❌ Error sending transaction message: {e}")
        
        # Send log to logs channel with buyer and seller info
        try:
            # Determine group type based on chat title
            chat = await context.bot.get_chat(chat_id=chat_id)
            group_type = "OTC" if "OTC" in chat.title else "P2P"
            
            await send_group_creation_log(
                context=context,
                chat_id=chat_id,
                buyer_username=buyer_info['username'],
                seller_username=seller_info['username'],
                group_type=group_type
            )
        except Exception as e:
            print(f"Error sending log to channel: {e}")
    
    elif query.data == "reject_escrow":
        # Handle escrow rejection - delete the message
        chat_id = query.message.chat_id
        user_id = query.from_user.id
        
        if chat_id not in escrow_roles:
            await query.answer("Error: Escrow data not found!", show_alert=True)
            return
        
        buyer_info = escrow_roles[chat_id].get('buyer')
        seller_info = escrow_roles[chat_id].get('seller')
        token_initiator = escrow_roles[chat_id].get('token_initiator')
        
        if not all([buyer_info, seller_info, token_initiator]):
            await query.answer("Error: Missing escrow information!", show_alert=True)
            return
        
        # Determine who should accept/reject
        if token_initiator == buyer_info['user_id']:
            allowed_user_id = seller_info['user_id']
        else:
            allowed_user_id = buyer_info['user_id']
        
        # Check if the person clicking is authorized
        if user_id != allowed_user_id:
            await query.answer("⚠️ Only the other party can accept or reject this escrow!", show_alert=True)
            return
        
        await query.message.delete()
        await query.answer("❌ Escrow rejected. Message deleted.")
    
    elif query.data.startswith("fakedepo_"):
        # Handle fakedepo network selection
        user_id = query.from_user.id
        
        # Check if this user has a pending fakedepo request
        if user_id not in fakedepo_pending:
            await query.answer("⚠️ No pending fakedepo request found!", show_alert=True)
            return
        
        target_chat_id = fakedepo_pending[user_id]
        
        # Determine which network was selected
        if query.data == "fakedepo_trc20":
            network = "TRON"
            fake_address = "THb2Do8gmwEBocTGaduh73q6EwxfcX9Vx4"
            network_label = "TRC20"
        elif query.data == "fakedepo_bep20":
            network = "BSC"
            fake_address = "0xf282e789e835ed379aea84ece204d2d643e6774f"
            network_label = "BEP20"
        else:
            await query.answer("⚠️ Unknown network selected!", show_alert=True)
            return
        
        # Set the fake deposit address for this chat
        if target_chat_id not in escrow_roles:
            escrow_roles[target_chat_id] = {}
        
        escrow_roles[target_chat_id]['fake_deposit_enabled'] = True
        escrow_roles[target_chat_id]['fake_deposit_network'] = network
        escrow_roles[target_chat_id]['fake_deposit_address'] = fake_address
        
        # Remove from pending
        del fakedepo_pending[user_id]
        
        await query.edit_message_text(
            f"<b>✅ Fakedepo configured successfully!</b>\n\n"
            f"<b>Chat ID:</b> <code>{target_chat_id}</code>\n"
            f"<b>Network:</b> USDT[{network_label}]\n"
            f"<b>Fixed Address:</b> <code>{fake_address}</code>\n\n"
            f"<b>Note:</b> This group will now use the fixed address for USDT[{network}] deposits instead of rotating addresses.",
            parse_mode='HTML'
        )
        await query.answer("✅ Fakedepo configured!")
        print(f"✅ Admin {user_id} configured fakedepo for chat {target_chat_id}: USDT[{network}] -> {fake_address}")
    
    elif query.data == "check_payment_deposit":
        # Handle Check Payment button on deposit message - refresh with current balance
        chat_id = query.message.chat_id
        
        if chat_id not in escrow_roles:
            await query.answer("Error: Escrow data not found!", show_alert=True)
            return
        
        buyer_info = escrow_roles[chat_id].get('buyer')
        seller_info = escrow_roles[chat_id].get('seller')
        token = escrow_roles[chat_id].get('selected_token')
        network = escrow_roles[chat_id].get('selected_network')
        transaction_id = escrow_roles[chat_id].get('transaction_id')
        trade_start_time = escrow_roles[chat_id].get('trade_start_time')
        escrow_address = escrow_roles[chat_id].get('escrow_address')
        
        if not all([buyer_info, seller_info, token, network, transaction_id, trade_start_time, escrow_address]):
            await query.answer("Error: Missing transaction information!", show_alert=True)
            return
        
        # Determine network label based on network
        if network == "BSC":
            network_label = "BSC"
        elif network == "TRON":
            network_label = "TRON"
        elif network == "BTC":
            network_label = "BTC"
        elif network == "LTC":
            network_label = "LTC"
        else:
            network_label = network
        
        # Get current balance from monitored addresses
        monitored_balance = 0
        if escrow_address in monitored_addresses:
            monitored_balance = monitored_addresses[escrow_address]['total_balance']
        
        # Get manually added balance (from /addbalance)
        manual_balance = escrow_roles[chat_id].get('balance', 0)
        
        # Total balance = monitored + manual
        current_balance = monitored_balance + manual_balance
        
        # Calculate time elapsed since deposit request
        last_deposit_time = escrow_roles[chat_id].get('last_deposit_time')
        if last_deposit_time:
            time_elapsed = (datetime.now() - last_deposit_time).total_seconds() / 60
            remaining_time = max(0, 20 - time_elapsed)
        else:
            remaining_time = 20.00
        
        # Determine group type (OTC/Product Deal vs P2P)
        chat = query.message.chat
        is_otc_group = "OTC" in chat.title if chat.title else False
        
        # Set payment instruction based on group type
        if is_otc_group:
            payment_instruction = f"<b>Buyer [{buyer_info['username']}] Will Pay on the Escrow Address, And Click On Check Payment.</b>"
        else:
            payment_instruction = f"<b>Seller [{seller_info['username']}] Will Pay on the Escrow Address, And Click On Check Payment.</b>"
        
        # Set release/refund messages based on group type
        if is_otc_group:
            release_msg = "Will Release The Funds To Seller."
            refund_msg = "Will Refund The Funds To Buyer."
        else:
            release_msg = "Will Release The Funds To Buyer."
            refund_msg = "Will Refund The Funds To Seller."
        
        # Recreate the deposit message with updated balance
        deposit_message = f"""📍 <b>TRANSACTION INFORMATION [{transaction_id}]</b>

⚡️ <b>SELLER</b>
<b>{seller_info['username']} | [<b>{seller_info['user_id']}</b>]</b>
⚡️ <b>BUYER</b>
<b>{buyer_info['username']} | [<b>{buyer_info['user_id']}</b>]</b>
🟢 <b>ESCROW ADDRESS</b>
<code>{escrow_address}</code> <b>[{token}] [{network_label}]</b>

{payment_instruction}

Amount Recieved: <code>{current_balance:.5f}</code> [<b>{current_balance:.2f}$</b>]

⏰ <b>Trade Start Time: {trade_start_time}</b>
⏰ <b>Address Reset In: {remaining_time:.2f} Min</b>

📄 <b>Note: Address will reset after the given time, so make sure to deposit in the bot before the address exprires.</b>
<b>Useful commands:</b>
🗒 <b>/release = {release_msg}</b>
🗒 <b>/refund = {refund_msg}</b>

<b>Remember, once commands are used payment will be released, there is no revert!</b>"""
        
        # Recreate the button
        keyboard = [[InlineKeyboardButton("Check Payment", callback_data="check_payment_deposit")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Edit the message to refresh it
        await query.edit_message_text(
            text=deposit_message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        await query.answer("✅ Payment status refreshed!")
    
    elif query.data == "back_to_token":
        # Go back to token selection
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data="token_BTC"), 
             InlineKeyboardButton("LTC", callback_data="token_LTC")],
            [InlineKeyboardButton("USDT", callback_data="token_USDT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>Choose token from the list below</b>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("release_buyer_confirm_"):
        # Extract chat_id and amount from callback data
        parts = query.data.split("_")
        chat_id = int(parts[3])
        amount = "_".join(parts[4:])
        
        # Find the release pending entry for this message
        message_id = query.message.message_id
        if message_id in release_pending:
            release_data = release_pending[message_id]
            
            # Check if buyer can confirm
            if query.from_user.id == release_data['buyer_id']:
                release_data['buyer_confirmed'] = True
                
                # Update button states
                buyer_status = "✅" if release_data['buyer_confirmed'] else "❌"
                seller_status = "✅" if release_data['seller_confirmed'] else "❌"
                
                # Check if both have confirmed
                if release_data['buyer_confirmed'] and release_data['seller_confirmed']:
                    # Both confirmed - remove buttons
                    reply_markup = InlineKeyboardMarkup([])
                else:
                    # Still waiting for one party - show buttons
                    keyboard = [
                        [InlineKeyboardButton(f"Buyer Confirmation {buyer_status}", callback_data=f"release_buyer_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton(f"Seller Confirmation {seller_status}", callback_data=f"release_seller_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton("Reject ❌", callback_data=f"release_reject_{chat_id}_{amount}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Reconstruct message with proper formatting
                base_message = release_data.get('original_message', query.message.text)
                updated_text = base_message
                if "<b>✅ Buyer Confirmed</b>" not in updated_text:
                    updated_text += "<b>✅ Buyer Confirmed</b>"
                if release_data['seller_confirmed'] and "<b>✅ Seller Confirmed</b>" not in updated_text:
                    updated_text += "\n<b>✅ Seller Confirmed</b>"
                
                await query.edit_message_text(
                    text=updated_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                
                # Send status message if seller hasn't confirmed yet
                if not release_data['seller_confirmed']:
                    buyer_name = release_data['buyer_username'].lstrip('@') if release_data['buyer_username'].startswith('@') else release_data['buyer_username']
                    seller_name = release_data.get('seller_username', 'Seller').lstrip('@') if release_data.get('seller_username', 'Seller').startswith('@') else release_data.get('seller_username', 'Seller')
                    status_msg = f"<b><u>Buyer</u>[<u>@{buyer_name}</u>] have confirmed the Release withdrawl, waiting for <u>Seller</u>[<u>@{seller_name}</u>] confirmation.</b>"
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=status_msg, parse_mode='HTML')
                elif release_data['seller_confirmed']:
                    # Both confirmed - send completion message
                    seller_name = release_data.get('seller_username', 'Seller').lstrip('@') if release_data.get('seller_username', 'Seller').startswith('@') else release_data.get('seller_username', 'Seller')
                    buyer_name = release_data['buyer_username'].lstrip('@') if release_data['buyer_username'].startswith('@') else release_data['buyer_username']
                    both_msg = f"<b>Both <u>Seller</u>[<u>@{seller_name}</u>] and <u>Buyer</u>[<u>@{buyer_name}</u>] have confirmed the Release withdrawl.</b>"
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=both_msg, parse_mode='HTML')
                    
                    # Get escrow balance and send release progress message
                    escrow_balance = escrow_roles[release_data['chat_id']].get('balance', 0)
                    release_progress_msg = f"<b>Release of payment {escrow_balance:.5f} usdt is in progress.</b>"
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=release_progress_msg, parse_mode='HTML')
                    
                    # Wait 10 seconds then send completion message
                    await asyncio.sleep(10)
                    
                    # Calculate amounts after fees
                    network_fee = 0.10
                    # Check if both have bot in bio for 0.5% fee, otherwise 1%
                    both_have_bio = release_data.get('buyer_has_bio', False) and release_data.get('seller_has_bio', False)
                    escrow_fee_percent = 0.005 if both_have_bio else 0.01
                    escrow_fee = escrow_balance * escrow_fee_percent
                    amount_after_fees = escrow_balance - network_fee - escrow_fee
                    
                    # Get token and network info
                    token = escrow_roles[release_data['chat_id']].get('selected_token', 'USDT')
                    network = escrow_roles[release_data['chat_id']].get('selected_network', 'BSC')
                    buyer_name = release_data['buyer_username'].lstrip('@') if release_data['buyer_username'].startswith('@') else release_data['buyer_username']
                    seller_name = release_data.get('seller_username', 'Seller').lstrip('@') if release_data.get('seller_username', 'Seller').startswith('@') else release_data.get('seller_username', 'Seller')
                    
                    # Create completion message
                    completion_msg = f"""<b>{amount_after_fees:.5f} {token} [{amount_after_fees:.2f}$] 💸 + NETWORK FEE has been released to the <u>Buyer</u>'s address! 🚀

Approved By: @{buyer_name} | [{release_data['buyer_id']}]
Thank you for using @PagaLEscrowBot 🙌

@{buyer_name} and @{seller_name}, if you liked the bot please leave a good review about the bot and use command /vouch in reply to the review, and please also mention @PagaLEscrowBot in your vouch.</b>"""
                    
                    # Create Link button to blockchain explorer
                    buyer_address = release_data.get('buyer_address', '')
                    if buyer_address:
                        if network == "BSC":
                            explorer_url = f"https://bscscan.com/address/{buyer_address}"
                        elif network == "TRON":
                            explorer_url = f"https://tronscan.org/#/address/{buyer_address}"
                        else:
                            explorer_url = None
                        
                        if explorer_url:
                            keyboard = [[InlineKeyboardButton("Link", url=explorer_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                        else:
                            reply_markup = None
                    else:
                        reply_markup = None
                    
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=completion_msg, parse_mode='HTML', reply_markup=reply_markup)
                    
                    # Send deal success to logs channel
                    if LOGS_CHANNEL_ID:
                        try:
                            chat_info = await context.bot.get_chat(release_data['chat_id'])
                            group_type = "OTC" if "OTC" in chat_info.title else ("Product Deal" if "Product" in chat_info.title else "P2P")
                            group_link = f"https://t.me/c/{str(chat_info.id)[4:]}/{query.message.message_id}"
                            logs_msg = f"""✅ <b>DEAL SUCCESSFULLY COMPLETED</b> ✅

👤 <b>Buyer:</b> {release_data['buyer_username']}
👤 <b>Seller:</b> {release_data['seller_username']}
📋 <b>Group Type:</b> {group_type}
💰 <b>Amount:</b> [{amount_after_fees:.2f}$]
🔗 <b>Group:</b> <a href="{group_link}">{chat_info.title}</a>"""
                            await context.bot.send_message(chat_id=LOGS_CHANNEL_ID, text=logs_msg, parse_mode='HTML')
                        except Exception as e:
                            print(f"Error sending logs message: {e}")
                    
                    # Deduct released amount from balance
                    try:
                        release_amt = float(amount) if amount.lower() != 'all' else escrow_balance
                        current_balance = escrow_roles[release_data['chat_id']].get('balance', 0)
                        new_balance = max(0, current_balance - release_amt)
                        escrow_roles[release_data['chat_id']]['balance'] = new_balance
                        
                        # Mark deal as complete if balance reaches 0
                        if new_balance <= 0:
                            escrow_roles[release_data['chat_id']]['deal_complete'] = True
                    except:
                        escrow_roles[release_data['chat_id']]['deal_complete'] = True
                    
                    save_escrow_roles(escrow_roles)
                    
                    # Clean up release pending entry
                    del release_pending[message_id]
                
                await query.answer("✅ Buyer confirmed! Waiting for seller confirmation.", show_alert=False)
            else:
                await query.answer("❌ Only the buyer can use this button!", show_alert=True)
        else:
            await query.answer("❌ Confirmation session expired!", show_alert=True)
    
    elif query.data.startswith("release_seller_confirm_"):
        # Extract chat_id and amount from callback data
        parts = query.data.split("_")
        chat_id = int(parts[3])
        amount = "_".join(parts[4:])
        
        # Find the release pending entry for this message
        message_id = query.message.message_id
        if message_id in release_pending:
            release_data = release_pending[message_id]
            
            # Check if seller can confirm
            if query.from_user.id == release_data['seller_id']:
                release_data['seller_confirmed'] = True
                
                # Update button states
                buyer_status = "✅" if release_data['buyer_confirmed'] else "❌"
                seller_status = "✅" if release_data['seller_confirmed'] else "❌"
                
                # Check if both have confirmed
                if release_data['buyer_confirmed'] and release_data['seller_confirmed']:
                    # Both confirmed - remove buttons
                    reply_markup = InlineKeyboardMarkup([])
                else:
                    # Still waiting for one party - show buttons
                    keyboard = [
                        [InlineKeyboardButton(f"Buyer Confirmation {buyer_status}", callback_data=f"release_buyer_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton(f"Seller Confirmation {seller_status}", callback_data=f"release_seller_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton("Reject ❌", callback_data=f"release_reject_{chat_id}_{amount}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Reconstruct message with proper formatting
                base_message = release_data.get('original_message', query.message.text)
                updated_text = base_message
                if release_data['buyer_confirmed'] and "<b>✅ Buyer Confirmed</b>" not in updated_text:
                    updated_text += "<b>✅ Buyer Confirmed</b>"
                if "<b>✅ Seller Confirmed</b>" not in updated_text:
                    updated_text += "\n<b>✅ Seller Confirmed</b>"
                
                await query.edit_message_text(
                    text=updated_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                
                # Check if both have confirmed
                if release_data['buyer_confirmed'] and release_data['seller_confirmed']:
                    # Both confirmed - send completion message
                    seller_name = release_data.get('seller_username', 'Seller').lstrip('@') if release_data.get('seller_username', 'Seller').startswith('@') else release_data.get('seller_username', 'Seller')
                    buyer_name = release_data['buyer_username'].lstrip('@') if release_data['buyer_username'].startswith('@') else release_data['buyer_username']
                    both_msg = f"<b>Both <u>Seller</u>[<u>@{seller_name}</u>] and <u>Buyer</u>[<u>@{buyer_name}</u>] have confirmed the Release withdrawl.</b>"
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=both_msg, parse_mode='HTML')
                    
                    # Get escrow balance and send release progress message
                    escrow_balance = escrow_roles[release_data['chat_id']].get('balance', 0)
                    release_progress_msg = f"<b>Release of payment {escrow_balance:.5f} usdt is in progress.</b>"
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=release_progress_msg, parse_mode='HTML')
                    
                    # Wait 10 seconds then send completion message
                    await asyncio.sleep(10)
                    
                    # Calculate amounts after fees
                    network_fee = 0.10
                    # Check if both have bot in bio for 0.5% fee, otherwise 1%
                    both_have_bio = release_data.get('buyer_has_bio', False) and release_data.get('seller_has_bio', False)
                    escrow_fee_percent = 0.005 if both_have_bio else 0.01
                    escrow_fee = escrow_balance * escrow_fee_percent
                    amount_after_fees = escrow_balance - network_fee - escrow_fee
                    
                    # Get token and network info
                    token = escrow_roles[release_data['chat_id']].get('selected_token', 'USDT')
                    network = escrow_roles[release_data['chat_id']].get('selected_network', 'BSC')
                    buyer_name = release_data['buyer_username'].lstrip('@') if release_data['buyer_username'].startswith('@') else release_data['buyer_username']
                    seller_name = release_data.get('seller_username', 'Seller').lstrip('@') if release_data.get('seller_username', 'Seller').startswith('@') else release_data.get('seller_username', 'Seller')
                    
                    # Create completion message
                    completion_msg = f"""<b>{amount_after_fees:.5f} {token} [{amount_after_fees:.2f}$] 💸 + NETWORK FEE has been released to the <u>Buyer</u>'s address! 🚀

Approved By: @{buyer_name} | [{release_data['buyer_id']}]
Thank you for using @PagaLEscrowBot 🙌

@{buyer_name} and @{seller_name}, if you liked the bot please leave a good review about the bot and use command /vouch in reply to the review, and please also mention @PagaLEscrowBot in your vouch.</b>"""
                    
                    # Create Link button to blockchain explorer
                    buyer_address = release_data.get('buyer_address', '')
                    if buyer_address:
                        if network == "BSC":
                            explorer_url = f"https://bscscan.com/address/{buyer_address}"
                        elif network == "TRON":
                            explorer_url = f"https://tronscan.org/#/address/{buyer_address}"
                        else:
                            explorer_url = None
                        
                        if explorer_url:
                            keyboard = [[InlineKeyboardButton("Link", url=explorer_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                        else:
                            reply_markup = None
                    else:
                        reply_markup = None
                    
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=completion_msg, parse_mode='HTML', reply_markup=reply_markup)
                    
                    # Send deal success to logs channel
                    if LOGS_CHANNEL_ID:
                        try:
                            chat_info = await context.bot.get_chat(release_data['chat_id'])
                            group_type = "OTC" if "OTC" in chat_info.title else ("Product Deal" if "Product" in chat_info.title else "P2P")
                            group_link = f"https://t.me/c/{str(chat_info.id)[4:]}/{query.message.message_id}"
                            logs_msg = f"""✅ <b>DEAL SUCCESSFULLY COMPLETED</b> ✅

👤 <b>Buyer:</b> {release_data['buyer_username']}
👤 <b>Seller:</b> {release_data['seller_username']}
📋 <b>Group Type:</b> {group_type}
💰 <b>Amount:</b> [{amount_after_fees:.2f}$]
🔗 <b>Group:</b> <a href="{group_link}">{chat_info.title}</a>"""
                            await context.bot.send_message(chat_id=LOGS_CHANNEL_ID, text=logs_msg, parse_mode='HTML')
                        except Exception as e:
                            print(f"Error sending logs message: {e}")
                    
                    # Deduct the released amount from the balance
                    escrow_roles[release_data['chat_id']]['balance'] -= escrow_balance
                    
                    # Mark deal as complete only if balance reaches 0
                    if escrow_roles[release_data['chat_id']]['balance'] <= 0:
                        escrow_roles[release_data['chat_id']]['deal_complete'] = True
                    
                    save_escrow_roles(escrow_roles)
                    
                    # Clean up release pending entry
                    del release_pending[message_id]
                else:
                    # Only seller confirmed, send status message
                    seller_name = release_data.get('seller_username', 'Seller').lstrip('@') if release_data.get('seller_username', 'Seller').startswith('@') else release_data.get('seller_username', 'Seller')
                    buyer_name = release_data['buyer_username'].lstrip('@') if release_data['buyer_username'].startswith('@') else release_data['buyer_username']
                    status_msg = f"<b><u>Seller</u>[<u>@{seller_name}</u>] have confirmed the Release withdrawl, waiting for <u>Buyer</u>[<u>@{buyer_name}</u>] confirmation.</b>"
                    await context.bot.send_message(chat_id=release_data['chat_id'], text=status_msg, parse_mode='HTML')
                
                await query.answer("✅ Seller confirmed! Waiting for buyer confirmation.", show_alert=False)
            else:
                await query.answer("❌ Only the seller can use this button!", show_alert=True)
        else:
            await query.answer("❌ Confirmation session expired!", show_alert=True)
    
    elif query.data.startswith("release_reject_"):
        # Extract chat_id and amount from callback data
        parts = query.data.split("_")
        chat_id = int(parts[2])
        amount = "_".join(parts[3:])
        
        # Find the release pending entry for this message
        message_id = query.message.message_id
        if message_id in release_pending:
            release_data = release_pending[message_id]
            
            # Only buyer or seller can reject
            if query.from_user.id in [release_data['buyer_id'], release_data['seller_id']]:
                await query.edit_message_text(
                    text="<b>❌ Release confirmation rejected. Transaction cancelled.</b>",
                    parse_mode='HTML'
                )
                await query.answer("❌ Release cancelled!", show_alert=False)
                # Clean up release pending entry
                del release_pending[message_id]
            else:
                await query.answer("❌ Only buyer or seller can reject!", show_alert=True)
        else:
            await query.answer("❌ Confirmation session expired!", show_alert=True)
    
    elif query.data.startswith("refund_buyer_confirm_"):
        # Extract chat_id and amount from callback data
        parts = query.data.split("_")
        chat_id = int(parts[3])
        amount = "_".join(parts[4:])
        
        # Find the refund pending entry for this message
        message_id = query.message.message_id
        if message_id in refund_pending:
            refund_data = refund_pending[message_id]
            
            # Check if buyer can confirm
            if query.from_user.id == refund_data['buyer_id']:
                refund_data['buyer_confirmed'] = True
                
                # Update button states
                buyer_status = "✅" if refund_data['buyer_confirmed'] else "❌"
                seller_status = "✅" if refund_data['seller_confirmed'] else "❌"
                
                # Check if both have confirmed
                if refund_data['buyer_confirmed'] and refund_data['seller_confirmed']:
                    # Both confirmed - remove buttons
                    reply_markup = InlineKeyboardMarkup([])
                else:
                    # Still waiting for one party - show buttons
                    keyboard = [
                        [InlineKeyboardButton(f"Buyer Confirmation {buyer_status}", callback_data=f"refund_buyer_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton(f"Seller Confirmation {seller_status}", callback_data=f"refund_seller_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton("Reject ❌", callback_data=f"refund_reject_{chat_id}_{amount}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Reconstruct message with proper formatting
                base_message = refund_data.get('original_message', query.message.text)
                updated_text = base_message
                if "<b>✅ Buyer Confirmed</b>" not in updated_text:
                    updated_text += "<b>✅ Buyer Confirmed</b>"
                if refund_data['seller_confirmed'] and "<b>✅ Seller Confirmed</b>" not in updated_text:
                    updated_text += "\n<b>✅ Seller Confirmed</b>"
                
                await query.edit_message_text(
                    text=updated_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                
                # Send status message if seller hasn't confirmed yet
                if not refund_data['seller_confirmed']:
                    buyer_name = refund_data['buyer_username'].lstrip('@') if refund_data['buyer_username'].startswith('@') else refund_data['buyer_username']
                    seller_name = refund_data.get('seller_username', 'Seller').lstrip('@') if refund_data.get('seller_username', 'Seller').startswith('@') else refund_data.get('seller_username', 'Seller')
                    status_msg = f"<b><u>Buyer</u>[<u>@{buyer_name}</u>] have confirmed the Refund, waiting for <u>Seller</u>[<u>@{seller_name}</u>] confirmation.</b>"
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=status_msg, parse_mode='HTML')
                elif refund_data['seller_confirmed']:
                    # Both confirmed - send completion message
                    seller_name = refund_data.get('seller_username', 'Seller').lstrip('@') if refund_data.get('seller_username', 'Seller').startswith('@') else refund_data.get('seller_username', 'Seller')
                    buyer_name = refund_data['buyer_username'].lstrip('@') if refund_data['buyer_username'].startswith('@') else refund_data['buyer_username']
                    both_msg = f"<b>Both <u>Seller</u>[<u>@{seller_name}</u>] and <u>Buyer</u>[<u>@{buyer_name}</u>] have confirmed the Refund.</b>"
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=both_msg, parse_mode='HTML')
                    
                    # Get escrow balance and send refund progress message
                    escrow_balance = escrow_roles[refund_data['chat_id']].get('balance', 0)
                    refund_progress_msg = f"<b>Refund of payment {escrow_balance:.5f} usdt is in progress.</b>"
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=refund_progress_msg, parse_mode='HTML')
                    
                    # Wait 10 seconds then send completion message
                    await asyncio.sleep(10)
                    
                    # Calculate amounts after fees
                    network_fee = 0.10
                    # Check if both have bot in bio for 0.5% fee, otherwise 1%
                    both_have_bio = release_data.get('buyer_has_bio', False) and release_data.get('seller_has_bio', False)
                    escrow_fee_percent = 0.005 if both_have_bio else 0.01
                    escrow_fee = escrow_balance * escrow_fee_percent
                    amount_after_fees = escrow_balance - network_fee - escrow_fee
                    
                    # Get token and network info
                    token = escrow_roles[refund_data['chat_id']].get('selected_token', 'USDT')
                    network = escrow_roles[refund_data['chat_id']].get('selected_network', 'BSC')
                    buyer_name = refund_data['buyer_username'].lstrip('@') if refund_data['buyer_username'].startswith('@') else refund_data['buyer_username']
                    seller_name = refund_data.get('seller_username', 'Seller').lstrip('@') if refund_data.get('seller_username', 'Seller').startswith('@') else refund_data.get('seller_username', 'Seller')
                    
                    # Create completion message
                    completion_msg = f"""<b>{amount_after_fees:.5f} {token} [{amount_after_fees:.2f}$] 💸 + NETWORK FEE has been refunded to the <u>Seller</u>'s address! 🚀

Approved By: @{seller_name} | [{refund_data['seller_id']}]
Thank you for using @PagaLEscrowBot 🙌

@{buyer_name} and @{seller_name}, if you liked the bot please leave a good review about the bot and use command /vouch in reply to the review, and please also mention @PagaLEscrowBot in your vouch.</b>"""
                    
                    # Create Link button to blockchain explorer
                    seller_address = refund_data.get('seller_address', '')
                    if seller_address:
                        if network == "BSC":
                            explorer_url = f"https://bscscan.com/address/{seller_address}"
                        elif network == "TRON":
                            explorer_url = f"https://tronscan.org/#/address/{seller_address}"
                        else:
                            explorer_url = None
                        
                        if explorer_url:
                            keyboard = [[InlineKeyboardButton("Link", url=explorer_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                        else:
                            reply_markup = None
                    else:
                        reply_markup = None
                    
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=completion_msg, parse_mode='HTML', reply_markup=reply_markup)
                    
                    # Send deal success to logs channel
                    if LOGS_CHANNEL_ID:
                        try:
                            chat_info = await context.bot.get_chat(refund_data['chat_id'])
                            group_type = "OTC" if "OTC" in chat_info.title else ("Product Deal" if "Product" in chat_info.title else "P2P")
                            group_link = f"https://t.me/c/{str(chat_info.id)[4:]}/{query.message.message_id}"
                            logs_msg = f"""✅ <b>DEAL SUCCESSFULLY COMPLETED</b> ✅

👤 <b>Buyer:</b> {refund_data['buyer_username']}
👤 <b>Seller:</b> {refund_data['seller_username']}
📋 <b>Group Type:</b> {group_type}
💰 <b>Amount:</b> [{amount_after_fees:.2f}$]
🔗 <b>Group:</b> <a href="{group_link}">{chat_info.title}</a>"""
                            await context.bot.send_message(chat_id=LOGS_CHANNEL_ID, text=logs_msg, parse_mode='HTML')
                        except Exception as e:
                            print(f"Error sending logs message: {e}")
                    
                    # Mark deal as complete
                    escrow_roles[refund_data['chat_id']]['deal_complete'] = True
                    save_escrow_roles(escrow_roles)
                    
                    # Clean up refund pending entry
                    del refund_pending[message_id]
                
                await query.answer("✅ Buyer confirmed! Waiting for seller confirmation.", show_alert=False)
            else:
                await query.answer("❌ Only the buyer can use this button!", show_alert=True)
        else:
            await query.answer("❌ Confirmation session expired!", show_alert=True)
    
    elif query.data.startswith("refund_seller_confirm_"):
        # Extract chat_id and amount from callback data
        parts = query.data.split("_")
        chat_id = int(parts[3])
        amount = "_".join(parts[4:])
        
        # Find the refund pending entry for this message
        message_id = query.message.message_id
        if message_id in refund_pending:
            refund_data = refund_pending[message_id]
            
            # Check if seller can confirm
            if query.from_user.id == refund_data['seller_id']:
                refund_data['seller_confirmed'] = True
                
                # Update button states
                buyer_status = "✅" if refund_data['buyer_confirmed'] else "❌"
                seller_status = "✅" if refund_data['seller_confirmed'] else "❌"
                
                # Check if both have confirmed
                if refund_data['buyer_confirmed'] and refund_data['seller_confirmed']:
                    # Both confirmed - remove buttons
                    reply_markup = InlineKeyboardMarkup([])
                else:
                    # Still waiting for one party - show buttons
                    keyboard = [
                        [InlineKeyboardButton(f"Buyer Confirmation {buyer_status}", callback_data=f"refund_buyer_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton(f"Seller Confirmation {seller_status}", callback_data=f"refund_seller_confirm_{chat_id}_{amount}")],
                        [InlineKeyboardButton("Reject ❌", callback_data=f"refund_reject_{chat_id}_{amount}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Reconstruct message with proper formatting
                base_message = refund_data.get('original_message', query.message.text)
                updated_text = base_message
                if refund_data['buyer_confirmed'] and "<b>✅ Buyer Confirmed</b>" not in updated_text:
                    updated_text += "<b>✅ Buyer Confirmed</b>"
                if "<b>✅ Seller Confirmed</b>" not in updated_text:
                    updated_text += "\n<b>✅ Seller Confirmed</b>"
                
                await query.edit_message_text(
                    text=updated_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                
                # Check if both have confirmed
                if refund_data['buyer_confirmed'] and refund_data['seller_confirmed']:
                    # Both confirmed - send completion message
                    seller_name = refund_data.get('seller_username', 'Seller').lstrip('@') if refund_data.get('seller_username', 'Seller').startswith('@') else refund_data.get('seller_username', 'Seller')
                    buyer_name = refund_data['buyer_username'].lstrip('@') if refund_data['buyer_username'].startswith('@') else refund_data['buyer_username']
                    both_msg = f"<b>Both <u>Seller</u>[<u>@{seller_name}</u>] and <u>Buyer</u>[<u>@{buyer_name}</u>] have confirmed the Refund.</b>"
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=both_msg, parse_mode='HTML')
                    
                    # Get escrow balance and send refund progress message
                    escrow_balance = escrow_roles[refund_data['chat_id']].get('balance', 0)
                    refund_progress_msg = f"<b>Refund of payment {escrow_balance:.5f} usdt is in progress.</b>"
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=refund_progress_msg, parse_mode='HTML')
                    
                    # Wait 10 seconds then send completion message
                    await asyncio.sleep(10)
                    
                    # Calculate amounts after fees
                    network_fee = 0.10
                    # Check if both have bot in bio for 0.5% fee, otherwise 1%
                    both_have_bio = release_data.get('buyer_has_bio', False) and release_data.get('seller_has_bio', False)
                    escrow_fee_percent = 0.005 if both_have_bio else 0.01
                    escrow_fee = escrow_balance * escrow_fee_percent
                    amount_after_fees = escrow_balance - network_fee - escrow_fee
                    
                    # Get token and network info
                    token = escrow_roles[refund_data['chat_id']].get('selected_token', 'USDT')
                    network = escrow_roles[refund_data['chat_id']].get('selected_network', 'BSC')
                    buyer_name = refund_data['buyer_username'].lstrip('@') if refund_data['buyer_username'].startswith('@') else refund_data['buyer_username']
                    seller_name = refund_data.get('seller_username', 'Seller').lstrip('@') if refund_data.get('seller_username', 'Seller').startswith('@') else refund_data.get('seller_username', 'Seller')
                    
                    # Create completion message
                    completion_msg = f"""<b>{amount_after_fees:.5f} {token} [{amount_after_fees:.2f}$] 💸 + NETWORK FEE has been refunded to the <u>Seller</u>'s address! 🚀

Approved By: @{seller_name} | [{refund_data['seller_id']}]
Thank you for using @PagaLEscrowBot 🙌

@{buyer_name} and @{seller_name}, if you liked the bot please leave a good review about the bot and use command /vouch in reply to the review, and please also mention @PagaLEscrowBot in your vouch.</b>"""
                    
                    # Create Link button to blockchain explorer
                    seller_address = refund_data.get('seller_address', '')
                    if seller_address:
                        if network == "BSC":
                            explorer_url = f"https://bscscan.com/address/{seller_address}"
                        elif network == "TRON":
                            explorer_url = f"https://tronscan.org/#/address/{seller_address}"
                        else:
                            explorer_url = None
                        
                        if explorer_url:
                            keyboard = [[InlineKeyboardButton("Link", url=explorer_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                        else:
                            reply_markup = None
                    else:
                        reply_markup = None
                    
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=completion_msg, parse_mode='HTML', reply_markup=reply_markup)
                    
                    # Send deal success to logs channel
                    if LOGS_CHANNEL_ID:
                        try:
                            chat_info = await context.bot.get_chat(refund_data['chat_id'])
                            group_type = "OTC" if "OTC" in chat_info.title else ("Product Deal" if "Product" in chat_info.title else "P2P")
                            group_link = f"https://t.me/c/{str(chat_info.id)[4:]}/{query.message.message_id}"
                            logs_msg = f"""✅ <b>DEAL SUCCESSFULLY COMPLETED</b> ✅

👤 <b>Buyer:</b> {refund_data['buyer_username']}
👤 <b>Seller:</b> {refund_data['seller_username']}
📋 <b>Group Type:</b> {group_type}
💰 <b>Amount:</b> [{amount_after_fees:.2f}$]
🔗 <b>Group:</b> <a href="{group_link}">{chat_info.title}</a>"""
                            await context.bot.send_message(chat_id=LOGS_CHANNEL_ID, text=logs_msg, parse_mode='HTML')
                        except Exception as e:
                            print(f"Error sending logs message: {e}")
                    
                    # Deduct refunded amount from balance
                    try:
                        refund_amt = float(amount) if amount.lower() != 'all' else escrow_balance
                        current_balance = escrow_roles[refund_data['chat_id']].get('balance', 0)
                        new_balance = max(0, current_balance - refund_amt)
                        escrow_roles[refund_data['chat_id']]['balance'] = new_balance
                        
                        # Mark deal as complete if balance reaches 0
                        if new_balance <= 0:
                            escrow_roles[refund_data['chat_id']]['deal_complete'] = True
                    except:
                        escrow_roles[refund_data['chat_id']]['deal_complete'] = True
                    
                    save_escrow_roles(escrow_roles)
                    
                    # Clean up refund pending entry
                    del refund_pending[message_id]
                else:
                    # Only seller confirmed, send status message
                    seller_name = refund_data.get('seller_username', 'Seller').lstrip('@') if refund_data.get('seller_username', 'Seller').startswith('@') else refund_data.get('seller_username', 'Seller')
                    buyer_name = refund_data['buyer_username'].lstrip('@') if refund_data['buyer_username'].startswith('@') else refund_data['buyer_username']
                    status_msg = f"<b><u>Seller</u>[<u>@{seller_name}</u>] have confirmed the Refund, waiting for <u>Buyer</u>[<u>@{buyer_name}</u>] confirmation.</b>"
                    await context.bot.send_message(chat_id=refund_data['chat_id'], text=status_msg, parse_mode='HTML')
                
                await query.answer("✅ Seller confirmed! Waiting for buyer confirmation.", show_alert=False)
            else:
                await query.answer("❌ Only the seller can use this button!", show_alert=True)
        else:
            await query.answer("❌ Confirmation session expired!", show_alert=True)
    
    elif query.data.startswith("refund_reject_"):
        # Extract chat_id and amount from callback data
        parts = query.data.split("_")
        chat_id = int(parts[2])
        amount = "_".join(parts[3:])
        
        # Find the refund pending entry for this message
        message_id = query.message.message_id
        if message_id in refund_pending:
            refund_data = refund_pending[message_id]
            
            # Only buyer or seller can reject
            if query.from_user.id in [refund_data['buyer_id'], refund_data['seller_id']]:
                await query.edit_message_text(
                    text="<b>❌ Refund confirmation rejected. Transaction cancelled.</b>",
                    parse_mode='HTML'
                )
                await query.answer("❌ Refund cancelled!", show_alert=False)
                # Clean up refund pending entry
                del refund_pending[message_id]
            else:
                await query.answer("❌ Only buyer or seller can reject!", show_alert=True)
        else:
            await query.answer("❌ Confirmation session expired!", show_alert=True)
    
    elif query.data == "back_to_start":
        welcome_message = """💫 @PagaLEscrowBot 💫
Your Trustworthy Telegram Escrow Service

Welcome to @PagaLEscrowBot. This bot provides a reliable escrow service for your transactions on Telegram.
Avoid scams, your funds are safeguarded throughout your deals. If you run into any issues, simply type /dispute and an arbitrator will join the group chat within 24 hours.

🎟 ESCROW FEE:
1.0% for P2P and 1.0% for OTC Flat

🌐 [UPDATES](https://t.me/BSR_ShoppiE) - [VOUCHES](https://t.me/PagaL_Escrow_Vouches) ☑️

💬 Proceed with /escrow (to start with a new escrow)

⚠️ IMPORTANT - Make sure coin is same of Buyer and Seller else you may loose your coin.

💡 Type /menu to summon a menu with all bots features"""
        
        keyboard = [
            [InlineKeyboardButton("COMMANDS LIST 🤖", callback_data="commands_list")],
            [InlineKeyboardButton("☎️ CONTACT", callback_data="contact")],
            [InlineKeyboardButton("Updates 🔃", url="http://t.me/Escrow_PagaL"), 
             InlineKeyboardButton("Vouches ✔️", url="http://t.me/PagaL_Escrow_Vouches")],
            [InlineKeyboardButton("WHAT IS ESCROW ❔", callback_data="what_is_escrow"),
             InlineKeyboardButton("Instructions 🧑‍🏫", callback_data="instructions")],
            [InlineKeyboardButton("Terms 📝", callback_data="terms")],
            [InlineKeyboardButton("Invites 👤", callback_data="invites")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def buyer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buyer command with crypto address"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Check if deal is already complete
    if chat_id in escrow_roles and escrow_roles[chat_id].get('deal_complete', False):
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if command has arguments (crypto address)
    if not context.args or len(context.args) == 0:
        # Send image with usage instructions
        caption = (
            "<code>/buyer [Your Crypto Address]</code>\n\n"
            "⛓️ <b>Chains Supported:</b> ltc, tron, bsc, btc"
        )
        try:
            with open('attached_assets/photo_6316666496414845910_y_1763710254477.jpg', 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode='HTML'
                )
        except FileNotFoundError:
            # Fallback to text if image not found
            await update.message.reply_text(caption, parse_mode='HTML')
        return
    
    # Get the crypto address from arguments
    crypto_address = " ".join(context.args)
    
    # Get username (or use first name if no username)
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    
    # Initialize chat in escrow_roles if not exists
    if chat_id not in escrow_roles:
        escrow_roles[chat_id] = {}
        save_escrow_roles(escrow_roles)
    
    # Check if buyer role is already set by another user (ROLE LOCKING)
    if 'buyer' in escrow_roles[chat_id]:
        existing_buyer_id = escrow_roles[chat_id]['buyer']['user_id']
        if existing_buyer_id != user_id:
            existing_buyer_username = escrow_roles[chat_id]['buyer']['username']
            await update.message.reply_text(
                f"⚠️ <b>Buyer role is already set by {existing_buyer_username}!</b>\n\n"
                f"Only {existing_buyer_username} can update the buyer information.",
                parse_mode='HTML'
            )
            return
    
    # Check if user has @PagaLEscrowBot in their bio using both Bot API and Pyrogram
    has_bot_in_bio = False
    
    # Try Bot API first
    try:
        user_chat = await context.bot.get_chat(user_id)
        if user_chat.bio and "@PagaLEscrowBot" in user_chat.bio:
            has_bot_in_bio = True
            print(f"✅ Bio detected via Bot API for user {user_id}")
    except Exception as e:
        print(f"Bot API bio check failed for user {user_id}: {e}")
    
    # If Bot API didn't detect bio and Pyrogram is available, try with Pyrogram
    if not has_bot_in_bio and user_client:
        try:
            # Start Pyrogram client if not connected
            if not user_client.is_connected:
                await user_client.start()
            
            pyrogram_user = await user_client.get_users(user_id)
            if hasattr(pyrogram_user, 'bio') and pyrogram_user.bio and "@PagaLEscrowBot" in pyrogram_user.bio:
                has_bot_in_bio = True
                print(f"✅ Bio detected via Pyrogram for user {user_id}")
        except Exception as pyro_error:
            print(f"Pyrogram bio check failed for user {user_id}: {pyro_error}")
    
    # Format the message
    response_message = f"""📍<b>ESCROW-ROLE DECLARATION</b>

⚡️ <b>BUYER {username} | Userid: [{user_id}]</b>

✅ <b>BUYER WALLET</b>
<code>{crypto_address}</code>

<i>Note: If you don't see any address, then your address will used from saved addresses after selecting token and chain for the current escrow.</i>"""
    
    # Only reply if update.message exists (not a callback query)
    if update.message:
        sent_message = await update.message.reply_text(response_message, parse_mode='HTML')
    else:
        # If called from callback, send message directly to chat
        sent_message = await context.bot.send_message(chat_id=chat_id, text=response_message, parse_mode='HTML')
    
    # Check if buyer was already set before
    buyer_already_set = 'buyer' in escrow_roles[chat_id]
    
    # Store buyer information
    escrow_roles[chat_id]['buyer'] = {
        'user_id': user_id,
        'username': username,
        'address': crypto_address,
        'has_bot_in_bio': has_bot_in_bio
    }
    save_escrow_roles(escrow_roles)
    
    # Rename group with transaction ID (8-digit number) if not already renamed
    try:
        if not escrow_roles[chat_id].get('group_renamed', False):
            # Get transaction ID (from group creation)
            transaction_id = escrow_roles[chat_id].get('transaction_id')
            if transaction_id:
                # Get current group info
                chat = await context.bot.get_chat(chat_id)
                current_title = chat.title
                
                # Only rename if transaction ID is not already in the title
                if str(transaction_id) not in current_title:
                    # Determine escrow type based on current title
                    if "P2P" in current_title:
                        new_title = f"P2P Escrow By PAGAL Bot ({transaction_id})"
                    elif "OTC" in current_title:
                        new_title = f"OTC Escrow By PAGAL Bot ({transaction_id})"
                    else:
                        new_title = f"Product Deal Escrow By PAGAL Bot ({transaction_id})"
                    
                    # Rename the group
                    await context.bot.set_chat_title(chat_id=chat_id, title=new_title)
                    escrow_roles[chat_id]['group_renamed'] = True
                    print(f"✅ Group renamed to: {new_title}")
    except Exception as e:
        print(f"Error renaming group in /buyer: {e}")
    
    # Only prompt if buyer was NOT already set before
    if not buyer_already_set:
        # Check if seller is already set
        if 'seller' not in escrow_roles[chat_id]:
            # Seller not set, prompt for seller
            if update.message:
                await update.message.reply_text(
                    "<b>Please set seller using /seller [DEPOSIT ADDRESS]</b>",
                    parse_mode='HTML'
                )
        else:
            # Both buyer and seller are set
            if update.message:
                await update.message.reply_text(
                    "<b>Use /token to Choose crypto.</b>",
                    parse_mode='HTML'
                )

async def seller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /seller command with crypto address"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Check if deal is already complete
    if chat_id in escrow_roles and escrow_roles[chat_id].get('deal_complete', False):
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if command has arguments (crypto address)
    if not context.args or len(context.args) == 0:
        # Send image with usage instructions
        caption = (
            "<code>/seller [Your Crypto Address]</code>\n\n"
            "⛓️ <b>Chains Supported:</b> ltc, tron, bsc, btc"
        )
        try:
            with open('attached_assets/photo_6314481552062090385_y_1763710249793.jpg', 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode='HTML'
                )
        except FileNotFoundError:
            # Fallback to text if image not found
            await update.message.reply_text(caption, parse_mode='HTML')
        return
    
    # Get the crypto address from arguments
    crypto_address = " ".join(context.args)
    
    # Get username (or use first name if no username)
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    
    # Initialize chat in escrow_roles if not exists
    if chat_id not in escrow_roles:
        escrow_roles[chat_id] = {}
        save_escrow_roles(escrow_roles)
    
    # Check if seller role is already set by another user (ROLE LOCKING)
    if 'seller' in escrow_roles[chat_id]:
        existing_seller_id = escrow_roles[chat_id]['seller']['user_id']
        if existing_seller_id != user_id:
            existing_seller_username = escrow_roles[chat_id]['seller']['username']
            await update.message.reply_text(
                f"⚠️ <b>Seller role is already set by {existing_seller_username}!</b>\n\n"
                f"Only {existing_seller_username} can update the seller information.",
                parse_mode='HTML'
            )
            return
    
    # Check if user has @PagaLEscrowBot in their bio using both Bot API and Pyrogram
    has_bot_in_bio = False
    
    # Try Bot API first
    try:
        user_chat = await context.bot.get_chat(user_id)
        if user_chat.bio and "@PagaLEscrowBot" in user_chat.bio:
            has_bot_in_bio = True
            print(f"✅ Bio detected via Bot API for user {user_id}")
    except Exception as e:
        print(f"Bot API bio check failed for user {user_id}: {e}")
    
    # If Bot API didn't detect bio and Pyrogram is available, try with Pyrogram
    if not has_bot_in_bio and user_client:
        try:
            # Start Pyrogram client if not connected
            if not user_client.is_connected:
                await user_client.start()
            
            pyrogram_user = await user_client.get_users(user_id)
            if hasattr(pyrogram_user, 'bio') and pyrogram_user.bio and "@PagaLEscrowBot" in pyrogram_user.bio:
                has_bot_in_bio = True
                print(f"✅ Bio detected via Pyrogram for user {user_id}")
        except Exception as pyro_error:
            print(f"Pyrogram bio check failed for user {user_id}: {pyro_error}")
    
    # Format the message
    response_message = f"""📍<b>ESCROW-ROLE DECLARATION</b>

⚡️ <b>SELLER {username} | Userid: [{user_id}]</b>

✅ <b>SELLER WALLET</b>
<code>{crypto_address}</code>

<i>Note: If you don't see any address, then your address will used from saved addresses after selecting token and chain for the current escrow.</i>"""
    
    # Only reply if update.message exists (not a callback query)
    if update.message:
        sent_message = await update.message.reply_text(response_message, parse_mode='HTML')
    else:
        # If called from callback, send message directly to chat
        sent_message = await context.bot.send_message(chat_id=chat_id, text=response_message, parse_mode='HTML')
    
    # Check if seller was already set before
    seller_already_set = 'seller' in escrow_roles[chat_id]
    
    # Store seller information
    escrow_roles[chat_id]['seller'] = {
        'user_id': user_id,
        'username': username,
        'address': crypto_address,
        'has_bot_in_bio': has_bot_in_bio
    }
    save_escrow_roles(escrow_roles)
    
    # Rename group with transaction ID (8-digit number) if not already renamed
    try:
        if not escrow_roles[chat_id].get('group_renamed', False):
            # Get transaction ID (from group creation)
            transaction_id = escrow_roles[chat_id].get('transaction_id')
            if transaction_id:
                # Get current group info
                chat = await context.bot.get_chat(chat_id)
                current_title = chat.title
                
                # Only rename if transaction ID is not already in the title
                if str(transaction_id) not in current_title:
                    # Determine escrow type based on current title
                    if "P2P" in current_title:
                        new_title = f"P2P Escrow By PAGAL Bot ({transaction_id})"
                    elif "OTC" in current_title:
                        new_title = f"OTC Escrow By PAGAL Bot ({transaction_id})"
                    else:
                        new_title = f"Product Deal Escrow By PAGAL Bot ({transaction_id})"
                    
                    # Rename the group
                    await context.bot.set_chat_title(chat_id=chat_id, title=new_title)
                    escrow_roles[chat_id]['group_renamed'] = True
                    print(f"✅ Group renamed to: {new_title}")
    except Exception as e:
        print(f"Error renaming group in /seller: {e}")
    
    # Only prompt if seller was NOT already set before
    if not seller_already_set:
        # Check if buyer is already set
        if 'buyer' not in escrow_roles[chat_id]:
            # Buyer not set, prompt for buyer
            await update.message.reply_text(
                "<b>Please set buyer using /buyer [DEPOSIT ADDRESS]</b>",
                parse_mode='HTML'
            )
        else:
            # Both buyer and seller are set
            await update.message.reply_text(
                "<b>Use /token to Choose crypto.</b>",
                parse_mode='HTML'
            )

async def token_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /token command to choose cryptocurrency"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if buyer and seller are set
    buyer_set = chat_id in escrow_roles and 'buyer' in escrow_roles[chat_id]
    seller_set = chat_id in escrow_roles and 'seller' in escrow_roles[chat_id]
    
    if not buyer_set and not seller_set:
        await update.message.reply_text(
            "⚠️ Please set both buyer and seller first using /buyer and /seller commands."
        )
        return
    elif not buyer_set:
        await update.message.reply_text(
            "⚠️ Please set buyer first using /buyer [DEPOSIT ADDRESS]"
        )
        return
    elif not seller_set:
        await update.message.reply_text(
            "⚠️ Please set seller first using /seller [DEPOSIT ADDRESS]"
        )
        return
    
    # Store who initiated the /token command
    escrow_roles[chat_id]['token_initiator'] = user_id
    
    # Create token selection buttons
    keyboard = [
        [InlineKeyboardButton("BTC", callback_data="token_BTC"), 
         InlineKeyboardButton("LTC", callback_data="token_LTC")],
        [InlineKeyboardButton("USDT", callback_data="token_USDT")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>Choose token from the list below</b>",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deposit command to generate deposit address"""
    chat_id = update.effective_chat.id
    
    # Check if escrow data exists
    if chat_id not in escrow_roles:
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if buyer and seller are set
    buyer_info = escrow_roles[chat_id].get('buyer')
    seller_info = escrow_roles[chat_id].get('seller')
    
    if not buyer_info and not seller_info:
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    elif not buyer_info:
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    elif not seller_info:
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if token and network are selected
    token = escrow_roles[chat_id].get('selected_token')
    network = escrow_roles[chat_id].get('selected_network')
    
    if not token or not network:
        await update.message.reply_text(
            "⚠️ Please select token and network first using /token command."
        )
        return
    
    # Check if deposit was used recently (20-minute cooldown)
    last_deposit_time = escrow_roles[chat_id].get('last_deposit_time')
    if last_deposit_time:
        time_elapsed = (datetime.now() - last_deposit_time).total_seconds() / 60  # in minutes
        if time_elapsed < 20:
            remaining_minutes = 20 - time_elapsed
            await update.message.reply_text(
                f"⏳ <b>Please wait {remaining_minutes:.1f} minutes before requesting a new deposit address.</b>\n\n"
                f"<b>Address will reset after 20 minutes from the last request.</b>",
                parse_mode='HTML'
            )
            return
    
    # Show initial waiting message
    waiting_msg = await update.message.reply_text("Requesting a deposit address for you please wait...")
    
    # Get transaction ID if exists, or generate new one
    transaction_id = escrow_roles[chat_id].get('transaction_id')
    if not transaction_id:
        transaction_id = random.randint(90000000, 99999999)
        escrow_roles[chat_id]['transaction_id'] = transaction_id
        save_escrow_roles(escrow_roles)
    
    # Get trade start time if exists, or use current time + 1 minute (IST timezone)
    trade_start_time = escrow_roles[chat_id].get('trade_start_time')
    if not trade_start_time:
        ist = timezone(timedelta(hours=5, minutes=30))
        trade_start_time = (datetime.now(ist) + timedelta(minutes=1)).strftime("%d/%m/%y %H:%M:%S")
        escrow_roles[chat_id]['trade_start_time'] = trade_start_time
        save_escrow_roles(escrow_roles)
    
    # Check if fakedepo is enabled for this chat
    fake_deposit_enabled = escrow_roles[chat_id].get('fake_deposit_enabled', False)
    fake_deposit_network = escrow_roles[chat_id].get('fake_deposit_network')
    fake_deposit_address = escrow_roles[chat_id].get('fake_deposit_address')
    
    # Determine escrow address and network label based on network
    if token == "USDT":
        if network == "BSC":
            # Check if fakedepo is enabled for BSC
            if fake_deposit_enabled and fake_deposit_network == "BSC":
                escrow_address = fake_deposit_address
            else:
                # Alternate between two BSC addresses
                bsc_addresses = [
                    "0xDA4c2a5B876b0c7521e1c752690D8705080000fE",
                    "0xf282e789e835ed379aea84ece204d2d643e6774f"
                ]
                escrow_address = random.choice(bsc_addresses)
            network_label = "BSC"
        elif network == "TRON":
            # Check if fakedepo is enabled for TRON
            if fake_deposit_enabled and fake_deposit_network == "TRON":
                escrow_address = fake_deposit_address
            else:
                # Alternate between two TRON addresses
                tron_addresses = [
                    "TVsTYwseYdRXUKk2ehcEcTT4UU3b2tqrVm",
                    "TXFyTRL3vau3DJe6kyxqUeazoscN8dRrHB"
                ]
                escrow_address = random.choice(tron_addresses)
            network_label = "TRON"
        else:
            await update.message.reply_text("⚠️ Unsupported network for deposit.")
            return
    elif token == "BTC":
        if network == "BTC":
            # Alternate between two BTC addresses
            btc_addresses = [
                "bc1qya2u04hfdy5j9mnzds7effh0xqx3mvwcyflnak",
                "bc1q43nwc38ashvvzhakw7ma7227yzd3yfkmpudl48"
            ]
            escrow_address = random.choice(btc_addresses)
            network_label = "BTC"
        else:
            await update.message.reply_text("⚠️ Unsupported network for BTC.")
            return
    elif token == "LTC":
        if network == "LTC":
            # Alternate between two LTC addresses
            ltc_addresses = [
                "ltc1qya2u04hfdy5j9mnzds7effh0xqx3mvwcq49h9x",
                "ltc1qfu7asf36pmg5kc4wge5dcz6t5yd3pyn3d86w66"
            ]
            escrow_address = random.choice(ltc_addresses)
            network_label = "LTC"
        elif network == "BSC":
            # Alternate between two BSC addresses (same as USDT[BSC])
            bsc_addresses = [
                "0xDA4c2a5B876b0c7521e1c752690D8705080000fE",
                "0xf282e789e835ed379aea84ece204d2d643e6774f"
            ]
            escrow_address = random.choice(bsc_addresses)
            network_label = "BSC"
        else:
            await update.message.reply_text("⚠️ Unsupported network for LTC.")
            return
    else:
        await update.message.reply_text(f"⚠️ Deposit is currently not supported for {token}.")
        return
    
    # Determine group type (OTC/Product Deal vs P2P)
    chat = update.effective_chat
    is_otc_group = "OTC" in chat.title if chat.title else False
    
    # Set payment instruction based on group type
    if is_otc_group:
        payment_instruction = f"<b>Buyer [{buyer_info['username']}] Will Pay on the Escrow Address, And Click On Check Payment.</b>"
    else:
        payment_instruction = f"<b>Seller [{seller_info['username']}] Will Pay on the Escrow Address, And Click On Check Payment.</b>"
    
    # Set release/refund messages based on group type
    if is_otc_group:
        release_msg = "Will Release The Funds To Seller."
        refund_msg = "Will Refund The Funds To Buyer."
    else:
        release_msg = "Will Release The Funds To Buyer."
        refund_msg = "Will Refund The Funds To Seller."
    
    # Check for existing balance (manual balance added by admin)
    manual_balance = escrow_roles[chat_id].get('balance', 0)
    initial_balance = manual_balance  # At deposit time, only manual balance exists
    
    # Create deposit information message
    deposit_message = f"""📍 <b>TRANSACTION INFORMATION [{transaction_id}]</b>

⚡️ <b>SELLER</b>
<b>{seller_info['username']} | [<b>{seller_info['user_id']}</b>]</b>
⚡️ <b>BUYER</b>
<b>{buyer_info['username']} | [<b>{buyer_info['user_id']}</b>]</b>
🟢 <b>ESCROW ADDRESS</b>
<code>{escrow_address}</code> <b>[{token}] [{network_label}]</b>

{payment_instruction}

Amount Recieved: <code>{initial_balance:.5f}</code> [<b>{initial_balance:.2f}$</b>]

⏰ <b>Trade Start Time: {trade_start_time}</b>
⏰ <b>Address Reset In: 20.00 Min</b>

📄 <b>Note: Address will reset after the given time, so make sure to deposit in the bot before the address exprires.</b>
<b>Useful commands:</b>
🗒 <b>/release = {release_msg}</b>
🗒 <b>/refund = {refund_msg}</b>

<b>Remember, once commands are used payment will be released, there is no revert!</b>"""
    
    # Create "Check Payment" button only
    keyboard = [[InlineKeyboardButton("Check Payment", callback_data="check_payment_deposit")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Delete waiting message
    await waiting_msg.delete()
    
    # Send deposit information as reply to /deposit command
    deposit_msg = await update.message.reply_text(deposit_message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Pin the deposit message so it stays visible
    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=deposit_msg.message_id)
        print(f"✅ Deposit message pinned in chat {chat_id}")
    except Exception as e:
        print(f"⚠️ Failed to pin deposit message: {e}")
    
    # Store the deposit message ID for later refreshing
    escrow_roles[chat_id]['deposit_message_id'] = deposit_msg.message_id
    
    # Store the current time as last deposit time
    escrow_roles[chat_id]['last_deposit_time'] = datetime.now()
    
    # Store the escrow address for transaction button
    escrow_roles[chat_id]['escrow_address'] = escrow_address
    save_escrow_roles(escrow_roles)
    
    # Start monitoring this address for deposits
    monitored_addresses[escrow_address] = {
        'chat_id': chat_id,
        'network': network,
        'token': token,
        'network_label': network_label,
        'total_balance': 0,
        'last_check': datetime.now()
    }
    save_monitored_addresses(monitored_addresses)
    
    print(f"Started monitoring {network} address {escrow_address} for chat {chat_id}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command to show current escrow balance"""
    chat_id = update.effective_chat.id
    
    # Check if escrow data exists
    if chat_id not in escrow_roles:
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Get the stored escrow address
    escrow_address = escrow_roles[chat_id].get('escrow_address')
    
    if not escrow_address:
        await update.message.reply_text(
            "⚠️ No deposit address found. Please use /deposit command first to generate an escrow address."
        )
        return
    
    # Get current balance from monitored addresses
    monitored_balance = 0
    if escrow_address in monitored_addresses:
        monitored_balance = monitored_addresses[escrow_address]['total_balance']
    
    # Get manually added balance (from /add or /addbalance commands)
    manual_balance = escrow_roles[chat_id].get('balance', 0)
    
    # Total balance is monitored + manual
    current_balance = monitored_balance + manual_balance
    
    # Format message: everything bold except amount (monospace) and USD value (bold+underline)
    balance_message = f"<b>Current Escrow Balance is: <code>{current_balance:.5f}</code>usdt <u>{current_balance:.2f}$</u></b>"
    
    await update.message.reply_text(balance_message, parse_mode='HTML')

async def addbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addbalance command to manually add balance to escrow"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Check if escrow data exists
    if chat_id not in escrow_roles:
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Parse command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>⚠️ Usage: /addbalance [amount]</b>\n\n"
            "<b>Example:</b> <code>/addbalance 1000</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount = float(context.args[0])
        if amount <= 0:
            await update.message.reply_text(
                "<b>❌ Amount must be a positive number.</b>",
                parse_mode='HTML'
            )
            return
    except ValueError:
        await update.message.reply_text(
            "<b>❌ Invalid amount. Please enter a valid number.</b>\n\n"
            "<b>Example:</b> <code>/addbalance 1000</code>",
            parse_mode='HTML'
        )
        return
    
    # Get current balance
    current_balance = escrow_roles[chat_id].get('balance', 0)
    
    # Add to balance
    new_balance = current_balance + amount
    escrow_roles[chat_id]['balance'] = new_balance
    save_escrow_roles(escrow_roles)
    
    # Send confirmation with the format requested: Amount Received: 500.00 [500.00$]
    await update.message.reply_text(
        f"<b>✅ Balance updated successfully!</b>\n\n"
        f"<b>Amount Received:</b> {new_balance:.2f} [{new_balance:.2f}$]\n\n"
        f"<b>Use /balance to check current escrow balance.</b>",
        parse_mode='HTML'
    )
    print(f"✅ Balance added: {amount} USDT for chat {chat_id}. New balance: {new_balance}")

async def check_bsc_transactions(address):
    """Check BSC USDT transactions for an address"""
    if not BSCSCAN_API_KEY:
        return []
    
    url = f"https://api.bscscan.com/api"
    params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': BSC_USDT_CONTRACT,
        'address': address,
        'startblock': 0,
        'endblock': 999999999,
        'sort': 'desc',
        'apikey': BSCSCAN_API_KEY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get('status') == '1' and data.get('result'):
                    # Filter incoming transactions only (to this address)
                    incoming = [tx for tx in data['result'] if tx['to'].lower() == address.lower()]
                    return incoming
                return []
    except Exception as e:
        print(f"Error checking BSC transactions: {e}")
        return []

async def check_tron_transactions(address):
    """Check TRON USDT (TRC20) transactions for an address"""
    if not TRONGRID_API_KEY:
        return []
    
    url = f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20"
    params = {
        'limit': 100,
        'contract_address': TRON_USDT_CONTRACT
    }
    headers = {
        'TRON-PRO-API-KEY': TRONGRID_API_KEY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                data = await response.json()
                if data.get('success') and data.get('data'):
                    # Filter incoming transactions only (to this address)
                    incoming = [tx for tx in data['data'] if tx['to'] == address]
                    return incoming
                return []
    except Exception as e:
        print(f"Error checking TRON transactions: {e}")
        return []

async def check_btc_transactions(address):
    """Check BTC transactions for an address using Blockchair API"""
    url = f"https://blockchair.com/api/v1/bitcoin/addresses/{address}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data.get('data') and address in data['data']:
                    addr_info = data['data'][address]
                    # Get transactions for this address
                    if addr_info.get('transactions'):
                        # Return transactions (each represents satoshis received)
                        return [{'value': str(int(addr_info.get('received', 0))), 'hash': 'BTC-TX'}]
                return []
    except Exception as e:
        print(f"Error checking BTC transactions: {e}")
        return []

async def check_ltc_transactions(address):
    """Check LTC transactions for an address using Blockchair API"""
    url = f"https://blockchair.com/api/v1/litecoin/addresses/{address}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data.get('data') and address in data['data']:
                    addr_info = data['data'][address]
                    # Get transactions for this address
                    if addr_info.get('transactions'):
                        # Return transactions (each represents litoshis received)
                        return [{'value': str(int(addr_info.get('received', 0))), 'hash': 'LTC-TX'}]
                return []
    except Exception as e:
        print(f"Error checking LTC transactions: {e}")
        return []

async def monitor_deposits(bot_app):
    """Background task to monitor escrow addresses for deposits"""
    while True:
        try:
            for address, info in list(monitored_addresses.items()):
                chat_id = info['chat_id']
                network = info['network']
                network_label = info['network_label']
                token = info['token']
                current_balance = info['total_balance']
                
                # Check transactions based on network
                transactions = []
                decimals = 8  # Default for BTC and LTC
                
                if network == "BSC":
                    transactions = await check_bsc_transactions(address)
                    decimals = 18  # BSC USDT has 18 decimals
                    token_name = "BSC-USDT"
                elif network == "TRON":
                    transactions = await check_tron_transactions(address)
                    decimals = 6  # TRON USDT has 6 decimals
                    token_name = "TRON-USDT"
                elif network == "BTC":
                    transactions = await check_btc_transactions(address)
                    decimals = 8  # BTC has 8 decimals (satoshis)
                    token_name = "BTC"
                elif network == "LTC":
                    transactions = await check_ltc_transactions(address)
                    decimals = 8  # LTC has 8 decimals (litoshis)
                    token_name = "LTC"
                
                # Calculate total received
                total_received = 0
                for tx in transactions:
                    total_received += int(tx['value']) / (10 ** decimals)
                
                # If new deposit detected
                if total_received > current_balance:
                    new_amount = total_received - current_balance
                    monitored_addresses[address]['total_balance'] = total_received
                    save_monitored_addresses(monitored_addresses)
                    
                    # Determine if OTC group for release/refund messages
                    try:
                        chat = await bot_app.bot.get_chat(chat_id=chat_id)
                        is_otc_group = "OTC" in chat.title if chat.title else False
                    except:
                        is_otc_group = False
                    
                    # Set release/refund messages based on group type
                    if is_otc_group:
                        release_msg = "Will Release The Funds To Seller."
                        refund_msg = "Will Refund The Funds To Buyer."
                    else:
                        release_msg = "Will Release The Funds To Buyer."
                        refund_msg = "Will Refund The Funds To Seller."
                    
                    # Get the most recent transaction hash
                    tx_hash = None
                    if transactions:
                        latest_tx = transactions[0]  # Most recent transaction
                        if network == "BSC":
                            tx_hash = latest_tx.get('hash')
                        elif network == "TRON":
                            tx_hash = latest_tx.get('transaction_id')
                        elif network in ["BTC", "LTC"]:
                            tx_hash = latest_tx.get('hash')
                    
                    # Send deposit confirmation message
                    confirmation_message = f"""<b>Deposit 💵 has been confirmed

🪙 Token: {token_name}
💰 Amount: {new_amount:.5f}[{new_amount:.2f}$]
💸 Balance: {total_received:.5f}[{total_received:.2f}$]

Now you can proceed with the Deal✅

Useful commands:
🗒 <code>/release</code> = {release_msg}
🗒 <code>/refund</code> = {refund_msg}</b>"""
                    
                    # Create transaction button with explorer link (if available)
                    explorer_url = None
                    if network == "BSC":
                        if tx_hash:
                            explorer_url = f"https://bscscan.com/tx/{tx_hash}"
                        else:
                            explorer_url = f"https://bscscan.com/address/{address}"
                    elif network == "TRON":
                        if tx_hash:
                            explorer_url = f"https://tronscan.org/#/transaction/{tx_hash}"
                        else:
                            explorer_url = f"https://tronscan.org/#/address/{address}"
                    elif network == "BTC":
                        explorer_url = f"https://blockchain.com/btc/address/{address}"
                    elif network == "LTC":
                        explorer_url = f"https://blockchair.com/litecoin/address/{address}"
                    
                    keyboard = None
                    if explorer_url:
                        keyboard = [[InlineKeyboardButton("Transaction ➡️", url=explorer_url)]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                    else:
                        reply_markup = None
                    
                    try:
                        await bot_app.bot.send_message(
                            chat_id=chat_id,
                            text=confirmation_message,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                        print(f"✅ Deposit detected: {new_amount} USDT on {network} for chat {chat_id}")
                    except Exception as e:
                        print(f"Failed to send deposit notification: {e}")
        
        except Exception as e:
            print(f"Error in deposit monitoring: {e}")
        
        # Check every 10 seconds for faster detection
        await asyncio.sleep(10)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command - manually confirm deposit"""
    user = update.effective_user
    
    # Check if command is used in DM
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in bot's DM.</b>",
            parse_mode='HTML'
        )
        return
    
    # Parse command arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "<b>⚠️ Usage: /add [amount] [chat_id]</b>\n\n"
            "<b>Example:</b> <code>/add 500 -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount = float(context.args[0])
        chat_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "<b>❌ Invalid format. Amount must be a number and chat_id must be an integer.</b>\n\n"
            "<b>Example:</b> <code>/add 500 -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    # Get token info and escrow address from escrow data if available
    token_info = "BSC-USDT"
    network = "BSC"
    escrow_address = None
    current_balance = 0
    
    if chat_id in escrow_roles:
        token = escrow_roles[chat_id].get('selected_token', 'USDT')
        network = escrow_roles[chat_id].get('selected_network', 'BSC')
        token_info = f"{network}-{token}"
        escrow_address = escrow_roles[chat_id].get('escrow_address')
        current_balance = escrow_roles[chat_id].get('balance', 0)
    
    # Calculate new balance (add to existing balance)
    new_balance = current_balance + amount
    
    # Determine if OTC group for release/refund messages
    try:
        chat = await context.bot.get_chat(chat_id=chat_id)
        is_otc_group = "OTC" in chat.title if chat.title else False
    except:
        is_otc_group = False
    
    # Set release/refund messages based on group type
    if is_otc_group:
        release_msg = "Will Release The Funds To <b><u>Seller</u></b>."
        refund_msg = "Will Refund The Funds To <b><u>Buyer</u></b>."
    else:
        release_msg = "Will Release The Funds To <b><u>Buyer</u></b>."
        refund_msg = "Will Refund The Funds To <b><u>Seller</u></b>."
    
    # Send confirmation message to the group
    confirmation_message = f"""<b><u>Deposit 💵 has been confirmed</u>

🪙 <b>Token:</b> {token_info}
💰 <b>Amount:</b> {amount:.5f}[{amount:.2f}$]
💸 <b>Balance:</b> {new_balance:.5f}[{new_balance:.2f}$]

Now you can proceed with the Deal✅

<b>Useful commands:</b>
🗒 <code>/release</code> = {release_msg}
🗒 <code>/refund</code> = {refund_msg}</b>"""
    
    # Create transaction button if escrow address is available
    reply_markup = None
    if escrow_address:
        if network == "BSC":
            explorer_url = f"https://bscscan.com/address/{escrow_address}"
        elif network == "TRON":
            explorer_url = f"https://tronscan.org/#/address/{escrow_address}"
        else:
            explorer_url = None
        
        if explorer_url:
            keyboard = [[InlineKeyboardButton("Transaction ➡️", url=explorer_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=confirmation_message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Update balance in escrow_roles if chat exists
        if chat_id in escrow_roles:
            escrow_roles[chat_id]['deposit_confirmed'] = True
            escrow_roles[chat_id]['balance'] = new_balance
            save_escrow_roles(escrow_roles)
        
        await update.message.reply_text(
            f"<b>✅ Deposit confirmation sent to chat {chat_id}</b>\n"
            f"<b>Amount Added:</b> ${amount:.2f}\n"
            f"<b>Total Balance:</b> ${new_balance:.2f}",
            parse_mode='HTML'
        )
        print(f"✅ Admin {user.id} manually confirmed deposit of ${amount} for chat {chat_id}")
    except Exception as e:
        await update.message.reply_text(
            f"<b>❌ Failed to send message to chat {chat_id}</b>\n\n"
            f"<b>Error:</b> {str(e)}\n\n"
            "<b>Make sure:</b>\n"
            "• The chat ID is correct\n"
            "• The bot is a member of that group",
            parse_mode='HTML'
        )
        print(f"❌ Failed to send deposit confirmation: {e}")

async def fakedepo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fakedepo command - set specific deposit address for testing"""
    user = update.effective_user
    
    # Check if command is used in DM
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in bot's DM.</b>",
            parse_mode='HTML'
        )
        return
    
    # Parse command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>⚠️ Usage: /fakedepo [chat_id]</b>\n\n"
            "<b>Example:</b> <code>/fakedepo -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        target_chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "<b>❌ Invalid format. Chat ID must be an integer.</b>\n\n"
            "<b>Example:</b> <code>/fakedepo -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    # Check if group already used /deposit
    if target_chat_id in escrow_roles and escrow_roles[target_chat_id].get('last_deposit_time'):
        await update.message.reply_text(
            "<b>❌ This group has already used /deposit command.</b>\n\n"
            "<b>Fakedepo is only available for groups that haven't requested a deposit address yet.</b>",
            parse_mode='HTML'
        )
        return
    
    # Store the target chat ID for this admin
    fakedepo_pending[user.id] = target_chat_id
    
    # Show network selection buttons
    keyboard = [
        [InlineKeyboardButton("USDT[TRC20]", callback_data="fakedepo_trc20")],
        [InlineKeyboardButton("USDT[BEP20]", callback_data="fakedepo_bep20")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"<b>Which network of USDT for chat {target_chat_id}?</b>",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /link command - restricted to CEO and OWNER only"""
    user = update.effective_user
    
    # Check if user is CEO (Venom) or OWNER (Suraj)
    CEO_ID = 5229586098
    OWNER_ID = 6864194951
    ALLOWED_LINK_USERS = [CEO_ID, OWNER_ID]
    
    if user.id not in ALLOWED_LINK_USERS:
        await update.message.reply_text(
            "<b>Sorry This Command Can Only Be Used By CEO [ Venom ] or OWNER [ Suraj ].</b>",
            parse_mode='HTML'
        )
        return
    
    # Parse command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>⚠️ Usage: /link [chat_id]</b>\n\n"
            "<b>Example:</b> <code>/link -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        target_chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "<b>❌ Invalid format. Chat ID must be an integer.</b>\n\n"
            "<b>Example:</b> <code>/link -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    # Generate invite link with member limit of 2 (for both CEO and OWNER)
    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=target_chat_id,
            member_limit=2,
            creates_join_request=False
        )
        
        await update.message.reply_text(
            f"<b>✅ Invite link generated for chat {target_chat_id}:</b>\n\n"
            f"{invite_link.invite_link}\n\n"
            f"<i>Note: This link is limited to 2 members only.</i>",
            parse_mode='HTML'
        )
        print(f"✅ Admin {user.id} generated invite link for chat {target_chat_id}")
    except Exception as e:
        await update.message.reply_text(
            f"<b>❌ Failed to generate invite link for chat {target_chat_id}</b>\n\n"
            f"<b>Error:</b> {str(e)}\n\n"
            "<b>Make sure:</b>\n"
            "• The chat ID is correct\n"
            "• The bot is a member of that group\n"
            "• The bot has permission to create invite links",
            parse_mode='HTML'
        )
        print(f"❌ Failed to generate invite link: {e}")

async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /revoke command - admin only, revoke all invite links for a chat"""
    user = update.effective_user
    
    print(f"🔍 /revoke command called by user {user.id} ({user.username or user.first_name})")
    print(f"   Admin IDs: {ADMIN_IDS}")
    print(f"   Is admin: {user.id in ADMIN_IDS}")
    
    # Check if user is an admin
    if user.id not in ADMIN_IDS:
        print(f"   ❌ User {user.id} is not an admin")
        await update.message.reply_text(
            "<b>⚠️ This command is only available for admins.</b>",
            parse_mode='HTML'
        )
        return
    
    print(f"   ✅ User {user.id} is an admin, proceeding")
    
    # Parse command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>⚠️ Usage: /revoke [chat_id]</b>\n\n"
            "<b>Example:</b> <code>/revoke -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        target_chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "<b>❌ Invalid format. Chat ID must be an integer.</b>\n\n"
            "<b>Example:</b> <code>/revoke -1001234567890</code>",
            parse_mode='HTML'
        )
        return
    
    # Revoke all invite links for the chat
    try:
        # Get the primary invite link
        primary_link = await context.bot.export_chat_invite_link(chat_id=target_chat_id)
        print(f"Primary link: {primary_link}")
        
        # Get the invite link URL string
        invite_link_str = primary_link.invite_link if hasattr(primary_link, 'invite_link') else str(primary_link)
        print(f"Revoking invite link: {invite_link_str}")
        
        # Revoke using the invite link string
        revoked = await context.bot.revoke_chat_invite_link(
            chat_id=target_chat_id,
            invite_link=invite_link_str
        )
        
        await update.message.reply_text(
            f"<b>✅ All invite links have been revoked for chat {target_chat_id}</b>\n\n"
            "<b>New invite links can only be generated using /link command.</b>",
            parse_mode='HTML'
        )
        print(f"✅ Admin {user.id} revoked all invite links for chat {target_chat_id}")
    except Exception as e:
        print(f"❌ Revoke error details: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"<b>❌ Failed to revoke invite links for chat {target_chat_id}</b>\n\n"
            f"<b>Error:</b> {str(e)}\n\n"
            "<b>Make sure:</b>\n"
            "• The chat ID is correct\n"
            "• The bot is a member of that group\n"
            "• The bot has permission to revoke invite links",
            parse_mode='HTML'
        )


async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /blacklist command - admin only, ban replied user or by username"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Check if user is an admin
    if user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "<b>⚠️ This command is only available for admins.</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if command is used in a group
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in groups.</b>",
            parse_mode='HTML'
        )
        return
    
    target_user_id = None
    target_display_name = None
    
    # Check if a username was provided as argument (e.g., /blacklist @username)
    if context.args and len(context.args) > 0:
        username = context.args[0].strip()
        # Remove @ prefix if present
        if username.startswith('@'):
            username = username[1:]
        
        # Try to find the user in recent chat administrators or members
        # This is a best-effort approach since Bot API doesn't allow username lookup directly
        try:
            # Try to get chat administrators first
            admins = await context.bot.get_chat_administrators(chat_id=chat.id)
            found = False
            for admin in admins:
                if admin.user.username and admin.user.username.lower() == username.lower():
                    target_user_id = admin.user.id
                    target_display_name = f"@{admin.user.username}"
                    found = True
                    break
            
            if not found:
                await update.message.reply_text(
                    f"<b>❌ Could not find user @{username}.</b>\n\n"
                    "<b>Tip:</b> Reply to their message and use <code>/blacklist</code> instead for guaranteed accuracy.",
                    parse_mode='HTML'
                )
                return
        except Exception as e:
            await update.message.reply_text(
                f"<b>❌ Failed to lookup user @{username}: {str(e)}</b>\n\n"
                "<b>Tip:</b> Reply to their message and use <code>/blacklist</code> instead.",
                parse_mode='HTML'
            )
            return
    # Check if this is a reply to another message
    elif update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_display_name = f"@{target_user.username}" if target_user.username else target_user.first_name
    else:
        await update.message.reply_text(
            "<b>⚠️ Usage:</b>\n"
            "• Reply to a message: <code>/blacklist</code>\n"
            "• By username: <code>/blacklist @username</code>",
            parse_mode='HTML'
        )
        return
    
    # Don't ban other admins
    if target_user_id in ADMIN_IDS:
        await update.message.reply_text(
            "<b>⚠️ Cannot blacklist other admins.</b>",
            parse_mode='HTML'
        )
        return
    
    # Ban the user
    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user_id)
        
        await update.message.reply_text(
            f"<b>✅ User {target_display_name} has been blacklisted and banned from this group.</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(
            f"<b>❌ Failed to ban user: {str(e)}</b>",
            parse_mode='HTML'
        )

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leave command - transfer ownership and leave group"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in groups.</b>",
            parse_mode='HTML'
        )
        return
    
    try:
        await update.message.reply_text(
            "<b>🔄 Transferring group ownership to you and leaving...</b>",
            parse_mode='HTML'
        )
        
        await asyncio.sleep(1)
        
        if user_client and user_client.is_connected:
            chat_id_pyrogram = int(str(chat.id).replace("-100", ""))
            
            # Transfer ownership to the requesting admin
            await user_client.set_chat_owner(chat_id_pyrogram, user.id)
            print(f"✅ Transferred ownership of {chat.id} to admin {user.id}")
            
            await asyncio.sleep(0.5)
            
            # Bot leaves the group
            await context.bot.leave_chat(chat_id=chat.id)
            print(f"✅ Bot left group {chat.id}")
        else:
            # Fallback: just leave if user_client not available
            await context.bot.leave_chat(chat_id=chat.id)
            print(f"✅ Admin {user.id} made bot leave group {chat.id}")
    except Exception as e:
        print(f"❌ Failed to transfer ownership/leave group {chat.id}: {e}")
        try:
            await update.message.reply_text(
                f"<b>❌ Failed to transfer ownership: {str(e)}</b>\n\n"
                "<b>Note:</b> The bot may not have permission to transfer ownership.",
                parse_mode='HTML'
            )
        except:
            pass

async def release_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /release command - only seller in P2P or buyer in OTC can release funds"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Only works in groups
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in escrow groups.</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if deal is already complete
    if chat.id in escrow_roles and escrow_roles[chat.id].get('deal_complete', False):
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if escrow roles are set for this chat
    if chat.id not in escrow_roles:
        await update.message.reply_text(
            "<b>⚠️ No active escrow found in this group.</b>",
            parse_mode='HTML'
        )
        return
    
    # Get buyer and seller info
    buyer_info = escrow_roles[chat.id].get('buyer')
    seller_info = escrow_roles[chat.id].get('seller')
    
    if not buyer_info or not seller_info:
        await update.message.reply_text(
            "<b>⚠️ Buyer and seller must be set first.</b>",
            parse_mode='HTML'
        )
        return
    
    # Determine if OTC or P2P group
    is_otc_group = "OTC" in chat.title if chat.title else False
    
    # Check permissions based on group type
    allowed = False
    if is_otc_group:
        # In OTC, only buyer can release (to seller)
        if user.id == buyer_info['user_id']:
            allowed = True
    else:
        # In P2P, only seller can release (to buyer)
        if user.id == seller_info['user_id']:
            allowed = True
    
    # If not allowed, show error
    if not allowed:
        await update.message.reply_text(
            "<b>Sorry! you are not allowed to use this command!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if amount was provided
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>Please enter the amount you wish to release.</b>\n\n"
            "Ex: <code>/release 200</code>, <code>/release all</code>",
            parse_mode='HTML'
        )
        return
    
    # Get amount
    amount = context.args[0]
    
    # Get token and network info
    token_info = escrow_roles[chat.id].get('token', 'USDT')
    # Handle both dict and string formats for token_info
    if isinstance(token_info, dict):
        token_name = token_info.get('name', 'USDT')
        network_name = token_info.get('network', 'BSC')
    else:
        token_name = token_info
        network_name = escrow_roles[chat.id].get('network', 'BSC')
    
    # Get buyer username
    buyer_username = buyer_info.get('username', 'Unknown')
    buyer_address = buyer_info.get('address', 'N/A')
    
    # Get escrow balance for "all" calculation
    escrow_address = escrow_roles[chat.id].get('escrow_address', '')
    monitored_balance = 0
    manual_balance = 0
    
    if escrow_address and escrow_address.lower() in monitored_addresses:
        monitored_balance = monitored_addresses[escrow_address.lower()].get('total_balance', 0)
    
    if chat.id in escrow_roles:
        manual_balance = escrow_roles[chat.id].get('balance', 0)
    
    current_escrow_balance = monitored_balance + manual_balance
    
    # Calculate fees (1% escrow fee)
    try:
        if amount.lower() == 'all':
            release_amount = current_escrow_balance
            amount_for_calc = current_escrow_balance
        else:
            release_amount = amount
            amount_for_calc = float(amount)
    except:
        release_amount = amount
        amount_for_calc = 0
    
    # Format amounts with $ symbol and proper decimals
    if isinstance(amount_for_calc, (int, float)) and amount_for_calc > 0:
        network_fee = 0.10  # Fixed network fee
        escrow_fee = amount_for_calc * 0.01  # 1% escrow fee
        ambassador_discount = 0.0  # Always 0
        ticket_discount = 0.0
        formatted_amount = f"{amount_for_calc:.5f}"
        formatted_network_fee = "0.10"
        formatted_escrow_fee = f"{escrow_fee:.5f}"
        formatted_ambassador = "0.00"
        formatted_ticket = f"{ticket_discount:.5f}"
    else:
        formatted_amount = f"{release_amount}"
        formatted_network_fee = "0.10"
        formatted_escrow_fee = "0.15000"
        formatted_ambassador = "0.00"
        formatted_ticket = "0.00000"
    
    # Create confirmation message
    # Strip @ from buyer_username if it exists
    buyer_name_clean = buyer_username.lstrip('@') if buyer_username.startswith('@') else buyer_username
    confirmation_message = f"""‼️<b>Release Confirmation</b>‼️

🔒 <b>Paying To: Buyer[<u>@{buyer_name_clean}</u>]</b>
💰 <b>Amount:</b> {formatted_amount} ({formatted_amount}$)
🌐 <b>Network Fee:</b> {formatted_network_fee} ({formatted_network_fee}$)
💷 <b>Escrow Fee:</b> {formatted_escrow_fee} ({formatted_escrow_fee}$)
🤝 <b>Ambassador Discounts:</b> {formatted_ambassador} ({formatted_ambassador}$)
🎫 <b>Ticket Discount:</b> {formatted_ticket} ({formatted_ticket}$)

📬 <b>Address:</b> <code>{buyer_address}</code>
🪙 <b>Token:</b> {token_name}
🌐 <b>Network:</b> {network_name}

<u><b>(Network fee will be deducted from amount)</b></u>
<u><b>(Escrow fee will be deducted from total balance)</b></u>

<b>Are you ready to proceed with this withdrawal?</b>
<b>Both the parties kindly confirm the same and note the action is irreversible.</b>

<b>For help: Hit /dispute to call an Administrator.</b>


"""
    
    # Create confirmation buttons - stacked vertically
    keyboard = [
        [InlineKeyboardButton("Buyer Confirmation ❌", callback_data=f"release_buyer_confirm_{chat.id}_{amount}")],
        [InlineKeyboardButton("Seller Confirmation ❌", callback_data=f"release_seller_confirm_{chat.id}_{amount}")],
        [InlineKeyboardButton("Reject ❌", callback_data=f"release_reject_{chat.id}_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send confirmation message
    msg = await update.message.reply_text(
        confirmation_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Get seller username
    seller_username = seller_info.get('username', 'Unknown')
    
    # Store release confirmation state
    release_pending[msg.message_id] = {
        'chat_id': chat.id,
        'amount': amount,
        'buyer_id': buyer_info['user_id'],
        'seller_id': seller_info['user_id'],
        'buyer_confirmed': False,
        'seller_confirmed': False,
        'token': token_name,
        'network': network_name,
        'buyer_username': buyer_username,
        'seller_username': seller_username,
        'buyer_address': buyer_address,
        'buyer_has_bio': buyer_info.get('has_bot_in_bio', False),
        'seller_has_bio': seller_info.get('has_bot_in_bio', False),
        'original_message': confirmation_message
    }

async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /refund command - refund funds to seller (mirrors release but to seller)"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Only works in groups
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in escrow groups.</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if deal is already complete
    if chat.id in escrow_roles and escrow_roles[chat.id].get('deal_complete', False):
        await update.message.reply_text(
            "<b>Sorry! please first use /dd first!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if escrow roles are set for this chat
    if chat.id not in escrow_roles:
        await update.message.reply_text(
            "<b>⚠️ No active escrow found in this group.</b>",
            parse_mode='HTML'
        )
        return
    
    # Get buyer and seller info
    buyer_info = escrow_roles[chat.id].get('buyer')
    seller_info = escrow_roles[chat.id].get('seller')
    
    if not buyer_info or not seller_info:
        await update.message.reply_text(
            "<b>⚠️ Buyer and seller must be set first.</b>",
            parse_mode='HTML'
        )
        return
    
    # Determine if OTC or P2P group
    is_otc_group = "OTC" in chat.title if chat.title else False
    
    # Check permissions based on group type
    allowed = False
    if is_otc_group:
        # In OTC, only seller can refund (to buyer)
        if user.id == seller_info['user_id']:
            allowed = True
    else:
        # In P2P, only buyer can refund (to seller)
        if user.id == buyer_info['user_id']:
            allowed = True
    
    # If not allowed, show error
    if not allowed:
        await update.message.reply_text(
            "<b>Sorry! you are not allowed to use this command!</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if amount was provided
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>Please enter the amount you wish to refund.</b>\n\n"
            "Ex: <code>/refund 200</code>, <code>/refund all</code>",
            parse_mode='HTML'
        )
        return
    
    # Get amount
    amount = context.args[0]
    
    # Get token and network info
    token_info = escrow_roles[chat.id].get('token', 'USDT')
    if isinstance(token_info, dict):
        token_name = token_info.get('name', 'USDT')
        network_name = token_info.get('network', 'BSC')
    else:
        token_name = token_info
        network_name = escrow_roles[chat.id].get('network', 'BSC')
    
    # Get seller username and address (paying to seller)
    seller_username = seller_info.get('username', 'Unknown')
    seller_address = seller_info.get('address', 'N/A')
    buyer_username = buyer_info.get('username', 'Unknown')
    
    # Get escrow balance
    escrow_address = escrow_roles[chat.id].get('escrow_address', '')
    monitored_balance = 0
    manual_balance = 0
    
    if escrow_address and escrow_address.lower() in monitored_addresses:
        monitored_balance = monitored_addresses[escrow_address.lower()].get('total_balance', 0)
    
    if chat.id in escrow_roles:
        manual_balance = escrow_roles[chat.id].get('balance', 0)
    
    current_escrow_balance = monitored_balance + manual_balance
    
    # Calculate amounts
    try:
        if amount.lower() == 'all':
            refund_amount = current_escrow_balance
            amount_for_calc = current_escrow_balance
        else:
            refund_amount = amount
            amount_for_calc = float(amount)
    except:
        refund_amount = amount
        amount_for_calc = 0
    
    # Format amounts
    if isinstance(amount_for_calc, (int, float)) and amount_for_calc > 0:
        network_fee = 0.10
        escrow_fee = amount_for_calc * 0.01
        ambassador_discount = 0.0
        ticket_discount = 0.0
        formatted_amount = f"{amount_for_calc:.5f}"
        formatted_network_fee = "0.10"
        formatted_escrow_fee = f"{escrow_fee:.5f}"
        formatted_ambassador = "0.00"
        formatted_ticket = f"{ticket_discount:.5f}"
    else:
        formatted_amount = f"{refund_amount}"
        formatted_network_fee = "0.10"
        formatted_escrow_fee = "0.15000"
        formatted_ambassador = "0.00"
        formatted_ticket = "0.00000"
    
    # Create refund confirmation message (paying to seller)
    seller_name_clean = seller_username.lstrip('@') if seller_username.startswith('@') else seller_username
    refund_message = f"""‼️<b>Refund Confirmation</b>‼️

🔒 <b>Paying To: Seller[<u>@{seller_name_clean}</u>]</b>
💰 <b>Amount:</b> {formatted_amount} ({formatted_amount}$)
🌐 <b>Network Fee:</b> {formatted_network_fee} ({formatted_network_fee}$)
💷 <b>Escrow Fee:</b> {formatted_escrow_fee} ({formatted_escrow_fee}$)
🤝 <b>Ambassador Discounts:</b> {formatted_ambassador} ({formatted_ambassador}$)
🎫 <b>Ticket Discount:</b> {formatted_ticket} ({formatted_ticket}$)

📬 <b>Address:</b> <code>{seller_address}</code>
🪙 <b>Token:</b> {token_name}
🌐 <b>Network:</b> {network_name}

<u><b>(Network fee will be deducted from amount)</b></u>
<u><b>(Escrow fee will be deducted from total balance)</b></u>

<b>Are you ready to proceed with this refund?</b>
<b>Both the parties kindly confirm the same and note the action is irreversible.</b>

<b>For help: Hit /dispute to call an Administrator.</b>


"""
    
    # Create confirmation buttons
    keyboard = [
        [InlineKeyboardButton("Buyer Confirmation ❌", callback_data=f"refund_buyer_confirm_{chat.id}_{amount}")],
        [InlineKeyboardButton("Seller Confirmation ❌", callback_data=f"refund_seller_confirm_{chat.id}_{amount}")],
        [InlineKeyboardButton("Reject ❌", callback_data=f"refund_reject_{chat.id}_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send confirmation message
    msg = await update.message.reply_text(
        refund_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Store refund confirmation state
    refund_pending[msg.message_id] = {
        'chat_id': chat.id,
        'amount': amount,
        'buyer_id': buyer_info['user_id'],
        'seller_id': seller_info['user_id'],
        'buyer_confirmed': False,
        'seller_confirmed': False,
        'token': token_name,
        'network': network_name,
        'buyer_username': buyer_username,
        'seller_username': seller_username,
        'seller_address': seller_address,
        'buyer_has_bio': buyer_info.get('has_bot_in_bio', False),
        'seller_has_bio': seller_info.get('has_bot_in_bio', False),
        'original_message': refund_message
    }

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify command to check if an address belongs to the bot"""
    # Check if address was provided
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "<b>Please use the proper format.\n\nEx:</b> /verify [address or gclink]",
            parse_mode='HTML'
        )
        return
    
    # Get the address from command arguments
    provided_address = context.args[0].strip()
    
    # All bot deposit addresses (in lowercase for case-insensitive comparison)
    bot_addresses = {
        # USDT BSC
        "0xda4c2a5b876b0c7521e1c752690d8705080000fe",
        "0xf282e789e835ed379aea84ece204d2d643e6774f",
        # USDT TRON
        "tvstywseydrxukk2ehcectt4uu3b2tqrvm",
        "txfytrl3vau3dje6kyxqueazoscn8drrhb",
        # BTC
        "bc1qya2u04hfdy5j9mnzds7effh0xqx3mvwcyflnak",
        "bc1q43nwc38ashvvzhakw7ma7227yzd3yfkmpudl48",
        # LTC
        "ltc1qya2u04hfdy5j9mnzds7effh0xqx3mvwcq49h9x",
        "ltc1qfu7asf36pmg5kc4wge5dcz6t5yd3pyn3d86w66",
        # Fake deposit addresses (for testing)
        "thb2do8gmweboctgaduh73q6ewxfcx9vx4"  # TRC20 test address
    }
    
    # Check if the provided address matches any bot address (case-insensitive)
    if provided_address.lower() in bot_addresses:
        await update.message.reply_text(
            "<b>The provided adress is valid and belongs to bot.</b>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "<b>The provided adress is invalid and doesn't belongs to bot.</b>",
            parse_mode='HTML'
        )

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track when members join and auto-promote admins"""
    print(f"✅ track_chat_members CALLED!")
    try:
        result = update.chat_member
        
        print(f"🔍 Chat member update detected")
        print(f"   Old status: {result.old_chat_member.status}, New status: {result.new_chat_member.status}")
        
        # Check if this is a new member joining (status changed from non-member to member)
        was_member = result.old_chat_member.status in ['member', 'administrator', 'creator']
        is_member = result.new_chat_member.status in ['member', 'administrator', 'creator']
        
        print(f"   Was member: {was_member}, Is member: {is_member}")
        
        # Only process if someone just joined
        if not was_member and is_member:
            user_id = result.new_chat_member.user.id
            chat_id = result.chat.id
            user_name = result.new_chat_member.user.first_name or "Admin"
            
            print(f"   New member joined: {user_id} ({user_name}) in chat {chat_id}")
            print(f"   Admin IDs: {ADMIN_IDS}")
            print(f"   Is admin: {user_id in ADMIN_IDS}")
            
            # Check if the user is in the admin list (including special user 5229586098)
            if user_id in ADMIN_IDS:
                try:
                    print(f"   👤 User {user_id} is in admin list - proceeding with promotion")
                    
                    # FIRST: Check bot's status in the group
                    chat = await context.bot.get_chat(chat_id)
                    bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                    print(f"   🔍 Checking bot status in chat {chat_id}...")
                    print(f"   📊 Bot status: {bot_member.status}")
                    print(f"   ✅ Bot can promote members: {getattr(bot_member, 'can_promote_members', False)}")
                    
                    # If bot is not admin, promote it first
                    if bot_member.status != 'administrator':
                        print(f"   ⚠️ Bot is not admin yet, promoting bot first...")
                        await context.bot.promote_chat_member(
                            chat_id=chat_id,
                            user_id=context.bot.id,
                            can_promote_members=True,
                            can_manage_chat=True,
                            can_delete_messages=True
                        )
                        print(f"   ✅ Bot promoted to admin in chat {chat_id}")
                    
                    # THEN: Promote the admin user with full permissions
                    print(f"   🚀 Promoting user {user_id} ({user_name}) to admin...")
                    await context.bot.promote_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        can_manage_chat=True,
                        can_delete_messages=True,
                        can_manage_video_chats=True,
                        can_restrict_members=True,
                        can_promote_members=True,
                        can_change_info=True,
                        can_invite_users=True,
                        can_pin_messages=True,
                        can_post_messages=True
                    )
                    print(f"✅✅ AUTO-PROMOTED: User {user_id} ({user_name}) is now admin in chat {chat_id}")
                    
                    # Send a notification to the group that admin has joined
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"<b>👮 Admin {user_name} has joined with full admin privileges to help resolve the dispute.</b>",
                            parse_mode='HTML'
                        )
                    except Exception as notify_err:
                        print(f"   Failed to send notification: {notify_err}")
                except Exception as e:
                    print(f"❌ Failed to promote admin {user_id}: {type(e).__name__}: {str(e)}")
                    import traceback
                    traceback.print_exc()
    except Exception as outer_e:
        print(f"❌ Error in track_chat_members: {type(outer_e).__name__}: {str(outer_e)}")
        import traceback
        traceback.print_exc()

async def auto_promote_admin_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-promote admin if they send a message in an escrow group"""
    try:
        if not update.message or update.message.chat.type not in ['group', 'supergroup']:
            return
        
        user = update.effective_user
        chat = update.effective_chat
        
        # Only process if user is in admin list
        if user.id not in ADMIN_IDS:
            return
        
        # Check if they're already an admin
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            if member.status in ['administrator', 'creator']:
                return  # Already admin
        except:
            pass
        
        # They're an admin but not yet promoted - promote them
        print(f"🔍 Auto-promoting admin {user.id} ({user.first_name}) on first message in {chat.id}")
        try:
            await context.bot.promote_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_post_messages=True
            )
            print(f"✅ Auto-promoted admin {user.id} on message in {chat.id}")
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>👮 Admin {user.first_name} has been promoted to admin with full privileges to help resolve the dispute.</b>",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Failed to promote admin on message: {e}")
    except Exception as e:
        print(f"Error in auto_promote_admin_on_message: {e}")

async def clearmessages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clearmessages command - admin only, delete last N messages"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    
    print(f"🔍 /clearmessages command: User {user.id} in chat {chat.id}")
    
    # Check if user is an admin
    if user.id not in ADMIN_IDS:
        print(f"   ❌ User {user.id} is not an admin")
        await update.message.reply_text(
            "<b>⚠️ This command is only available for admins.</b>",
            parse_mode='HTML'
        )
        return
    
    print(f"   ✅ User {user.id} is an admin")
    
    # Check if command is in a group
    if chat.type not in ['group', 'supergroup']:
        print(f"   ❌ Not a group: {chat.type}")
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in groups.</b>",
            parse_mode='HTML'
        )
        return
    
    # Get the number argument
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "<b>⚠️ Usage: /clearmessages [number]\nExample: /clearmessages 10</b>",
            parse_mode='HTML'
        )
        return
    
    try:
        num_to_delete = int(context.args[0])
        if num_to_delete <= 0 or num_to_delete > 100:
            await update.message.reply_text(
                "<b>⚠️ Please specify a number between 1 and 100.</b>",
                parse_mode='HTML'
            )
            return
    except ValueError:
        await update.message.reply_text(
            "<b>⚠️ Please provide a valid number.\nExample: /clearmessages 10</b>",
            parse_mode='HTML'
        )
        return
    
    print(f"   Deleting {num_to_delete} messages from chat {chat.id}")
    
    deleted_count = 0
    failed_count = 0
    current_msg_id = message.message_id
    
    try:
        # Delete the last N messages (going backwards from current message)
        for i in range(num_to_delete):
            msg_id_to_delete = current_msg_id - i - 1
            try:
                print(f"   Attempting to delete message {msg_id_to_delete}")
                await context.bot.delete_message(chat_id=chat.id, message_id=msg_id_to_delete)
                deleted_count += 1
                print(f"   ✅ Deleted message {msg_id_to_delete}")
            except Exception as delete_err:
                failed_count += 1
                print(f"   ❌ Failed to delete message {msg_id_to_delete}: {type(delete_err).__name__}")
        
        print(f"   Total deleted: {deleted_count}, Failed: {failed_count}")
        
        # Send confirmation
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"<b>🗑️ Deleted {deleted_count} messages</b>",
            parse_mode='HTML'
        )
        
        print(f"✅ Admin {user.id} deleted {deleted_count} messages in chat {chat.id}")
        
    except Exception as e:
        print(f"❌ Error clearing messages: {type(e).__name__}: {str(e)}")
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>❌ Error clearing messages: {str(e)}</b>",
                parse_mode='HTML'
            )
        except Exception as send_err:
            print(f"   Failed to send error message: {send_err}")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .purge command - admin only, with Pyrogram fallback"""
    print(f"✅✅✅ PURGE COMMAND CALLED ✅✅✅")
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    
    print(f"🔍 .purge command: User {user.id} in chat {chat.id}")
    
    # Check if user is an admin
    if user.id not in ADMIN_IDS:
        print(f"   ❌ User {user.id} is not an admin")
        await update.message.reply_text(
            "<b>⚠️ This command is only available for admins.</b>",
            parse_mode='HTML'
        )
        return
    
    print(f"   ✅ User {user.id} is an admin")
    
    # Check if command is in a group
    if chat.type not in ['group', 'supergroup']:
        print(f"   ❌ Not a group: {chat.type}")
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in groups.</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if message is a reply
    if not message.reply_to_message:
        print(f"   ❌ Not a reply")
        await update.message.reply_text(
            "<b>⚠️ Please reply to a message and use .purge to delete all messages from that point onwards.</b>",
            parse_mode='HTML'
        )
        return
    
    # Get message IDs
    target_message_id = message.reply_to_message.message_id
    current_message_id = message.message_id
    
    print(f"   Target ID: {target_message_id}, Current ID: {current_message_id}")
    
    deleted_count = 0
    failed_count = 0
    
    try:
        # Try deleting with Bot API first
        for msg_id in range(target_message_id, current_message_id + 1):
            try:
                print(f"   Attempting to delete message {msg_id} with Bot API")
                await context.bot.delete_message(chat_id=chat.id, message_id=msg_id)
                deleted_count += 1
                print(f"   ✅ Deleted message {msg_id}")
            except Exception as delete_err:
                print(f"   ❌ Bot API failed for {msg_id}: {type(delete_err).__name__}: {str(delete_err)}")
                failed_count += 1
        
        # If Bot API failed and Pyrogram available, try Pyrogram fallback
        if failed_count > 0 and user_client:
            print(f"   📌 Attempting Pyrogram fallback for {failed_count} failed messages...")
            try:
                if not user_client.is_connected:
                    await user_client.start()
                
                message_ids_to_delete = []
                for msg_id in range(target_message_id, current_message_id + 1):
                    if msg_id not in range(target_message_id, target_message_id + deleted_count):
                        message_ids_to_delete.append(msg_id)
                
                if message_ids_to_delete:
                    await user_client.delete_messages(chat.id, message_ids=message_ids_to_delete)
                    deleted_count += len(message_ids_to_delete)
                    print(f"   ✅ Pyrogram deleted {len(message_ids_to_delete)} messages")
            except Exception as pyro_err:
                print(f"   ⚠️ Pyrogram fallback failed: {pyro_err}")
        
        print(f"   Total deleted: {deleted_count}, Failed: {failed_count}")
        
        # Send confirmation
        if deleted_count > 0:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>🗑️ Purged {deleted_count} messages</b>",
                parse_mode='HTML'
            )
            print(f"✅ Admin {user.id} purged {deleted_count} messages in chat {chat.id}")
        else:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>❌ Could not delete any messages. Bot may lack admin permissions.</b>",
                parse_mode='HTML'
            )
        
    except Exception as e:
        print(f"❌ Error purging messages: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>❌ Error purging messages: {str(e)}</b>",
                parse_mode='HTML'
            )
        except Exception as send_err:
            print(f"   Failed to send error message: {send_err}")

async def clearall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clearall command - admin only, Pyrogram joins and clears all messages"""
    user = update.effective_user
    chat = update.effective_chat
    
    print(f"🔍 /clearall command: User {user.id} in chat {chat.id}")
    
    # Check if user is an admin
    if user.id not in ADMIN_IDS:
        print(f"   ❌ User {user.id} is not an admin")
        await update.message.reply_text(
            "<b>⚠️ This command is only available for admins.</b>",
            parse_mode='HTML'
        )
        return
    
    print(f"   ✅ User {user.id} is an admin")
    
    # Check if command is in a group
    if chat.type not in ['group', 'supergroup']:
        print(f"   ❌ Not a group: {chat.type}")
        await update.message.reply_text(
            "<b>⚠️ This command can only be used in groups.</b>",
            parse_mode='HTML'
        )
        return
    
    # Check if Pyrogram is available
    if not user_client:
        print(f"   ❌ Pyrogram not configured")
        await update.message.reply_text(
            "<b>⚠️ Pyrogram is not configured. Cannot clear all messages.</b>",
            parse_mode='HTML'
        )
        return
    
    try:
        await update.message.reply_text(
            "<b>⏳ Clearing all messages... Please wait...</b>",
            parse_mode='HTML'
        )
        
        # Start Pyrogram client if not connected
        if not user_client.is_connected:
            print(f"   Connecting Pyrogram client...")
            await user_client.start()
        
        print(f"   Joining group {chat.id} with Pyrogram...")
        
        # Join the group with Pyrogram (convert to supergroupformat)
        target_chat_id = chat.id
        
        # Get all messages and collect IDs to delete
        deleted_count = 0
        failed_count = 0
        batch_size = 100
        
        print(f"   Fetching messages from chat {target_chat_id}...")
        
        # Collect all message IDs first
        message_ids = []
        try:
            async for message in user_client.get_chat_history(target_chat_id, limit=None):
                message_ids.append(message.id)
                if len(message_ids) >= 1000:  # Limit to 1000 messages for safety
                    break
        except Exception as fetch_err:
            print(f"   ⚠️ Warning fetching messages: {fetch_err}")
            # If we can't fetch with Pyrogram, try with bot API instead
            print(f"   Falling back to Bot API deletion...")
            
            # Use Bot API - get current message ID and work backwards
            current_msg = update.message.message_id
            for msg_id in range(max(1, current_msg - 500), current_msg):
                try:
                    await context.bot.delete_message(chat_id=chat.id, message_id=msg_id)
                    deleted_count += 1
                except:
                    failed_count += 1
            
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>🗑️ Cleared ~{deleted_count} messages (using Bot API fallback)</b>",
                parse_mode='HTML'
            )
            print(f"✅ Admin {user.id} cleared ~{deleted_count} messages in chat {chat.id} using Bot API fallback")
            return
        
        # Delete messages in batches using Pyrogram
        print(f"   Deleting {len(message_ids)} messages...")
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i+batch_size]
            try:
                # Delete batch of messages
                await user_client.delete_messages(target_chat_id, message_ids=batch)
                deleted_count += len(batch)
                print(f"   ✅ Deleted batch of {len(batch)} messages")
            except FloodWait as fw:
                print(f"   ⏳ FloodWait: {fw.value}s, pausing...")
                await asyncio.sleep(fw.value)
                try:
                    await user_client.delete_messages(target_chat_id, message_ids=batch)
                    deleted_count += len(batch)
                    print(f"   ✅ Deleted batch of {len(batch)} messages after retry")
                except Exception as retry_err:
                    failed_count += len(batch)
                    print(f"   ❌ Failed to delete batch after retry: {retry_err}")
            except Exception as delete_err:
                failed_count += len(batch)
                print(f"   ❌ Failed to delete batch: {delete_err}")
        
        print(f"   Total deleted: {deleted_count}, Failed: {failed_count}")
        
        # Send confirmation
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"<b>🗑️ Cleared all {deleted_count} messages</b>",
            parse_mode='HTML'
        )
        
        print(f"✅ Admin {user.id} cleared all {deleted_count} messages in chat {chat.id}")
        
    except Exception as e:
        print(f"❌ Error clearing all messages: {type(e).__name__}: {str(e)}")
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"<b>❌ Error clearing messages: {str(e)}</b>",
                parse_mode='HTML'
            )
        except Exception as send_err:
            print(f"   Failed to send error message: {send_err}")

async def forward_media_to_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward photos and links from buyer/seller to logs channel"""
    try:
        if not LOGS_CHANNEL_ID or not update.message:
            return
        
        msg = update.message
        if not msg.photo:
            return
        
        user = update.effective_user
        chat = update.effective_chat
        
        if chat.type not in ['group', 'supergroup'] or chat.id not in escrow_roles:
            return
        
        buyer_info = escrow_roles[chat.id].get('buyer')
        seller_info = escrow_roles[chat.id].get('seller')
        if not buyer_info or not seller_info:
            return
        
        buyer_id = buyer_info.get('user_id')
        seller_id = seller_info.get('user_id')
        is_buyer = user.id == buyer_id
        is_seller = user.id == seller_id
        
        if not (is_buyer or is_seller):
            return
        
        sender_name = f"{'🛍️ Buyer' if is_buyer else '🏪 Seller'}"
        sender_username = user.username if user.username else user.first_name
        
        await context.bot.forward_message(chat_id=LOGS_CHANNEL_ID, from_chat_id=chat.id, message_id=msg.message_id)
        
        info = f"""📸 <b>Media/Link Forwarded</b>

{sender_name}: @{sender_username}
🆔 User ID: <code>{user.id}</code>
👥 Group: {chat.title}
🆔 Chat ID: <code>{chat.id}</code>
⏰ Time: {datetime.now().strftime('%d/%m/%y %H:%M:%S')}"""
        
        await context.bot.send_message(chat_id=LOGS_CHANNEL_ID, text=info, parse_mode='HTML')
    except:
        pass

def main():
    if not BOT_TOKEN:
        print("❌ Error: ESCROW_BOT_TOKEN environment variable not set!")
        print("Please set your Telegram bot token in Secrets.")
        return
    
    if not API_ID or not API_HASH or not PHONE:
        print("⚠️  Warning: Telegram user account credentials not configured!")
        print("   Group creation will not work without:")
        print("   - TELEGRAM_API_ID")
        print("   - TELEGRAM_API_HASH")
        print("   - TELEGRAM_PHONE")
        print("   Get credentials from https://my.telegram.org/apps")
        print("")
    
    # Build app with optimized settings for faster response
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)  # Handle multiple updates concurrently
        .pool_timeout(30.0)  # Faster timeout for connections
        .connection_pool_size(8)  # More concurrent connections
        .build()
    )
    
    # Error handler to catch any exceptions
    async def error_handler(update, context):
        print(f"❌ Error: {context.error}")
        import traceback
        traceback.print_exc()
    
    app.add_error_handler(error_handler)
    
    # Commands registration FIRST (highest priority)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("escrow", escrow_command))
    app.add_handler(CommandHandler("dispute", dispute_command))
    app.add_handler(CommandHandler("dd", dd_command))
    app.add_handler(CommandHandler("buyer", buyer_command))
    app.add_handler(CommandHandler("seller", seller_command))
    app.add_handler(CommandHandler("token", token_command))
    app.add_handler(CommandHandler("deposit", deposit_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("addbalance", addbalance_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("fakedepo", fakedepo_command))
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("revoke", revoke_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))
    app.add_handler(CommandHandler("verify", verify_command))
    app.add_handler(CommandHandler("release", release_command))
    app.add_handler(CommandHandler("refund", refund_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("clearmessages", clearmessages_command))
    app.add_handler(CommandHandler("clearall", clearall_command))
    
    # SIMPLE TEST: Print every message received (but skip commands)
    async def simple_message_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not update.message:
                print(f"🔴 MESSAGE: No message object")
                return
            
            text = update.message.text or ""
            print(f"🔴 MESSAGE RECEIVED: {text[:100] if text else '(empty)'}")
            
            if text.lower().startswith(".purge"):
                print("🔴 PURGE DETECTED!")
                await purge_command(update, context)
        except Exception as e:
            print(f"🔴 Error in message logger: {type(e).__name__}: {e}")
    
    # Register message handler with TEXT filter AFTER commands (group 1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, simple_message_logger), group=1)
    
    # Register ChatMemberHandler (group 2)
    app.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.ANY_CHAT_MEMBER), group=2)
    
    # Register message handler for photos (group 3)
    app.add_handler(MessageHandler(filters.PHOTO, forward_media_to_logs), group=3)
    
    # Text handler for groups (auto-promote) - group 4
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, auto_promote_admin_on_message), group=4)
    
    
    # Register callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Start deposit monitoring in background with proper cleanup
    async def post_init(application):
        # Store the task in the application so we can cancel it later
        application.monitor_task = asyncio.create_task(monitor_deposits(application))
        print("✅ Deposit monitoring task started")
    
    async def post_stop(application):
        # Properly cancel the monitoring task on shutdown
        if hasattr(application, 'monitor_task') and application.monitor_task:
            application.monitor_task.cancel()
            try:
                await application.monitor_task
            except asyncio.CancelledError:
                print("✅ Deposit monitoring task cancelled gracefully")
    
    app.post_init = post_init
    app.post_stop = post_stop
    
    print("✅ @PagaLEscrowBot is running...")
    print(f"✅ Registered admin IDs: {ADMIN_IDS}")
    print(f"✅ /purge command handler registered!")
    if BSCSCAN_API_KEY and TRONGRID_API_KEY:
        print("✅ Blockchain monitoring enabled (BSC & TRON)")
    else:
        print("⚠️  Blockchain monitoring disabled (API keys not configured)")
    
    if LOGS_CHANNEL_ID:
        print(f"✅ Logs channel configured: {LOGS_CHANNEL_ID}")
    else:
        print("⚠️  Logs channel not configured (LOGS_CHANNEL_ID not set)")
    
    try:
        # Run polling with faster updates
        print("🔄 Starting bot polling...")
        print("📡 Listening for updates from Telegram...")
        print("✅ Global update logger installed with highest priority")
        app.run_polling(
            poll_interval=0.5,  # Check for updates every 0.5 seconds
            timeout=10,  # Faster timeout
            drop_pending_updates=False,
            allowed_updates=None  # Accept all update types
        )
    finally:
        # Stop user client if it's running
        if user_client and user_client.is_connected:
            asyncio.run(user_client.stop())

if __name__ == "__main__":
    main()
