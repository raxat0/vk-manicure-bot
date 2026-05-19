# database.py
import aiosqlite
import logging
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                services TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                vk_id INTEGER DEFAULT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY,
                master_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                available INTEGER DEFAULT 1,
                FOREIGN KEY(master_id) REFERENCES masters(id),
                UNIQUE(master_id, date, time)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                master_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                service TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Начальные мастера
        masters_data = [
            ("Анна", "Маникюр,Педикюр"),
            ("Мария", "Маникюр,Педикюр"),
            ("Ольга", "Визажист"),
            ("Екатерина", "Парикмахер"),
        ]
        for name, services in masters_data:
            await db.execute(
                "INSERT OR IGNORE INTO masters (name, services) VALUES (?, ?)",
                (name, services)
            )
        await db.commit()

        # Миграции
        migrations = [
            "ALTER TABLE masters ADD COLUMN active INTEGER DEFAULT 1",
            "ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'active'",
            "ALTER TABLE masters ADD COLUMN vk_id INTEGER DEFAULT NULL",
        ]
        for sql in migrations:
            try:
                await db.execute(sql)
                await db.commit()
            except aiosqlite.OperationalError:
                pass


# ============ МАСТЕРА ============

async def get_masters_by_service(service: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, name FROM masters WHERE services LIKE ? AND active = 1",
            (f"%{service}%",)
        )
        return await cursor.fetchall()


async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM masters WHERE active = 1")
        return await cursor.fetchall()


async def add_master(name: str, services: str, vk_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO masters (name, services, vk_id) VALUES (?, ?, ?)",
            (name, services, vk_id)
        )
        await db.commit()


async def update_master_vk_id(master_id: int, vk_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE masters SET vk_id = ? WHERE id = ?",
            (vk_id, master_id)
        )
        await db.commit()


async def get_master_vk_id(master_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT vk_id FROM masters WHERE id = ?", (master_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None


async def get_master_name(master_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM masters WHERE id = ?", (master_id,))
        row = await cursor.fetchone()
        return row[0] if row else "Мастер"


# ============ СЛОТЫ ============

async def add_slot(master_id: int, date: str, time: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO slots (master_id, date, time, available) VALUES (?, ?, ?, 1)",
            (master_id, date, time)
        )
        await db.commit()


async def get_available_dates(master_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT DISTINCT date FROM slots
            WHERE master_id = ? AND available = 1 AND date >= date('now')
            ORDER BY date LIMIT 30
        """, (master_id,))
        return [row[0] for row in await cursor.fetchall()]


async def get_available_times(master_id: int, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT time FROM slots
            WHERE master_id = ? AND date = ? AND available = 1
            ORDER BY time
        """, (master_id, date))
        return [row[0] for row in await cursor.fetchall()]


async def delete_day_slots(master_id: int, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM slots WHERE master_id = ? AND date = ?",
            (master_id, date)
        )
        await db.commit()


# ============ ЗАПИСИ ============

async def book_slot(user_id: int, master_id: int, date: str, time: str,
                    service: str, name: str, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем активную запись
        cursor = await db.execute(
            "SELECT id FROM bookings WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        if await cursor.fetchone():
            raise ValueError("У вас уже есть активная запись")

        await db.execute("""
            INSERT INTO bookings (user_id, master_id, date, time, service, name, phone, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, (user_id, master_id, date, time, service, name, phone))

        await db.execute(
            "UPDATE slots SET available = 0 WHERE master_id = ? AND date = ? AND time = ?",
            (master_id, date, time)
        )
        await db.commit()


async def cancel_booking(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT master_id, date, time FROM bookings WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        master_id, date, time = row

        await db.execute(
            "UPDATE slots SET available = 1 WHERE master_id = ? AND date = ? AND time = ?",
            (master_id, date, time)
        )
        await db.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        await db.commit()
        return {"date": date, "time": time}


async def get_user_booking(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT b.date, b.time, b.service, b.name, b.phone, m.name as master_name, b.master_id
            FROM bookings b
            JOIN masters m ON b.master_id = m.id
            WHERE b.user_id = ? AND b.status = 'active'
        """, (user_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "date": row[0], "time": row[1], "service": row[2],
            "name": row[3], "phone": row[4], "master_name": row[5],
            "master_id": row[6]
        }


async def get_all_bookings_admin():
    """Все активные записи для администратора"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT b.date, b.time, b.service, b.name, b.phone, m.name as master_name, b.user_id
            FROM bookings b
            JOIN masters m ON b.master_id = m.id
            WHERE b.status = 'active'
            ORDER BY b.date, b.time
        """)
        rows = await cursor.fetchall()
        return [
            {
                "date": r[0], "time": r[1], "service": r[2],
                "name": r[3], "phone": r[4], "master_name": r[5], "user_id": r[6]
            }
            for r in rows
        ]


async def admin_cancel_booking_by_user(user_id: int):
    return await cancel_booking(user_id)
