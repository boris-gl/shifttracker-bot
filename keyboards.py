from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import datetime, date, timedelta

def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="/смена"))
    builder.add(KeyboardButton(text="/статистика"))
    builder.add(KeyboardButton(text="/график"))
    
    builder.row()
    builder.add(KeyboardButton(text="/отпуск"))
    builder.add(KeyboardButton(text="/больничный"))
    builder.add(KeyboardButton(text="/за_счет"))
    
    builder.row()
    builder.add(KeyboardButton(text="/отпуск_период"))
    builder.add(KeyboardButton(text="/больничный_период"))
    
    builder.row()
    builder.add(KeyboardButton(text="/исправить"))
    builder.add(KeyboardButton(text="/стоимость"))
    
    if is_admin:
        builder.row()
        builder.add(KeyboardButton(text="/добавить"))
        builder.add(KeyboardButton(text="/оклад"))
        builder.add(KeyboardButton(text="/список"))
    
    builder.adjust(3, 3, 2, 2, 3)
    return builder.as_markup(resize_keyboard=True)

def get_date_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    builder.add(InlineKeyboardButton(
        text=f"Сегодня ({today.strftime('%d.%m')})",
        callback_data=f"date_today"
    ))
    builder.add(InlineKeyboardButton(
        text=f"Вчера ({yesterday.strftime('%d.%m')})",
        callback_data=f"date_yesterday"
    ))
    builder.add(InlineKeyboardButton(
        text="📅 Выбрать дату",
        callback_data="date_custom"
    ))
    
    builder.adjust(2, 1)
    return builder.as_markup()

def get_hours_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Полная смена (12ч)",
        callback_data="hours_12"
    ))
    builder.add(InlineKeyboardButton(
        text="🕐 Неполная смена",
        callback_data="hours_custom"
    ))
    
    builder.adjust(1)
    return builder.as_markup()

def get_absence_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🏖 Отпуск",
        callback_data="type_vacation"
    ))
    builder.add(InlineKeyboardButton(
        text="🤒 Больничный",
        callback_data="type_sick"
    ))
    builder.add(InlineKeyboardButton(
        text="🕐 За свой счёт",
        callback_data="type_unpaid"
    ))
    
    builder.adjust(2, 1)
    return builder.as_markup()

def get_period_length_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="3 дня", callback_data="period_3"))
    builder.add(InlineKeyboardButton(text="Неделя", callback_data="period_7"))
    builder.add(InlineKeyboardButton(text="2 недели", callback_data="period_14"))
    builder.add(InlineKeyboardButton(text="Месяц", callback_data="period_30"))
    builder.add(InlineKeyboardButton(text="📅 Произвольные даты", callback_data="period_custom"))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_conflict_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="✅ Перезаписать", callback_data="resolve_overwrite"))
    builder.add(InlineKeyboardButton(text="📅 Изменить даты", callback_data="resolve_change"))
    builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="resolve_cancel"))
    
    builder.adjust(2, 1)
    return builder.as_markup()

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="✅ Да, всё верно", callback_data="confirm_yes"))
    builder.add(InlineKeyboardButton(text="❌ Нет, изменить", callback_data="confirm_no"))
    
    builder.adjust(2)
    return builder.as_markup()

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    
    builder.adjust(1)
    return builder.as_markup()

def get_shift_numbers_keyboard() -> InlineKeyboardMarkup:
    """Выбор номера смены"""
    builder = InlineKeyboardBuilder()
    
    for i in range(1, 5):
        builder.add(InlineKeyboardButton(text=f"Смена {i}", callback_data=f"shift_{i}"))
    
    builder.adjust(2, 2)
    return builder.as_markup()

def get_last_records_keyboard(records: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for i, record in enumerate(records, 1):
        date_str = datetime.strptime(record['date'], "%Y-%m-%d").strftime("%d.%m")
        builder.add(InlineKeyboardButton(
            text=f"{i}. {date_str} - {record['day_type']}",
            callback_data=f"delete_{record['id']}"
        ))
    
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    builder.adjust(1)
    return builder.as_markup()

def get_periods_keyboard(periods: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for i, period in enumerate(periods, 1):
        start = datetime.strptime(period['start_date'], "%Y-%m-%d").strftime("%d.%m")
        end = datetime.strptime(period['end_date'], "%Y-%m-%d").strftime("%d.%m")
        builder.add(InlineKeyboardButton(
            text=f"{i}. {period['period_type']}: {start}-{end}",
            callback_data=f"delete_period_{period['id']}"
        ))
    
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    builder.adjust(1)
    return builder.as_markup()

def get_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    month_name = datetime(year, month, 1).strftime("%B %Y")
    builder.add(InlineKeyboardButton(text=month_name, callback_data="ignore"))
    builder.row()
    
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in weekdays:
        builder.add(InlineKeyboardButton(text=day, callback_data="ignore"))
    builder.row()
    
    first_day = date(year, month, 1)
    last_day = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
    
    weekday_offset = first_day.weekday()
    for _ in range(weekday_offset):
        builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))
    
    current = first_day
    while current <= last_day:
        builder.add(InlineKeyboardButton(
            text=str(current.day),
            callback_data=f"calendar_{current.year}_{current.month}_{current.day}"
        ))
        current += timedelta(days=1)
        
        if current.weekday() == 0 and current <= last_day:
            builder.row()
    
    builder.row()
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    builder.add(InlineKeyboardButton(
        text="◀️",
        callback_data=f"calendar_nav_{prev_year}_{prev_month}"
    ))
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    builder.add(InlineKeyboardButton(
        text="▶️",
        callback_data=f"calendar_nav_{next_year}_{next_month}"
    ))
    
    builder.adjust(7, 7, *[7] * ((last_day.day + weekday_offset) // 7 + 1), 3)
    
    return builder.as_markup()
