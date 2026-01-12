import os
from dotenv import load_dotenv

load_dotenv()

# ⚠️ ВНИМАНИЕ: Токен бота будем вставлять позже!
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ⚠️ ВАЖНО: Замените 123456789 на ВАШ реальный ID в Telegram
# Как узнать ID: напишите @userinfobot в Telegram
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(","))) if os.getenv("ADMIN_IDS") else [123456789]

# Константы графика смен
SHIFT_CYCLE = ['day', 'night', 'rest', 'off']  # Цикл смен
START_DATE = (2024, 10, 1)  # 1 октября 2024 - у смены 1 день

# База данных
DB_PATH = "database.db"

# Другое
SHIFT_HOURS = 12  # Длительность смены
DEFAULT_SALARY = 137500  # Оклад по умолчанию