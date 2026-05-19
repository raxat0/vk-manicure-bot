# keyboards.py
from vkbottle import Keyboard, Callback, OpenLink
from config import CHANNEL_LINK, PORTFOLIO_LINK


# ============ ГЛАВНОЕ МЕНЮ ============

def main_menu_keyboard(is_admin: bool = False, has_booking: bool = False):
    kb = Keyboard(inline=True)
    kb.add(Callback("📅 Записаться на приём", payload={"action": "start_booking"}))
    kb.row()
    kb.add(Callback("💰 Прайс-лист", payload={"action": "prices"}))
    kb.add(Callback("📸 Портфолио", payload={"action": "portfolio"}))
    if has_booking:
        kb.row()
        kb.add(Callback("📋 Моя запись", payload={"action": "my_booking"}))
        kb.add(Callback("❌ Отменить запись", payload={"action": "cancel_booking_ask"}))
    if is_admin:
        kb.row()
        kb.add(Callback("⚙️ Панель администратора", payload={"action": "admin_menu"}))
    return kb.get_json()


# ============ УСЛУГИ ============

def service_keyboard():
    kb = Keyboard(inline=True)
    kb.add(Callback("💅 Маникюр", payload={"action": "choose_service", "service": "Маникюр"}))
    kb.add(Callback("🦶 Педикюр", payload={"action": "choose_service", "service": "Педикюр"}))
    kb.row()
    kb.add(Callback("💄 Визажист", payload={"action": "choose_service", "service": "Визажист"}))
    kb.add(Callback("✂️ Парикмахер", payload={"action": "choose_service", "service": "Парикмахер"}))
    kb.row()
    kb.add(Callback("🔙 Назад", payload={"action": "back_to_menu"}))
    return kb.get_json()


# ============ МАСТЕРА ============

def masters_keyboard(masters):
    kb = Keyboard(inline=True)
    for i, (master_id, name) in enumerate(masters):
        kb.add(Callback(f"👩 {name}", payload={"action": "choose_master", "master_id": master_id}))
        if i % 2 == 1:
            kb.row()
    if len(masters) % 2 == 1:
        kb.row()
    kb.add(Callback("🔙 Назад к услугам", payload={"action": "back_to_services"}))
    return kb.get_json()


# ============ ПОДТВЕРЖДЕНИЕ ОТМЕНЫ ============

def cancel_confirm_keyboard():
    kb = Keyboard(inline=True)
    kb.add(Callback("✅ Да, отменить", payload={"action": "cancel_confirm_yes"}))
    kb.add(Callback("🔙 Нет, оставить", payload={"action": "back_to_menu"}))
    return kb.get_json()


# ============ ПОСЛЕ ЗАПИСИ ============

def after_booking_keyboard(is_admin: bool = False):
    kb = Keyboard(inline=True)
    kb.add(Callback("📋 Моя запись", payload={"action": "my_booking"}))
    kb.row()
    kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
    if is_admin:
        kb.row()
        kb.add(Callback("⚙️ Панель администратора", payload={"action": "admin_menu"}))
    return kb.get_json()


# ============ ПОРТФОЛИО ============

def portfolio_keyboard():
    kb = Keyboard(inline=True)
    kb.add(OpenLink(label="📷 Смотреть портфолио", link=PORTFOLIO_LINK))
    kb.row()
    kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
    return kb.get_json()


# ============ АДМИН-МЕНЮ ============

def admin_menu_keyboard():
    kb = Keyboard(inline=True)
    kb.add(Callback("📋 Все записи", payload={"action": "admin_view_bookings"}))
    kb.add(Callback("📅 Расписание", payload={"action": "admin_view_schedule"}))
    kb.row()
    kb.add(Callback("➕ Добавить слоты", payload={"action": "admin_add_slot"}))
    kb.add(Callback("🗑 Удалить день", payload={"action": "admin_close_day"}))
    kb.row()
    kb.add(Callback("👩 Добавить мастера", payload={"action": "admin_add_master"}))
    kb.add(Callback("📱 VK мастера", payload={"action": "admin_set_master_vk"}))
    kb.row()
    kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
    return kb.get_json()


def admin_back_keyboard():
    kb = Keyboard(inline=True)
    kb.add(Callback("🔙 Назад в админ-панель", payload={"action": "admin_menu"}))
    return kb.get_json()


# ============ ПАГИНАЦИЯ ДАТ ============

async def date_keyboard(available_dates, page: int = 0, back_action: str = "back_to_menu"):
    kb = Keyboard(inline=True)
    per_page = 6
    start = page * per_page
    end = start + per_page
    dates_on_page = available_dates[start:end]

    for i, d in enumerate(dates_on_page):
        if i > 0 and i % 3 == 0:
            kb.row()
        # Форматируем дату красиво: 2026-05-10 → 10.05
        try:
            from datetime import datetime
            dt = datetime.strptime(d, "%Y-%m-%d")
            label = dt.strftime("%d.%m")
        except Exception:
            label = d
        kb.add(Callback(label, payload={"action": "select_date", "date": d}))

    kb.row()
    has_prev = page > 0
    has_next = end < len(available_dates)

    if has_prev:
        kb.add(Callback("◀️ Назад", payload={"action": "date_page", "page": page - 1}))
    if has_next:
        kb.add(Callback("Вперёд ▶️", payload={"action": "date_page", "page": page + 1}))

    kb.row()
    kb.add(Callback("🔙 Главное меню", payload={"action": back_action}))
    return kb.get_json()


# ============ ПАГИНАЦИЯ ВРЕМЕНИ ============

async def time_keyboard(available_times, page: int = 0):
    kb = Keyboard(inline=True)
    per_page = 6
    start = page * per_page
    end = start + per_page
    times_on_page = available_times[start:end]

    for i, t in enumerate(times_on_page):
        if i > 0 and i % 3 == 0:
            kb.row()
        kb.add(Callback(f"🕐 {t}", payload={"action": "select_time", "time": t}))

    kb.row()
    has_prev = page > 0
    has_next = end < len(available_times)

    if has_prev:
        kb.add(Callback("◀️ Назад", payload={"action": "time_page", "page": page - 1}))
    if has_next:
        kb.add(Callback("Вперёд ▶️", payload={"action": "time_page", "page": page + 1}))

    kb.row()
    kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
    return kb.get_json()


# ============ ВЫБОР МАСТЕРА В АДМИНКЕ ============

def admin_master_choice_keyboard(masters, action: str):
    kb = Keyboard(inline=True)
    for mid, name in masters:
        kb.add(Callback(f"👩 {name}", payload={"action": action, "master_id": mid}))
        kb.row()
    kb.add(Callback("🔙 Назад в админ-панель", payload={"action": "admin_menu"}))
    return kb.get_json()


# ============ ВЫБОР ДАТЫ В АДМИНКЕ ============

async def admin_date_keyboard(available_dates, master_id: int, page: int = 0):
    kb = Keyboard(inline=True)
    per_page = 6
    start = page * per_page
    end = start + per_page
    dates_on_page = available_dates[start:end]

    for i, d in enumerate(dates_on_page):
        if i > 0 and i % 3 == 0:
            kb.row()
        try:
            from datetime import datetime
            dt = datetime.strptime(d, "%Y-%m-%d")
            label = dt.strftime("%d.%m")
        except Exception:
            label = d
        kb.add(Callback(label, payload={"action": "admin_select_date", "date": d, "master_id": master_id}))

    kb.row()
    has_prev = page > 0
    has_next = end < len(available_dates)

    if has_prev:
        kb.add(Callback("◀️ Назад", payload={"action": "admin_date_page", "page": page - 1, "master_id": master_id}))
    if has_next:
        kb.add(Callback("Вперёд ▶️", payload={"action": "admin_date_page", "page": page + 1, "master_id": master_id}))

    kb.row()
    kb.add(Callback("🔙 Назад в админ-панель", payload={"action": "admin_menu"}))
    return kb.get_json()
