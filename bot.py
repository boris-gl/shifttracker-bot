import logging
import asyncio
import re
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hbold

from config import BOT_TOKEN, ADMIN_IDS
from database import db
from keyboards import *
from calculations import *

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================================
# STATES (СОСТОЯНИЯ ДЛЯ FSM)
# ============================================

class ShiftState(StatesGroup):
    waiting_date = State()
    waiting_hours = State()

class PeriodState(StatesGroup):
    waiting_type = State()
    waiting_start = State()
    waiting_end = State()
    waiting_confirm = State()

class RatesState(StatesGroup):
    waiting_vacation = State()
    waiting_sick = State()

class AddEmployeeState(StatesGroup):
    waiting_user_id = State()
    waiting_full_name = State()
    waiting_shift = State()

class SalaryState(StatesGroup):
    waiting_amount = State()

class CheckDayState(StatesGroup):
    waiting_date = State()

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def parse_flexible_date(date_str: str) -> Optional[date]:
    """
    Умный парсинг даты с поддержкой разных форматов
    """
    date_str = date_str.strip().lower()
    today = date.today()
    
    # Специальные слова
    special_dates = {
        "сегодня": today,
        "завтра": today + timedelta(days=1),
        "послезавтра": today + timedelta(days=2),
        "вчера": today - timedelta(days=1),
        "позавчера": today - timedelta(days=2),
    }
    
    if date_str in special_dates:
        return special_dates[date_str]
    
    # Относительные дни: +7, +30, -5
    match = re.match(r'^([+-]?\d+)$', date_str)
    if match:
        days = int(match.group(1))
        return today + timedelta(days=days)
    
    # Формат: 15.10 (без года)
    match = re.match(r'^(\d{1,2})[\./-](\d{1,2})$', date_str)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        # Если месяц уже прошёл в этом году - берём следующий год
        if month < today.month or (month == today.month and day < today.day):
            year = today.year + 1
        else:
            year = today.year
        try:
            return date(year, month, day)
        except ValueError:
            return None
    
    # Форматы дат
    formats = [
        "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y",
        "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d",
        "%d.%m.%y", "%d/%m/%y", "%d-%m-%y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Текстовый формат: "15 октября 2026"
    month_names = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
        'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
        'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
        'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
    }
    
    match = re.match(r'^(\d{1,2})\s+([а-я]+)\s+(\d{4})$', date_str)
    if match:
        day, month_name, year = match.group(1), match.group(2), match.group(3)
        if month_name in month_names:
            try:
                return date(int(year), month_names[month_name], int(day))
            except ValueError:
                return None
    
    return None

def format_day_check_response(employee: Dict[str, Any], target_date: date, 
                             day_type: str, existing_record: Optional[Dict[str, Any]]) -> str:
    """
    Форматирование ответа о конкретном дне
    """
    # Эмодзи и русские названия
    emoji_map = {
        'day': '🌞',
        'night': '🌙', 
        'rest': '😴',
        'off': '🏠'
    }
    
    type_names = {
        'day': 'дневная смена',
        'night': 'ночная смена',
        'rest': 'отсыпной',
        'off': 'выходной'
    }
    
    # Определяем рабочий ли день
    is_work_day = day_type in ['day', 'night']
    
    # Форматируем дату
    date_str = target_date.strftime("%d.%m.%Y")
    weekday = target_date.strftime("%A").capitalize()
    
    # Русские названия дней недели
    weekdays_ru = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }
    weekday_ru = weekdays_ru.get(weekday, weekday)
    
    # Начинаем формировать ответ
    response = f"<b>📅 {date_str}</b> ({weekday_ru})\n"
    response += f"<b>👤 {employee['full_name']}</b> | Смена {employee['shift_number']}\n"
    response += "─" * 35 + "\n\n"
    
    # Информация по графику
    response += f"<b>📊 По графику:</b>\n"
    response += f"{emoji_map.get(day_type, '❓')} <b>{type_names.get(day_type, 'неизвестно')}</b>\n"
    
    if is_work_day:
        response += f"⏰ Плановые часы: <b>12 часов</b>\n"
    else:
        response += f"⏰ Плановые часы: <b>0 часов</b>\n"
    
    response += "\n"
    
    # Информация о фактической записи
    if existing_record:
        record_emojis = {
            'work': '✅',
            'reinforce': '⚡',
            'vacation': '🏖',
            'sick': '🤒',
            'unpaid': '🕐'
        }
        
        record_names = {
            'work': 'Рабочая смена',
            'reinforce': 'Усиление',
            'vacation': 'Отпуск',
            'sick': 'Больничный',
            'unpaid': 'За свой счёт'
        }
        
        response += f"<b>📝 Фактически отмечено:</b>\n"
        emoji = record_emojis.get(existing_record['day_type'], '❓')
        name = record_names.get(existing_record['day_type'], 'Неизвестно')
        response += f"{emoji} <b>{name}</b>\n"
        
        if existing_record['hours'] > 0:
            response += f"⏰ Отработано: <b>{existing_record['hours']} часов</b>\n"
    else:
        response += f"<b>📝 Фактически:</b> <i>запись отсутствует</i>\n"
    
    # Расстояние до даты
    today = date.today()
    days_diff = (target_date - today).days
    
    response += "\n"
    response += "─" * 35 + "\n"
    
    if days_diff > 0:
        weeks = days_diff // 7
        remaining_days = days_diff % 7
        
        if weeks > 0:
            if remaining_days > 0:
                response += f"⏳ До этой даты: <b>{weeks} нед. {remaining_days} дн.</b>\n"
            else:
                response += f"⏳ До этой даты: <b>{weeks} недель</b>\n"
        else:
            response += f"⏳ До этой даты: <b>{days_diff} дней</b>\n"
            
    elif days_diff == 0:
        response += f"⏳ <b>🎯 Сегодня!</b>\n"
    else:
        days_ago = abs(days_diff)
        weeks_ago = days_ago // 7
        remaining_days = days_ago % 7
        
        if weeks_ago > 0:
            if remaining_days > 0:
                response += f"⏳ Было: <b>{weeks_ago} нед. {remaining_days} дн. назад</b>\n"
            else:
                response += f"⏳ Было: <b>{weeks_ago} недель назад</b>\n"
        else:
            response += f"⏳ Было: <b>{days_ago} дней назад</b>\n"
    
    # Рекомендации
    response += "\n<b>💡 Что можно сделать:</b>\n"
    
    if existing_record:
        if existing_record['day_type'] == 'work' and existing_record['hours'] == 0:
            response += "• Указать отработанные часы (<code>/смена</code>)\n"
        response += "• Исправить запись (<code>/исправить</code>)\n"
    else:
        if is_work_day:
            response += "• Отметить смену (<code>/смена</code>)\n"
            response += "• Запланировать отпуск (<code>/отпуск_период</code>)\n"
        elif day_type == 'rest':
            response += "• Отметить как отсыпной\n"
        elif day_type == 'off':
            response += "• Отметить как выходной\n"
        
        if not is_work_day:
            response += "• Запланировать отсутствие\n"
    
    return response

# ============================================
# ОСНОВНЫЕ КОМАНДЫ
# ============================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /старт"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if employee:
        is_admin_user = is_admin(user_id)
        
        welcome_text = (
            f"👋 Привет, <b>{employee['full_name']}</b>!\n\n"
            f"Я — бот для учёта смен <b>ShiftTracker</b>.\n"
            f"Ваша смена: <b>{employee['shift_number']}</b>\n\n"
            f"<b>📋 Основные команды:</b>\n"
            f"/смена - отметить рабочую смену\n"
            f"/усиление - отметить выход вне графика\n"
            f"/отпуск - один день отпуска\n"
            f"/больничный - один день больничного\n"
            f"/за_счет - день за свой счёт\n"
            f"/отпуск_период - отпуск на несколько дней\n"
            f"/больничный_период - больничный на несколько дней\n\n"
            f"<b>🔍 Проверка графика:</b>\n"
            f"/статистика - статистика и расчёт\n"
            f"/график - мой график на месяц\n"
            f"/будет [дата] - проверить любой день\n\n"
            f"<b>⚙️ Управление:</b>\n"
            f"/исправить - удалить запись\n"
            f"/стоимость - установить ставки\n"
            f"/отпуски - мои отпуска\n"
            f"/больничные - мои больничные\n"
            f"/отмена_периода - удалить период\n\n"
            f"<i>Используйте кнопки ниже или команды...</i>"
        )
        
        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(is_admin_user),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👋 Привет!\n\n"
            f"Вы не зарегистрированы в системе.\n"
            f"Ваш ID: <b>{user_id}</b>\n\n"
            f"Передайте этот ID администратору для регистрации.",
            parse_mode="HTML"
        )

@dp.message(Command("смена"))
async def cmd_shift(message: Message, state: FSMContext):
    """Отметить рабочую смену"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.set_state(ShiftState.waiting_date)
    await message.answer(
        "📅 За какую дату отмечаете смену?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("отпуск"))
async def cmd_vacation(message: Message, state: FSMContext):
    """Отметить один день отпуска"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.update_data(absence_type='vacation')
    await message.answer(
        "📅 За какую дату отмечаете отпуск?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("больничный"))
async def cmd_sick(message: Message, state: FSMContext):
    """Отметить один день больничного"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.update_data(absence_type='sick')
    await message.answer(
        "📅 За какую дату отмечаете больничный?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("за_счет"))
async def cmd_unpaid(message: Message, state: FSMContext):
    """Отметить день за свой счёт"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.update_data(absence_type='unpaid')
    await message.answer(
        "📅 За какую дату отмечаете день за свой счёт?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("усиление"))
async def cmd_reinforce(message: Message, state: FSMContext):
    """Отметить выход вне графика"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.update_data(absence_type='reinforce')
    await message.answer(
        "📅 За какую дату отмечаете усиление?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("отпуск_период"))
async def cmd_vacation_period(message: Message, state: FSMContext):
    """Отпуск периодом"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.set_state(PeriodState.waiting_type)
    await state.update_data(period_type='vacation')
    await state.set_state(PeriodState.waiting_start)
    
    await message.answer(
        "🏖 Отметить отпуск\n"
        "📅 С какой даты начинается отпуск?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("больничный_период"))
async def cmd_sick_period(message: Message, state: FSMContext):
    """Больничный периодом"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.set_state(PeriodState.waiting_type)
    await state.update_data(period_type='sick')
    await state.set_state(PeriodState.waiting_start)
    
    await message.answer(
        "🤒 Отметить больничный\n"
        "📅 С какой даты начинается больничный?",
        reply_markup=get_date_keyboard()
    )

@dp.message(Command("статистика"))
async def cmd_stats(message: Message):
    """Статистика за текущий месяц"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    today = datetime.now()
    stats = calculate_month_stats(user_id, today.year, today.month)
    
    if stats:
        formatted_stats = format_month_stats(stats)
        await message.answer(formatted_stats)
    else:
        await message.answer("❌ Не удалось получить статистику.")

@dp.message(Command("график"))
async def cmd_schedule(message: Message):
    """График на текущий месяц"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    today = datetime.now()
    schedule = get_month_schedule(user_id, today.year, today.month)
    
    if schedule:
        formatted_schedule = format_month_schedule(schedule)
        await message.answer(formatted_schedule)
    else:
        await message.answer("❌ Не удалось получить график.")

@dp.message(Command("будет"))
async def cmd_check_day(message: Message, state: FSMContext):
    """
    Проверить график на конкретную дату
    Использование: /будет 15.10.2026
    Или просто: /будет (бот спросит дату)
    """
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    # Проверяем, есть ли дата в сообщении
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) > 1:
        # Дата передана сразу: /будет 15.10.2026
        date_str = ' '.join(parts[1:])
        await process_date_check(message, state, date_str, employee)
    else:
        # Дата не передана - показываем календарь
        await state.set_state(CheckDayState.waiting_date)
        
        today = datetime.now()
        keyboard = get_calendar_keyboard(today.year, today.month)
        
        await message.answer(
            "📅 <b>Выберите дату для проверки</b>\n\n"
            "<i>Или отправьте дату в любом формате:</i>\n"
            "• 15.10.2026\n"
            "• 2026-10-15\n"
            "• сегодня / завтра\n"
            "• +30 (через 30 дней)\n"
            "• 15 октября 2026\n"
            "• 15.10 (15 октября)\n\n"
            "<i>Можно проверять любые даты, даже через несколько лет!</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

async def process_date_check(message: Message, state: FSMContext, date_str: str, employee: Optional[Dict] = None):
    """Основная функция проверки даты"""
    try:
        user_id = message.from_user.id
        
        if not employee:
            employee = db.get_employee(user_id)
        
        if not employee:
            await message.answer("❌ Вы не зарегистрированы в системе.")
            await state.clear()
            return
        
        # Парсим дату
        target_date = parse_flexible_date(date_str)
        
        if not target_date:
            await message.answer(
                "❌ <b>Не могу понять дату.</b>\n\n"
                "<i>Попробуйте в одном из форматов:</i>\n"
                "• <code>15.10.2026</code>\n"
                "• <code>2026-10-15</code>\n"
                "• <code>сегодня</code> / <code>завтра</code>\n"
                "• <code>+30</code> (через 30 дней)\n"
                "• <code>15.10</code> (15 октября)\n"
                "• <code>15 октября 2026</code>\n\n"
                "<i>Можно проверять любые даты, даже на 10 лет вперёд!</i>",
                parse_mode="HTML"
            )
            return
        
        # Получаем тип дня
        day_type = get_day_type(employee['shift_number'], target_date)
        
        # Проверяем, есть ли уже запись
        existing_record = db.get_record(user_id, target_date)
        
        # Формируем ответ
        response = format_day_check_response(
            employee, target_date, day_type, existing_record
        )
        
        await message.answer(response, parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка проверки даты: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка при проверке даты.</b>\n\n"
            "Попробуйте другую дату или обратитесь к администратору.",
            parse_mode="HTML"
        )
        await state.clear()

@dp.message(CheckDayState.waiting_date)
async def process_check_date_input(message: Message, state: FSMContext):
    """Обработка введённой даты в состоянии ожидания"""
    await process_date_check(message, state, message.text)

@dp.message(Command("исправить"))
async def cmd_correct(message: Message):
    """Удалить последнюю запись"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    records = db.get_last_records(user_id, 5)
    
    if not records:
        await message.answer("📭 У вас нет записей для удаления.")
        return
    
    await message.answer(
        "📝 Выберите запись для удаления:",
        reply_markup=get_last_records_keyboard(records)
    )

@dp.message(Command("отпуски"))
async def cmd_vacations(message: Message):
    """Список отпусков"""
    await show_periods_list(message, "vacation")

@dp.message(Command("больничные"))
async def cmd_sick_list(message: Message):
    """Список больничных"""
    await show_periods_list(message, "sick")

async def show_periods_list(message: Message, period_type: str):
    """Показать список периодов"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    periods = db.get_absence_periods(user_id, period_type)
    
    if not periods:
        type_name = "отпусков" if period_type == "vacation" else "больничных"
        await message.answer(f"📭 У вас нет записей о {type_name}.")
        return
    
    text = "📋 Ваши периоды:\n\n"
    for i, period in enumerate(periods, 1):
        start = datetime.strptime(period['start_date'], "%Y-%m-%d").strftime("%d.%m.%Y")
        end = datetime.strptime(period['end_date'], "%Y-%m-%d").strftime("%d.%m.%Y")
        days = int(period['days'])
        
        type_emoji = "🏖" if period['period_type'] == "vacation" else "🤒"
        text += f"{i}. {type_emoji} {start} - {end} ({days} дн.)\n"
    
    await message.answer(text)

@dp.message(Command("отмена_периода"))
async def cmd_cancel_period(message: Message):
    """Удаление периода"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    periods = db.get_absence_periods(user_id)
    
    if not periods:
        await message.answer("📭 У вас нет периодов для удаления.")
        return
    
    await message.answer(
        "📋 Выберите период для удаления:",
        reply_markup=get_periods_keyboard(periods)
    )

@dp.message(Command("стоимость"))
async def cmd_rates(message: Message, state: FSMContext):
    """Установка стоимости дней"""
    user_id = message.from_user.id
    employee = db.get_employee(user_id)
    
    if not employee:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    await state.set_state(RatesState.waiting_vacation)
    await message.answer(
        f"💰 Текущие ставки:\n"
        f"• Отпуск: {employee['vacation_rate']} ₽/день\n"
        f"• Больничный: {employee['sick_rate']} ₽/день\n\n"
        f"Введите стоимость дня отпуска (в рублях):"
    )

# ============================================
# КОМАНДЫ АДМИНИСТРАТОРА
# ============================================

@dp.message(Command("добавить"))
async def cmd_add_employee(message: Message, state: FSMContext):
    """Добавить нового сотрудника (админ)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов.")
        return
    
    await state.set_state(AddEmployeeState.waiting_user_id)
    await message.answer("Введите ID Telegram нового сотрудника:")

@dp.message(Command("оклад"))
async def cmd_set_salary(message: Message, state: FSMContext):
    """Установить общий оклад (админ)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов.")
        return
    
    current_salary = db.get_monthly_salary()
    await state.set_state(SalaryState.waiting_amount)
    await message.answer(
        f"💰 Текущий оклад: {current_salary:,.0f} ₽\n\n"
        f"Введите новый оклад (в рублях):"
    )

@dp.message(Command("список"))
async def cmd_list_employees(message: Message):
    """Список всех сотрудников (админ)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("❌ Эта команда только для администраторов.")
        return
    
    employees = db.get_all_employees()
    
    if not employees:
        await message.answer("📭 В системе нет сотрудников.")
        return
    
    text = "📋 Список сотрудников:\n\n"
    for i, emp in enumerate(employees, 1):
        text += (
            f"{i}. <b>{emp['full_name']}</b>\n"
            f"   ID: {emp['user_id']} | Смена: {emp['shift_number']}\n"
            f"   Отпуск: {emp['vacation_rate']} ₽/день\n"
            f"   Больничный: {emp['sick_rate']} ₽/день\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")

# ============================================
# ОБРАБОТЧИКИ КНОПОК (CALLBACK)
# ============================================

@dp.callback_query(F.data.startswith("date_"))
async def handle_date_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора даты"""
    action = callback.data
    
    if action == "date_today":
        selected_date = date.today()
    elif action == "date_yesterday":
        selected_date = date.today() - timedelta(days=1)
    elif action == "date_custom":
        today = datetime.now()
        await callback.message.edit_text(
            "📅 Выберите дату:",
            reply_markup=get_calendar_keyboard(today.year, today.month)
        )
        return
    else:
        await callback.answer("Неизвестное действие")
        return
    
    current_state = await state.get_state()
    
    if current_state == ShiftState.waiting_date.state:
        await state.update_data(selected_date=selected_date)
        await state.set_state(ShiftState.waiting_hours)
        await callback.message.edit_text(
            f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Отработали полную смену (12 часов)?",
            reply_markup=get_hours_keyboard()
        )
    else:
        # Обработка отпуска/больничного/за свой счёт/усиления
        data = await state.get_data()
        absence_type = data.get('absence_type')
        
        if absence_type:
            user_id = callback.from_user.id
            
            success = db.add_record(
                user_id=user_id,
                date=selected_date,
                day_type=absence_type,
                hours=12 if absence_type == 'reinforce' else 0
            )
            
            if success:
                type_names = {
                    "vacation": "отпуск",
                    "sick": "больничный",
                    "unpaid": "день за свой счёт",
                    "reinforce": "усиление"
                }
                type_emojis = {
                    "vacation": "🏖",
                    "sick": "🤒", 
                    "unpaid": "🕐",
                    "reinforce": "⚡"
                }
                
                hours_text = " (12ч)" if absence_type == 'reinforce' else ""
                
                await callback.message.edit_text(
                    f"{type_emojis.get(absence_type, '✅')} <b>{type_names[absence_type].capitalize()} отмечен{hours_text}</b>\n\n"
                    f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
                    f"📋 Тип: {type_names[absence_type]}",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text("❌ Ошибка при сохранении записи")
            
            await state.clear()
    
    await callback.answer()

@dp.callback_query(F.data.startswith("calendar_"))
async def handle_calendar_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора даты из календаря"""
    if callback.data == "cancel":
        await callback.message.delete()
        await state.clear()
        return
    
    if callback.data.startswith("calendar_nav_"):
        parts = callback.data.split("_")
        year, month = int(parts[2]), int(parts[3])
        await callback.message.edit_reply_markup(
            reply_markup=get_calendar_keyboard(year, month)
        )
        return
    
    # Выбор конкретной даты
    parts = callback.data.split("_")
    year, month, day = int(parts[1]), int(parts[2]), int(parts[3])
    selected_date = date(year, month, day)
    
    current_state = await state.get_state()
    
    if current_state == ShiftState.waiting_date.state:
        await state.update_data(selected_date=selected_date)
        await state.set_state(ShiftState.waiting_hours)
        
        await callback.message.delete()
        await callback.message.answer(
            f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Отработали полную смену (12 часов)?",
            reply_markup=get_hours_keyboard()
        )
    elif current_state == CheckDayState.waiting_date.state:
        # Для команды /будет
        user_id = callback.from_user.id
        employee = db.get_employee(user_id)
        
        if not employee:
            await callback.message.edit_text("❌ Вы не зарегистрированы.")
            await state.clear()
            return
        
        day_type = get_day_type(employee['shift_number'], selected_date)
        existing_record = db.get_record(user_id, selected_date)
        
        response = format_day_check_response(employee, selected_date, day_type, existing_record)
        
        await callback.message.edit_text(response, parse_mode="HTML")
        await state.clear()
    else:
        # Для отпуска/больничного и т.д.
        data = await state.get_data()
        absence_type = data.get('absence_type')
        
        if absence_type:
            user_id = callback.from_user.id
            
            success = db.add_record(
                user_id=user_id,
                date=selected_date,
                day_type=absence_type,
                hours=12 if absence_type == 'reinforce' else 0
            )
            
            if success:
                type_names = {
                    "vacation": "отпуск",
                    "sick": "больничный",
                    "unpaid": "день за свой счёт",
                    "reinforce": "усиление"
                }
                type_emojis = {
                    "vacation": "🏖",
                    "sick": "🤒", 
                    "unpaid": "🕐",
                    "reinforce": "⚡"
                }
                
                hours_text = " (12ч)" if absence_type == 'reinforce' else ""
                
                await callback.message.edit_text(
                    f"{type_emojis.get(absence_type, '✅')} <b>{type_names[absence_type].capitalize()} отмечен{hours_text}</b>\n\n"
                    f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
                    f"📋 Тип: {type_names[absence_type]}",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text("❌ Ошибка при сохранении записи")
            
            await state.clear()
    
    await callback.answer()

@dp.callback_query(F.data.startswith("hours_"))
async def handle_hours_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора часов"""
    action = callback.data
    
    if action == "hours_12":
        hours = 12.0
    elif action == "hours_custom":
        await callback.message.edit_text(
            "⏰ Введите количество часов (от 0.5 до 12):\n\n"
            "Пример: 8.5"
        )
        return
    else:
        await callback.answer("Неизвестное действие")
        return
    
    data = await state.get_data()
    selected_date = data.get('selected_date')
    
    if not selected_date:
        await callback.message.edit_text("❌ Ошибка: дата не выбрана")
        await state.clear()
        return
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли уже запись
    existing = db.get_record(user_id, selected_date)
    
    if existing:
        # Показываем конфликт
        conflict_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Перезаписать", callback_data=f"overwrite_{selected_date}_{hours}"),
                InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel")
            ]
        ])
        
        await callback.message.edit_text(
            f"⚠️ {selected_date.strftime('%d.%m.%Y')} уже отмечен как: {existing['day_type']}\n"
            f"Что делаем?",
            reply_markup=conflict_keyboard
        )
        return
    
    success = db.add_record(
        user_id=user_id,
        date=selected_date,
        day_type='work',
        hours=hours
    )
    
    if success:
        await callback.message.edit_text(
            f"✅ Смена зафиксирована\n\n"
            f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Часы: {hours}\n"
            f"📋 Тип: Рабочая смена"
        )
    else:
        await callback.message.edit_text("❌ Ошибка при сохранении записи")
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data.startswith("overwrite_"))
async def handle_overwrite(callback: CallbackQuery):
    """Перезаписать существующую запись"""
    data = callback.data.replace("overwrite_", "")
    parts = data.split("_")
    
    if len(parts) >= 3:
        date_str = parts[0]
        hours = float(parts[1])
        
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            user_id = callback.from_user.id
            
            success = db.add_record(
                user_id=user_id,
                date=selected_date,
                day_type='work',
                hours=hours
            )
            
            if success:
                await callback.message.edit_text(
                    f"✅ Смена перезаписана\n\n"
                    f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
                    f"⏰ Часы: {hours}\n"
                    f"📋 Тип: Рабочая смена"
                )
            else:
                await callback.message.edit_text("❌ Ошибка при сохранении записи")
                
        except Exception as e:
            logger.error(f"Ошибка перезаписи: {e}")
            await callback.message.edit_text("❌ Ошибка при перезаписи записи")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_"))
async def handle_delete(callback: CallbackQuery):
    """Удаление записи"""
    if callback.data == "cancel":
        await callback.message.delete()
        return
    
    if callback.data.startswith("delete_period_"):
        period_id = int(callback.data.split("_")[2])
        success = db.delete_absence_period(period_id)
        
        if success:
            await callback.message.edit_text("✅ Период удалён")
        else:
            await callback.message.edit_text("❌ Ошибка при удалении периода")
        return
    
    record_id = int(callback.data.split("_")[1])
    success = db.delete_record(record_id)
    
    if success:
        await callback.message.edit_text("✅ Запись удалена")
    else:
        await callback.message.edit_text("❌ Ошибка при удалении записи")
    
    await callback.answer()

# ============================================
# ОБРАБОТЧИКИ ТЕКСТОВОГО ВВОДА (с правильным приоритетом)
# ============================================

@dp.message(AddEmployeeState.waiting_user_id)
async def process_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя при добавлении сотрудника"""
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await state.set_state(AddEmployeeState.waiting_full_name)
        await message.answer("Введите ФИО сотрудника:")
    except ValueError:
        await message.answer("❌ Введите корректный ID (только цифры)")

@dp.message(AddEmployeeState.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Обработка ФИО при добавлении сотрудника"""
    full_name = message.text.strip()
    
    if len(full_name) < 3:
        await message.answer("❌ Введите полное ФИО (минимум 3 символа)")
        return
    
    await state.update_data(full_name=full_name)
    await state.set_state(AddEmployeeState.waiting_shift)
    
    await message.answer(
        "Выберите номер смены:",
        reply_markup=get_shift_numbers_keyboard()
    )

@dp.callback_query(F.data.startswith("shift_"), AddEmployeeState.waiting_shift)
async def process_shift_number(callback: CallbackQuery, state: FSMContext):
    """Обработка номера смены при добавлении сотрудника"""
    shift_number = callback.data.split("_")[1]
    
    data = await state.get_data()
    user_id = data.get('user_id')
    full_name = data.get('full_name')
    
    if not all([user_id, full_name, shift_number]):
        await callback.message.edit_text("❌ Ошибка: не все данные")
        await state.clear()
        return
    
    success = db.add_employee(user_id, full_name, shift_number)
    
    if success:
        await callback.message.edit_text(
            f"✅ Сотрудник добавлен:\n\n"
            f"• ID: {user_id}\n"
            f"• ФИО: {full_name}\n"
            f"• Смена: {shift_number}"
        )
    else:
        await callback.message.edit_text(
            f"❌ Не удалось добавить сотрудника\n"
            f"Возможно, он уже зарегистрирован."
        )
    
    await state.clear()
    await callback.answer()

@dp.message(SalaryState.waiting_amount)
async def process_salary(message: Message, state: FSMContext):
    """Обработка ввода оклада"""
    try:
        salary = int(message.text.replace(" ", "").replace(",", ""))
        
        if salary <= 0:
            await message.answer("❌ Введите положительное число")
            return
        
        success = db.update_monthly_salary(salary)
        
        if success:
            await message.answer(f"✅ Оклад установлен: {salary:,.0f} ₽")
        else:
            await message.answer("❌ Ошибка при обновлении оклада")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число (только цифры)")

@dp.message(RatesState.waiting_vacation)
async def process_vacation_rate(message: Message, state: FSMContext):
    """Обработка ввода стоимости отпуска"""
    try:
        vacation_rate = int(message.text.replace(" ", "").replace(",", ""))
        
        if vacation_rate < 0:
            await message.answer("❌ Введите неотрицательное число")
            return
        
        await state.update_data(vacation_rate=vacation_rate)
        await state.set_state(RatesState.waiting_sick)
        
        await message.answer("Введите стоимость дня больничного (в рублях):")
    except ValueError:
        await message.answer("❌ Введите корректное число (только цифры)")

@dp.message(RatesState.waiting_sick)
async def process_sick_rate(message: Message, state: FSMContext):
    """Обработка ввода стоимости больничного"""
    try:
        sick_rate = int(message.text.replace(" ", "").replace(",", ""))
        
        if sick_rate < 0:
            await message.answer("❌ Введите неотрицательное число")
            return
        
        data = await state.get_data()
        vacation_rate = data.get('vacation_rate')
        user_id = message.from_user.id
        
        success = db.update_employee_rates(
            user_id=user_id,
            vacation_rate=vacation_rate,
            sick_rate=sick_rate
        )
        
        if success:
            await message.answer(
                f"✅ Ставки обновлены:\n\n"
                f"• Отпуск: {vacation_rate:,.0f} ₽/день\n"
                f"• Больничный: {sick_rate:,.0f} ₽/день"
            )
        else:
            await message.answer("❌ Ошибка при обновлении ставок")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число (только цифры)")

# ============================================
# ОБРАБОТЧИК КАСТОМНЫХ ЧАСОВ (должен быть ПОСЛЕДНИМ!)
# ============================================

@dp.message(F.text.regexp(r'^\d+(\.\d+)?$'))
async def process_custom_hours(message: Message, state: FSMContext):
    """Обработка ввода кастомных часов для смены - ТОЛЬКО в состоянии waiting_hours"""
    current_state = await state.get_state()
    
    # Работает ТОЛЬКО когда мы в состоянии ожидания часов
    if current_state != ShiftState.waiting_hours.state:
        return  # Пропускаем, если не в нужном состоянии
    
    try:
        hours = float(message.text.replace(",", "."))
        
        if hours < 0.5 or hours > 12:
            await message.answer("❌ Введите от 0.5 до 12 часов")
            return
        
        data = await state.get_data()
        selected_date = data.get('selected_date')
        
        if not selected_date:
            await message.answer("❌ Ошибка: дата не выбрана")
            await state.clear()
            return
        
        user_id = message.from_user.id
        
        success = db.add_record(
            user_id=user_id,
            date=selected_date,
            day_type='work',
            hours=hours
        )
        
        if success:
            await message.answer(
                f"✅ Смена зафиксирована\n\n"
                f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
                f"⏰ Часы: {hours}\n"
                f"📋 Тип: Рабочая смена"
            )
        else:
            await message.answer("❌ Ошибка при сохранении записи")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число (например: 8.5)")
# ============================================
# ERROR HANDLER
# ============================================

@dp.error()
async def error_handler(event, **kwargs):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка: {event}", exc_info=True)

# ============================================
# MAIN FUNCTION
# ============================================

async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск бота ShiftTracker...")
    
    if not BOT_TOKEN:
        logger.error("Не указан BOT_TOKEN в .env файле!")
        return
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())