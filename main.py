# main.py
import asyncio
import logging
import random
import aiosqlite
from datetime import datetime

from vkbottle import LoopWrapper, GroupEventType, Keyboard, Callback
from vkbottle.bot import Bot, Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadContainsRule

from config import TOKEN, ADMIN_IDS, STUDIO_NAME, DB_PATH
from database import (
    init_db, get_masters_by_service, get_all_masters, add_slot, add_master,
    get_available_dates, get_available_times, book_slot, cancel_booking,
    get_user_booking, get_all_bookings_admin, delete_day_slots,
    get_master_name, admin_cancel_booking_by_user,
    get_master_vk_id, update_master_vk_id
)
from states import BookingStates, AdminStates
from keyboards import (
    main_menu_keyboard, service_keyboard, masters_keyboard,
    admin_menu_keyboard, admin_back_keyboard, date_keyboard, time_keyboard,
    portfolio_keyboard, cancel_confirm_keyboard, after_booking_keyboard,
    admin_master_choice_keyboard, admin_date_keyboard
)

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)


# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def safe_send(event_or_msg, text: str, keyboard=None):
    random_id = random.randint(1, 2147483647)
    try:
        if isinstance(event_or_msg, MessageEvent):
            await event_or_msg.ctx_api.messages.send(
                peer_id=event_or_msg.peer_id,
                message=text,
                keyboard=keyboard,
                random_id=random_id
            )
        else:
            await event_or_msg.answer(text, keyboard=keyboard)
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")


async def notify_master(master_id: int, text: str):
    """Отправляет уведомление мастеру, если у него привязан VK ID."""
    vk_id = await get_master_vk_id(master_id)
    if not vk_id:
        return
    try:
        await bot.api.messages.send(
            user_id=vk_id,
            message=text,
            random_id=random.randint(1, 2147483647)
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить мастера (vk_id={vk_id}): {e}")


async def safe_delete_state(peer_id: int):
    try:
        if await bot.state_dispenser.get(peer_id):
            await bot.state_dispenser.delete(peer_id)
    except Exception:
        pass


def format_booking(booking: dict) -> str:
    return (
        f"🗓 Дата: {booking['date']}\n"
        f"⏰ Время: {booking['time']}\n"
        f"✨ Услуга: {booking['service']}\n"
        f"👩 Мастер: {booking['master_name']}\n"
        f"👤 Имя: {booking['name']}\n"
        f"📱 Телефон: {booking['phone']}"
    )


# ====================== СТАРТ ======================

@bot.on.private_message(text=["/start", "меню", "начать", "привет", "старт"])
async def start_handler(message: Message):
    await safe_delete_state(message.peer_id)
    booking = await get_user_booking(message.from_id)
    await message.answer(
        f"👋 Добро пожаловать в {STUDIO_NAME}!\n\n"
        f"{'📋 У вас есть активная запись.\n\n' if booking else ''}"
        "Выберите действие из меню ниже:",
        keyboard=main_menu_keyboard(is_admin(message.from_id), bool(booking))
    )


# ====================== ГЛАВНОЕ МЕНЮ (КНОПКИ) ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "back_to_menu"}))
async def back_to_menu_handler(event: MessageEvent):
    await safe_delete_state(event.peer_id)
    booking = await get_user_booking(event.user_id)
    await safe_send(
        event,
        f"🏠 Главное меню\n{'📋 У вас есть активная запись.' if booking else ''}",
        main_menu_keyboard(is_admin(event.user_id), bool(booking))
    )


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "back_to_services"}))
async def back_to_services_handler(event: MessageEvent):
    await safe_send(event, "✨ Выберите услугу:", service_keyboard())


# ====================== МОЯ ЗАПИСЬ ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "my_booking"}))
async def my_booking_handler(event: MessageEvent):
    booking = await get_user_booking(event.user_id)
    if booking:
        text = f"📋 Ваша запись:\n\n{format_booking(booking)}"
        kb = Keyboard(inline=True)
        kb.add(Callback("❌ Отменить запись", payload={"action": "cancel_booking_ask"}))
        kb.row()
        kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
        await safe_send(event, text, kb.get_json())
    else:
        await safe_send(event, "У вас нет активных записей.", main_menu_keyboard(is_admin(event.user_id), False))


# ====================== ОТМЕНА ЗАПИСИ ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "cancel_booking_ask"}))
async def cancel_booking_ask(event: MessageEvent):
    booking = await get_user_booking(event.user_id)
    if not booking:
        await safe_send(event, "У вас нет активных записей.", main_menu_keyboard(is_admin(event.user_id), False))
        return
    text = (
        f"⚠️ Вы хотите отменить запись?\n\n"
        f"{format_booking(booking)}\n\n"
        "Подтвердите отмену:"
    )
    await safe_send(event, text, cancel_confirm_keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "cancel_confirm_yes"}))
async def cancel_confirm_yes(event: MessageEvent):
    # Получаем запись ДО отмены, чтобы знать master_id
    booking_before = await get_user_booking(event.user_id)
    result = await cancel_booking(event.user_id)
    if result:
        # Уведомляем мастера об отмене
        if booking_before:
            await notify_master(
                booking_before["master_id"],
                f"❌ Клиент отменил запись!\n\n"
                f"📅 {result['date']} в {result['time']}\n"
                f"✨ Услуга: {booking_before.get('service', '—')}\n"
                f"👤 {booking_before.get('name', '—')}\n"
                f"📱 {booking_before.get('phone', '—')}"
            )
        await safe_send(
            event,
            f"✅ Запись на {result['date']} в {result['time']} успешно отменена.\n\n"
            "Будем рады видеть вас снова! 💅",
            main_menu_keyboard(is_admin(event.user_id), False)
        )
    else:
        await safe_send(event, "У вас нет активных записей.", main_menu_keyboard(is_admin(event.user_id), False))


# ====================== ПРАЙС-ЛИСТ ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "prices"}))
async def prices_handler(event: MessageEvent):
    text = (
        "💰 Прайс-лист\n\n"
        "💅 Маникюр:\n"
        "   • Классический — от 800 ₽\n"
        "   • С покрытием гель-лак — от 1 200 ₽\n"
        "   • Наращивание — от 2 500 ₽\n\n"
        "🦶 Педикюр:\n"
        "   • Классический — от 1 000 ₽\n"
        "   • Европейский — от 1 300 ₽\n"
        "   • С покрытием — от 1 600 ₽\n\n"
        "💄 Визажист:\n"
        "   • Дневной макияж — от 1 500 ₽\n"
        "   • Вечерний макияж — от 2 000 ₽\n\n"
        "✂️ Парикмахер:\n"
        "   • Стрижка — от 500 ₽\n"
        "   • Окрашивание — от 2 000 ₽\n"
        "   • Укладка — от 800 ₽\n\n"
        "📞 Точную стоимость уточняйте у мастера."
    )
    kb = Keyboard(inline=True)
    kb.add(Callback("📅 Записаться", payload={"action": "start_booking"}))
    kb.row()
    kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
    await safe_send(event, text, kb.get_json())


# ====================== ПОРТФОЛИО ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "portfolio"}))
async def portfolio_handler(event: MessageEvent):
    await safe_send(event, "📸 Наши работы:", portfolio_keyboard())


# ====================== ЗАПИСЬ НА ПРИЁМ ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "start_booking"}))
async def start_booking(event: MessageEvent):
    # Проверяем, есть ли уже запись
    booking = await get_user_booking(event.user_id)
    if booking:
        text = (
            f"⚠️ У вас уже есть активная запись:\n\n"
            f"{format_booking(booking)}\n\n"
            "Для новой записи сначала отмените текущую."
        )
        kb = Keyboard(inline=True)
        kb.add(Callback("❌ Отменить текущую запись", payload={"action": "cancel_booking_ask"}))
        kb.row()
        kb.add(Callback("🔙 Главное меню", payload={"action": "back_to_menu"}))
        await safe_send(event, text, kb.get_json())
        return

    await safe_delete_state(event.peer_id)
    await bot.state_dispenser.set(event.peer_id, BookingStates.WAITING_SERVICE)
    await safe_send(event, "✨ Выберите услугу:", service_keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "choose_service"}))
async def choose_service(event: MessageEvent):
    service = event.payload["service"]
    masters = await get_masters_by_service(service)

    if not masters:
        await safe_send(event, f"😔 К сожалению, на услугу «{service}» нет доступных мастеров.\n\nПопробуйте выбрать другую услугу:", service_keyboard())
        return

    # Если один мастер — сразу переходим к датам
    if len(masters) == 1 or service in ["Визажист", "Парикмахер"]:
        master_id, master_name = masters[0]
        await bot.state_dispenser.set(event.peer_id, BookingStates.WAITING_DATE,
                                      service=service, master_id=master_id, master_name=master_name)
        dates = await get_available_dates(master_id)
        if not dates:
            await safe_send(event, f"😔 У мастера {master_name} пока нет свободных дат.\n\nПопробуйте позже.", main_menu_keyboard(is_admin(event.user_id)))
            return
        await safe_send(
            event,
            f"✨ Услуга: {service}\n👩 Мастер: {master_name}\n\n📅 Выберите удобную дату:",
            await date_keyboard(dates)
        )
    else:
        await bot.state_dispenser.set(event.peer_id, BookingStates.WAITING_MASTER, service=service)
        await safe_send(event, f"✨ Услуга: {service}\n\n👩 Выберите мастера:", masters_keyboard(masters))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "choose_master"}))
async def choose_master(event: MessageEvent):
    master_id = event.payload["master_id"]
    state = await bot.state_dispenser.get(event.peer_id)
    service = state.payload.get("service") if state else "Неизвестно"
    master_name = await get_master_name(master_id)

    await bot.state_dispenser.set(event.peer_id, BookingStates.WAITING_DATE,
                                  service=service, master_id=master_id, master_name=master_name)

    dates = await get_available_dates(master_id)
    if not dates:
        await safe_send(event, f"😔 У мастера {master_name} пока нет свободных дат.", main_menu_keyboard(is_admin(event.user_id)))
        return
    await safe_send(
        event,
        f"✨ Услуга: {service}\n👩 Мастер: {master_name}\n\n📅 Выберите удобную дату:",
        await date_keyboard(dates)
    )


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "select_date"}))
async def select_date(event: MessageEvent):
    state = await bot.state_dispenser.get(event.peer_id)
    if not state:
        return

    # Если это состояние закрытия дня (админ) — игнорируем здесь
    if state.state in [AdminStates.WAITING_CLOSE_DAY]:
        return

    date = event.payload["date"]
    master_id = state.payload.get("master_id")

    await bot.state_dispenser.set(event.peer_id, BookingStates.WAITING_TIME,
                                  **state.payload, date=date)

    times = await get_available_times(master_id, date)
    if not times:
        await safe_send(event, "😔 На эту дату нет свободного времени. Выберите другую дату:",
                        await date_keyboard(await get_available_dates(master_id)))
        return

    try:
        from datetime import datetime as dt
        d = dt.strptime(date, "%Y-%m-%d")
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        day_label = f"{d.strftime('%d.%m.%Y')} ({day_names[d.weekday()]})"
    except Exception:
        day_label = date

    await safe_send(
        event,
        f"📅 Дата: {day_label}\n\n⏰ Выберите удобное время:",
        await time_keyboard(times)
    )


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "date_page"}))
async def date_page_handler(event: MessageEvent):
    page = int(event.payload.get("page", 0))
    state = await bot.state_dispenser.get(event.peer_id)
    if not state:
        return
    master_id = state.payload.get("master_id")
    dates = await get_available_dates(master_id)
    await safe_send(event, f"📅 Выберите дату:", await date_keyboard(dates, page))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "time_page"}))
async def time_page_handler(event: MessageEvent):
    page = int(event.payload.get("page", 0))
    state = await bot.state_dispenser.get(event.peer_id)
    if not state:
        return
    master_id = state.payload.get("master_id")
    date = state.payload.get("date")
    times = await get_available_times(master_id, date)
    await safe_send(event, f"⏰ Выберите время:", await time_keyboard(times, page))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "select_time"}))
async def select_time(event: MessageEvent):
    time = event.payload["time"]
    state = await bot.state_dispenser.get(event.peer_id)
    if not state:
        return

    await bot.state_dispenser.set(event.peer_id, BookingStates.WAITING_NAME,
                                  **state.payload, time=time)

    await safe_send(
        event,
        f"✅ Отлично!\n"
        f"📅 {state.payload.get('date')} в {time}\n"
        f"👩 Мастер: {state.payload.get('master_name')}\n"
        f"✨ Услуга: {state.payload.get('service')}\n\n"
        "👤 Введите ваше имя и фамилию:"
    )


@bot.on.private_message(state=BookingStates.WAITING_NAME)
async def process_name(message: Message):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Пожалуйста, введите ваше полное имя:")
        return
    state = await bot.state_dispenser.get(message.peer_id)
    await bot.state_dispenser.set(message.peer_id, BookingStates.WAITING_PHONE,
                                  **state.payload, name=name)
    await message.answer(
        f"👤 Имя: {name}\n\n"
        "📱 Введите номер телефона для подтверждения:"
    )


@bot.on.private_message(state=BookingStates.WAITING_PHONE)
async def process_phone(message: Message):
    phone = message.text.strip()
    state = await bot.state_dispenser.get(message.peer_id)
    data = state.payload

    try:
        await book_slot(
            user_id=message.from_id,
            master_id=data["master_id"],
            date=data["date"],
            time=data["time"],
            service=data.get("service", "Неизвестно"),
            name=data["name"],
            phone=phone
        )
        await bot.state_dispenser.delete(message.peer_id)

        # Уведомляем мастера
        await notify_master(
            data["master_id"],
            f"💅 Новая запись к вам!\n\n"
            f"📅 Дата: {data['date']} в {data['time']}\n"
            f"✨ Услуга: {data.get('service')}\n"
            f"👤 Клиент: {data['name']}\n"
            f"📱 Телефон: {phone}"
        )

        # Уведомляем всех админов
        for admin_id in ADMIN_IDS:
            try:
                await bot.api.messages.send(
                    user_id=admin_id,
                    message=(
                        f"🔔 Новая запись!\n\n"
                        f"✨ Услуга: {data.get('service')}\n"
                        f"👩 Мастер: {data.get('master_name')}\n"
                        f"📅 Дата: {data['date']} в {data['time']}\n"
                        f"👤 Клиент: {data['name']}\n"
                        f"📱 Телефон: {phone}"
                    ),
                    random_id=random.randint(1, 2147483647)
                )
            except Exception:
                pass

        await message.answer(
            f"🎉 Запись подтверждена!\n\n"
            f"✨ Услуга: {data.get('service')}\n"
            f"👩 Мастер: {data.get('master_name')}\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}\n"
            f"👤 Имя: {data['name']}\n"
            f"📱 Телефон: {phone}\n\n"
            "Ждём вас! 💅✨",
            keyboard=after_booking_keyboard(is_admin(message.from_id))
        )
    except ValueError as e:
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer(
            f"⚠️ {str(e)}",
            keyboard=main_menu_keyboard(is_admin(message.from_id), True)
        )
    except Exception as e:
        logging.error(f"Ошибка записи: {e}")
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer(
            "❌ Ошибка при создании записи. Пожалуйста, попробуйте снова.",
            keyboard=main_menu_keyboard(is_admin(message.from_id))
        )


# ====================== АДМИН-ПАНЕЛЬ ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_menu"}))
async def admin_menu_handler(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return
    await safe_delete_state(event.peer_id)
    await safe_send(event, "⚙️ Панель администратора\n\nВыберите действие:", admin_menu_keyboard())


# ---- Просмотр записей ----

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_view_bookings"}))
async def admin_view_bookings(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return

    bookings = await get_all_bookings_admin()
    if not bookings:
        await safe_send(event, "📋 Активных записей нет.", admin_menu_keyboard())
        return

    text = f"📋 Все активные записи ({len(bookings)}):\n\n"
    for i, b in enumerate(bookings, 1):
        text += (
            f"{'─' * 25}\n"
            f"#{i} 📅 {b['date']} ⏰ {b['time']}\n"
            f"   ✨ {b['service']} → 👩 {b['master_name']}\n"
            f"   👤 {b['name']}  📱 {b['phone']}\n"
        )
        if i % 10 == 0 and i < len(bookings):
            await safe_send(event, text)
            text = ""

    if text:
        await safe_send(event, text.strip(), admin_menu_keyboard())


# ---- Просмотр расписания ----

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_view_schedule"}))
async def admin_view_schedule(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return

    masters = await get_all_masters()
    text = "📅 Расписание мастеров:\n\n"

    for master_id, master_name in masters:
        dates = await get_available_dates(master_id)
        text += f"👩 {master_name}:\n"
        if dates:
            for d in dates[:7]:
                times = await get_available_times(master_id, d)
                text += f"   📅 {d} — {len(times)} слот(ов): {', '.join(times[:5])}"
                if len(times) > 5:
                    text += f" (+{len(times) - 5})"
                text += "\n"
        else:
            text += "   Нет свободных дат\n"
        text += "\n"

    await safe_send(event, text.strip() or "Расписание пустое.", admin_menu_keyboard())


# ---- Добавить слоты ----

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_add_slot"}))
async def admin_add_slot_start(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return
    masters = await get_all_masters()
    await safe_send(event, "➕ Выберите мастера для добавления слотов:",
                    admin_master_choice_keyboard(masters, "admin_choose_master_for_slots"))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_choose_master_for_slots"}))
async def admin_choose_master_for_slots(event: MessageEvent):
    if not is_admin(event.user_id):
        return
    master_id = event.payload["master_id"]
    master_name = await get_master_name(master_id)
    await bot.state_dispenser.set(event.peer_id, AdminStates.WAITING_ADD_SLOTS, master_id=master_id)
    await safe_send(
        event,
        f"➕ Добавление слотов для мастера: {master_name}\n\n"
        "📝 Введите слоты в формате:\n"
        "<code>ГГГГ-ММ-ДД ЧЧ:ММ,ЧЧ:ММ,ЧЧ:ММ</code>\n\n"
        "Примеры:\n"
        "2026-05-10 10:00,12:00,14:00\n"
        "2026-05-11 09:00,11:30\n"
        "2026-05-12 15:00\n\n"
        "Можно указать несколько дней — каждый с новой строки."
    )


@bot.on.private_message(state=AdminStates.WAITING_ADD_SLOTS)
async def admin_add_slots(message: Message):
    if not is_admin(message.from_id):
        return

    state = await bot.state_dispenser.get(message.peer_id)
    if not state or "master_id" not in state.payload:
        await message.answer("⚠️ Ошибка. Начните заново.", keyboard=admin_menu_keyboard())
        await safe_delete_state(message.peer_id)
        return

    master_id = state.payload["master_id"]
    lines = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    added = 0
    errors = []

    for line in lines:
        try:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                errors.append(f"❌ '{line}' — неверный формат")
                continue
            date_str, times_str = parts[0].strip(), parts[1].strip()
            datetime.strptime(date_str, "%Y-%m-%d")

            time_list = [t.strip() for t in times_str.replace("-", ",").split(",") if t.strip()]
            for t in time_list:
                datetime.strptime(t, "%H:%M")
                await add_slot(master_id, date_str, t)
                added += 1
        except ValueError as e:
            errors.append(f"❌ '{line}' — {e}")
            continue

    await bot.state_dispenser.delete(message.peer_id)

    result = f"✅ Добавлено {added} слот(ов)!"
    if errors:
        result += f"\n\n⚠️ Ошибки ({len(errors)}):\n" + "\n".join(errors[:5])

    await message.answer(result, keyboard=admin_menu_keyboard())


# ---- Удалить день ----

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_close_day"}))
async def admin_close_day_start(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return
    masters = await get_all_masters()
    await bot.state_dispenser.set(event.peer_id, AdminStates.WAITING_CLOSE_DAY_MASTER)
    await safe_send(event, "🗑 Выберите мастера для удаления дня:",
                    admin_master_choice_keyboard(masters, "admin_close_choose_master"))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_close_choose_master"}))
async def admin_close_choose_master(event: MessageEvent):
    if not is_admin(event.user_id):
        return
    master_id = event.payload["master_id"]
    master_name = await get_master_name(master_id)

    dates = await get_available_dates(master_id)
    if not dates:
        await safe_send(event, f"У мастера {master_name} нет открытых дат.", admin_menu_keyboard())
        await safe_delete_state(event.peer_id)
        return

    await bot.state_dispenser.set(event.peer_id, AdminStates.WAITING_CLOSE_DAY, master_id=master_id)
    await safe_send(
        event,
        f"🗑 Мастер: {master_name}\n\nВыберите день для удаления:",
        await admin_date_keyboard(dates, master_id)
    )


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_select_date"}))
async def admin_select_date(event: MessageEvent):
    if not is_admin(event.user_id):
        return

    state = await bot.state_dispenser.get(event.peer_id)
    if not state or state.state != AdminStates.WAITING_CLOSE_DAY:
        return

    date_to_delete = event.payload["date"]
    master_id = state.payload.get("master_id") or event.payload.get("master_id")
    master_name = await get_master_name(master_id)

    try:
        await delete_day_slots(master_id, date_to_delete)

        # Отменяем записи клиентов на этот день
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id FROM bookings WHERE master_id = ? AND date = ? AND status = 'active'",
                (master_id, date_to_delete)
            )
            users_to_notify = [row[0] for row in await cursor.fetchall()]

            await db.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE master_id = ? AND date = ? AND status = 'active'",
                (master_id, date_to_delete)
            )
            await db.commit()

        # Уведомляем мастера об удалении дня
        await notify_master(
            master_id,
            f"⚠️ Администратор закрыл день {date_to_delete}.\n"
            f"Все ваши слоты на эту дату удалены."
            + (f"\nОтменено записей клиентов: {len(users_to_notify)}" if users_to_notify else "")
        )

        # Уведомляем клиентов об отмене
        for user_id in users_to_notify:
            try:
                await bot.api.messages.send(
                    user_id=user_id,
                    message=(
                        f"⚠️ Уважаемый клиент!\n\n"
                        f"Ваша запись на {date_to_delete} к мастеру {master_name} была отменена администратором.\n\n"
                        "Приносим извинения. Вы можете записаться на другую дату. 💅"
                    ),
                    random_id=random.randint(1, 2147483647)
                )
            except Exception:
                pass

        await safe_delete_state(event.peer_id)
        notified = f"\n📢 Уведомлено клиентов: {len(users_to_notify)}" if users_to_notify else ""
        await safe_send(
            event,
            f"✅ День {date_to_delete} у мастера {master_name} удалён.{notified}",
            admin_menu_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка удаления дня: {e}")
        await safe_send(event, "❌ Ошибка при удалении дня.", admin_menu_keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_date_page"}))
async def admin_date_page_handler(event: MessageEvent):
    if not is_admin(event.user_id):
        return
    page = int(event.payload.get("page", 0))
    master_id = event.payload.get("master_id")
    dates = await get_available_dates(master_id)
    await safe_send(event, "Выберите дату:", await admin_date_keyboard(dates, master_id, page))


# ---- Добавить мастера ----

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_add_master"}))
async def admin_add_master_start(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return
    await bot.state_dispenser.set(event.peer_id, AdminStates.WAITING_ADD_MASTER_NAME)
    await safe_send(
        event,
        "👩 Добавление нового мастера\n\n"
        "Введите имя мастера:"
    )


@bot.on.private_message(state=AdminStates.WAITING_ADD_MASTER_NAME)
async def admin_add_master_name(message: Message):
    if not is_admin(message.from_id):
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Введите корректное имя:")
        return
    await bot.state_dispenser.set(message.peer_id, AdminStates.WAITING_ADD_MASTER_SERVICES, master_name=name)
    await message.answer(
        f"👩 Имя: {name}\n\n"
        "Введите услуги через запятую:\n"
        "Доступные: Маникюр, Педикюр, Визажист, Парикмахер\n\n"
        "Пример: Маникюр,Педикюр"
    )


@bot.on.private_message(state=AdminStates.WAITING_ADD_MASTER_SERVICES)
async def admin_add_master_services(message: Message):
    if not is_admin(message.from_id):
        return
    state = await bot.state_dispenser.get(message.peer_id)
    master_name = state.payload.get("master_name")
    services = message.text.strip()

    await bot.state_dispenser.set(message.peer_id, AdminStates.WAITING_ADD_MASTER_VK_ID,
                                  master_name=master_name, services=services)
    await message.answer(
        f"👩 Имя: {master_name}\n"
        f"✨ Услуги: {services}\n\n"
        "📱 Введите VK ID мастера для получения уведомлений о записях.\n\n"
        "Как узнать ID: откройте страницу мастера ВКонтакте, ID — это цифры в адресе (vk.com/id<b>123456</b>)\n\n"
        "Или напишите <b>0</b> чтобы пропустить (уведомления не будут отправляться)."
    )


@bot.on.private_message(state=AdminStates.WAITING_ADD_MASTER_VK_ID)
async def admin_add_master_vk_id(message: Message):
    if not is_admin(message.from_id):
        return
    state = await bot.state_dispenser.get(message.peer_id)
    master_name = state.payload.get("master_name")
    services = state.payload.get("services")

    raw = message.text.strip()
    vk_id = None
    if raw != "0":
        try:
            vk_id = int(raw)
            if vk_id <= 0:
                vk_id = None
        except ValueError:
            await message.answer("⚠️ Введите число (VK ID) или 0 чтобы пропустить:")
            return

    try:
        await add_master(master_name, services, vk_id)
        await bot.state_dispenser.delete(message.peer_id)

        vk_note = f"\n📱 VK ID: {vk_id} (уведомления включены ✅)" if vk_id else "\n📱 VK ID не задан (уведомления отключены)"
        await message.answer(
            f"✅ Мастер добавлен!\n\n"
            f"👩 Имя: {master_name}\n"
            f"✨ Услуги: {services}"
            f"{vk_note}",
            keyboard=admin_menu_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка добавления мастера: {e}")
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer("❌ Ошибка при добавлении мастера.", keyboard=admin_menu_keyboard())


# ---- Привязать VK ID к существующему мастеру ----

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_set_master_vk"}))
async def admin_set_master_vk_start(event: MessageEvent):
    if not is_admin(event.user_id):
        await event.show_snackbar("⛔ Доступ запрещён")
        return
    masters = await get_all_masters()
    await safe_send(event, "📱 Выберите мастера для привязки VK ID:",
                    admin_master_choice_keyboard(masters, "admin_set_vk_choose_master"))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadContainsRule({"action": "admin_set_vk_choose_master"}))
async def admin_set_vk_choose_master(event: MessageEvent):
    if not is_admin(event.user_id):
        return
    master_id = event.payload["master_id"]
    master_name = await get_master_name(master_id)
    current_vk = await get_master_vk_id(master_id)

    await bot.state_dispenser.set(event.peer_id, AdminStates.WAITING_SET_MASTER_VK_ID, master_id=master_id)
    current_note = f"Текущий VK ID: {current_vk}" if current_vk else "VK ID не задан"
    await safe_send(
        event,
        f"👩 Мастер: {master_name}\n"
        f"📱 {current_note}\n\n"
        "Введите новый VK ID мастера\n"
        "(или 0 чтобы убрать привязку):"
    )


@bot.on.private_message(state=AdminStates.WAITING_SET_MASTER_VK_ID)
async def admin_set_master_vk_id(message: Message):
    if not is_admin(message.from_id):
        return
    state = await bot.state_dispenser.get(message.peer_id)
    master_id = state.payload.get("master_id")
    master_name = await get_master_name(master_id)

    raw = message.text.strip()
    try:
        vk_id = int(raw)
    except ValueError:
        await message.answer("⚠️ Введите число (VK ID) или 0 чтобы убрать привязку:")
        return

    vk_id_to_save = vk_id if vk_id > 0 else None
    await update_master_vk_id(master_id, vk_id_to_save)
    await bot.state_dispenser.delete(message.peer_id)

    if vk_id_to_save:
        result = f"✅ VK ID {vk_id_to_save} привязан к мастеру {master_name}.\nТеперь мастер будет получать уведомления о записях."
    else:
        result = f"✅ VK ID мастера {master_name} удалён. Уведомления отключены."

    await message.answer(result, keyboard=admin_menu_keyboard())


# ====================== FALLBACK ======================

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent)
async def unknown_callback(event: MessageEvent):
    action = event.payload.get("action", "unknown") if event.payload else "unknown"
    logging.info(f"Необработанное действие: {action} от {event.user_id}")
    await event.show_snackbar("Эта кнопка недоступна")


@bot.on.private_message()
async def unknown_message(message: Message):
    booking = await get_user_booking(message.from_id)
    await message.answer(
        "👋 Привет! Используйте кнопки меню для навигации.\n"
        "Напишите /start для открытия главного меню.",
        keyboard=main_menu_keyboard(is_admin(message.from_id), bool(booking))
    )


# ====================== ЗАПУСК ======================

async def on_startup():
    await init_db()
    logging.info(f"✅ Бот '{STUDIO_NAME}' запущен!")
    logging.info(f"👑 Администраторы: {ADMIN_IDS}")


if __name__ == "__main__":
    loop_wrapper = LoopWrapper()
    loop_wrapper.on_startup.append(on_startup())
    bot.loop_wrapper = loop_wrapper
    bot.run_forever()
