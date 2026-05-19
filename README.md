# VK Бот для записи в салон красоты

Бот для автоматизации записи клиентов. Написан на Python с использованием библиотеки vkbottle и асинхронной БД SQLite.

## Функции

- Выбор услуги → мастера → даты → времени
- Запись с указанием имени и телефона
- Отмена записи
- Админ-панель: просмотр записей, управление мастерами и расписанием
- Уведомления мастерам через VK

## Технологии

- Python 3.10
- vkbottle
- aiosqlite
- asyncio

## Установка

```bash
git clone https://github.com/raxat0/vk-manicure-bot.git
cd vk-manicure-bot
pip install -r requirements.txt
