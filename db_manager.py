import aiosqlite

DB_NAME = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # جدول المستخدمين (لحفظ الآدمنية، الأرصدة، الصلاحيات)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                role TEXT DEFAULT 'user', -- الأدوار: owner, admin, user
                balance INTEGER DEFAULT 0
            )
        ''')
        
        # جدول الحسابات (لحفظ أرقام وجلسات حسابات تيليجرام التي يتم إضافتها)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                phone TEXT PRIMARY KEY,
                session_string TEXT NOT NULL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # جدول الإعدادات (لحفظ الكليشة، معرف المالك، وأي إعدادات عامة)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.commit()
