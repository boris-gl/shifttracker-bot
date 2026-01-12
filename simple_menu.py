from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_simple_menu(is_admin: bool = False):
    """Простое меню, которое точно работает"""
    
    # Базовые кнопки для всех
    buttons = [
        [KeyboardButton(text="📅 Смена"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📋 График"), KeyboardButton(text="🔍 Будет")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="🤒 Больничный")],
        [KeyboardButton(text="✏️ Исправить"), KeyboardButton(text="💰 Стоимость")],
    ]
    
    # Добавляем кнопки администратора
    if is_admin:
        buttons.append([
            KeyboardButton(text="👥 Добавить"),
            KeyboardButton(text="💰 Оклад"),
            KeyboardButton(text="📋 Список")
        ])
    
    # Создаем клавиатуру
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Нажмите кнопку или введите команду..."
    )