import json
import asyncio
import aiosqlite
import os

# أسماء الملفات (تأكد أنها مطابقة لأسماء ملفاتك)
DATA_FILE = "bot_data.json"
DB_FILE = "bot_database.db"

async def migrate():
    print("⏳ جاري بدء عملية نقل البيانات...")
    
    if not os.path.exists(DATA_FILE):
        print(f"❌ لم يتم العثور على ملف {DATA_FILE}. يرجى التأكد من وجوده في نفس المجلد.")
        return
        
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    async with aiosqlite.connect(DB_FILE) as db:
        
        # 1. نقل المستخدمين المصرح لهم (الاشتراكات)
        auth_users = data.get("authorized_users", {})
        print(f"🔄 جاري نقل {len(auth_users)} مستخدم مشترك...")
        for uid_str, exp in auth_users.items():
            uid = int(uid_str)
            # -1 تعني اشتراك دائمي في قاعدتنا الجديدة
            expire_val = -1 if exp is None else exp 
            
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, auth_expire) 
                VALUES (?, ?)
            """, (uid, expire_val))
            await db.execute("UPDATE users SET auth_expire = ? WHERE user_id = ?", (expire_val, uid))

        # 2. نقل المشتركين في الفترة التجريبية
        trial_users = data.get("trial_users", [])
        print(f"🔄 جاري نقل {len(trial_users)} مستخدم تجريبي...")
        for uid in trial_users:
            await db.execute("INSERT OR IGNORE INTO users (user_id, has_trial) VALUES (?, TRUE)", (int(uid),))
            await db.execute("UPDATE users SET has_trial = TRUE WHERE user_id = ?", (int(uid),))

        # 3. نقل حسابات الخمط (المساعدة)
        accounts = data.get("accounts", {})
        total_accs = sum(len(v) for v in accounts.values()) if isinstance(accounts, dict) else 0
        print(f"🔄 جاري نقل {total_accs} حساب مساعد (للخمط)...")
        if isinstance(accounts, dict):
            for owner_id_str, acc_list in accounts.items():
                owner_id = int(owner_id_str)
                for acc in acc_list:
                    await db.execute("""
                        INSERT INTO accounts (owner_id, phone, session_name, account_id, name, account_type)
                        VALUES (?, ?, ?, ?, ?, 'scrape')
                    """, (owner_id, acc.get("phone"), acc.get("session"), acc.get("id"), acc.get("name")))

        # 4. نقل حسابات الشد (الريبورت)
        report_accounts = data.get("report_accounts", {})
        total_rep = sum(len(v) for v in report_accounts.values()) if isinstance(report_accounts, dict) else 0
        print(f"🔄 جاري نقل {total_rep} حساب شد (ريبورت)...")
        if isinstance(report_accounts, dict):
            for owner_id_str, acc_list in report_accounts.items():
                owner_id = int(owner_id_str)
                for acc in acc_list:
                    await db.execute("""
                        INSERT INTO accounts (owner_id, phone, session_name, account_id, name, account_type)
                        VALUES (?, ?, ?, ?, ?, 'report')
                    """, (owner_id, acc.get("phone"), acc.get("session"), acc.get("id"), acc.get("name")))

        # 5. نقل الإعدادات العامة للبوت
        print("🔄 جاري نقل الإعدادات والكليشات...")
        settings_to_migrate = [
            ("global_free_mode", data.get("global_free_mode", False), False),
            ("kalisha_text", data.get("kalisha_text", ""), False),
            ("kalisha_media", data.get("kalisha_media", ""), False),
            ("mutate_kalisha", data.get("mutate_kalisha", False), False),
            ("report_target", data.get("report_target", ""), False),
            ("report_text", data.get("report_text", ""), False),
            ("report_type", data.get("report_type", "spam"), False),
            ("is_reporting", data.get("is_reporting", False), False),
            ("report_count", data.get("report_count", 0), False),
            ("blacklisted_groups", data.get("blacklisted_groups", []), True),  # مصفوفة
            ("report_messages", data.get("report_messages", []), True)         # مصفوفة
        ]
        
        for key, val, is_json in settings_to_migrate:
            if val is None:
                str_val = ""
            elif is_json:
                str_val = json.dumps(val, ensure_ascii=False)
            elif isinstance(val, bool):
                str_val = "1" if val else "0"
            else:
                str_val = str(val)
                
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str_val))

        await db.commit()
        print("\n✅ تم نقل جميع البيانات بنجاح إلى قاعدة البيانات (bot_database.db)!")
        print("يمكنك الآن حذف ملف bot_data.json أو الاحتفاظ به كنسخة احتياطية.")

if __name__ == "__main__":
    asyncio.run(migrate())
