import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from database import db

logger = logging.getLogger(__name__)

def get_day_type(shift_number: str, date_obj: date) -> str:
    """
    Определяет тип дня для сотрудника на указанную дату
    """
    CYCLE = ['day', 'night', 'rest', 'off']
    START_DATE = date(2024, 10, 1)
    
    days_diff = (date_obj - START_DATE).days
    shift_index = int(shift_number) - 1
    cycle_position = (days_diff + shift_index) % 4
    
    return CYCLE[cycle_position]

def calculate_planned_days(shift_number: str, year: int, month: int) -> int:
    """
    Считает сколько рабочих дней (день+ночь) у сотрудника в месяце
    """
    work_days = 0
    current = date(year, month, 1)
    
    # Определяем последний день месяца
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # Считаем рабочие дни
    while current <= last_day:
        day_type = get_day_type(shift_number, current)
        if day_type in ['day', 'night']:
            work_days += 1
        current += timedelta(days=1)
    
    return work_days

def calculate_month_stats(user_id: int, year: int, month: int) -> Optional[Dict[str, Any]]:
    """
    Основная функция расчёта статистики за месяц
    """
    try:
        # Получаем данные пользователя
        user = db.get_employee(user_id)
        if not user:
            return None
        
        # Получаем все записи за месяц
        records = db.get_records_for_month(user_id, year, month)
        
        # Считаем плановые дни по графику
        planned_days = calculate_planned_days(user['shift_number'], year, month)
        planned_hours = planned_days * 12
        
        # Считаем фактические данные
        work_hours = 0
        work_days = 0
        reinforce_hours = 0
        reinforce_days = 0
        vacation_days = 0
        sick_days = 0
        unpaid_days = 0
        
        for record in records:
            if record['day_type'] == 'work':
                work_hours += record['hours']
                work_days += 1 if record['hours'] > 0 else 0
            elif record['day_type'] == 'reinforce':
                reinforce_hours += record['hours']
                reinforce_days += 1 if record['hours'] > 0 else 0
            elif record['day_type'] == 'vacation':
                vacation_days += 1
            elif record['day_type'] == 'sick':
                sick_days += 1
            elif record['day_type'] == 'unpaid':
                unpaid_days += 1
        
        total_work_hours = work_hours + reinforce_hours
        
        # Получаем оклад
        salary = db.get_monthly_salary()
        hour_rate = salary / planned_hours if planned_hours > 0 else 0
        
        # Расчёт
        hours_diff = total_work_hours - planned_hours
        hours_adjustment = hours_diff * hour_rate
        
        vacation_pay = vacation_days * user['vacation_rate']
        sick_pay = sick_days * user['sick_rate']
        
        total = salary + hours_adjustment + vacation_pay + sick_pay
        
        return {
            'planned_days': planned_days,
            'planned_hours': planned_hours,
            'work_days': work_days,
            'work_hours': work_hours,
            'reinforce_days': reinforce_days,
            'reinforce_hours': reinforce_hours,
            'total_work_hours': total_work_hours,
            'vacation_days': vacation_days,
            'sick_days': sick_days,
            'unpaid_days': unpaid_days,
            'salary': salary,
            'hour_rate': round(hour_rate, 2),
            'hours_adjustment': round(hours_adjustment, 2),
            'vacation_pay': vacation_pay,
            'sick_pay': sick_pay,
            'total': round(total, 2),
            'vacation_rate': user['vacation_rate'],
            'sick_rate': user['sick_rate']
        }
        
    except Exception as e:
        logger.error(f"Ошибка расчёта статистики: {e}")
        return None

def format_month_stats(stats: Dict[str, Any]) -> str:
    """
    Форматирование статистики в красивый текст
    """
    if not stats:
        return "❌ Не удалось рассчитать статистику"
    
    month_name = datetime(stats.get('year', 2024), stats.get('month', 1), 1).strftime("%B %Y")
    
    text = f"📊 {month_name} | Смена #{stats.get('shift_number', '?')}\n"
    text += "─" * 30 + "\n\n"
    
    text += f"📅 По графику: {stats['planned_days']} рабочих дней ({stats['planned_hours']}ч)\n\n"
    
    text += "✅ Фактически отработано:\n"
    if stats['work_days'] > 0:
        text += f"• Смен по графику: {stats['work_days']} × 12ч = {stats['work_hours']}ч\n"
    if stats['reinforce_days'] > 0:
        text += f"• Усиления: {stats['reinforce_days']} × 12ч = {stats['reinforce_hours']}ч\n"
    text += f"• Всего часов: {stats['total_work_hours']}ч\n\n"
    
    # Отсутствия
    absences = []
    if stats['vacation_days'] > 0:
        absences.append(f"Отпуск: {stats['vacation_days']} дней")
    if stats['sick_days'] > 0:
        absences.append(f"Больничный: {stats['sick_days']} дней")
    if stats['unpaid_days'] > 0:
        absences.append(f"За свой счёт: {stats['unpaid_days']} дней")
    
    if absences:
        text += "📋 Отсутствия:\n"
        for absence in absences:
            text += f"• {absence}\n"
        text += "\n"
    
    # Расчёт
    text += "💰 Примерный расчёт:\n"
    text += f"Оклад: {stats['salary']:,.0f} ₽\n".replace(',', ' ')
    
    if stats['hours_adjustment'] != 0:
        sign = "+" if stats['hours_adjustment'] > 0 else ""
        text += f"Корректировка за часы: {sign}{stats['hours_adjustment']:,.0f} ₽\n".replace(',', ' ')
    
    if stats['vacation_pay'] > 0:
        text += f"+ Отпуск ({stats['vacation_rate']} ₽/день): {stats['vacation_pay']:,.0f} ₽\n".replace(',', ' ')
    
    if stats['sick_pay'] > 0:
        text += f"+ Больничный ({stats['sick_rate']} ₽/день): {stats['sick_pay']:,.0f} ₽\n".replace(',', ' ')
    
    text += "─" * 30 + "\n"
    text += f"💵 ИТОГО: ~{stats['total']:,.0f} ₽\n\n".replace(',', ' ')
    
    text += "⚠️ Внимание: Это примерный расчёт!\n"
    text += "Официальный расчёт делает бухгалтерия."
    
    return text

def get_month_schedule(user_id: int, year: int, month: int) -> List[Dict[str, Any]]:
    """
    Получение графика на месяц
    """
    try:
        user = db.get_employee(user_id)
        if not user:
            return []
        
        schedule = []
        current = date(year, month, 1)
        
        # Определяем последний день месяца
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        while current <= last_day:
            day_type = get_day_type(user['shift_number'], current)
            record = db.get_record(user_id, current)
            
            schedule.append({
                'date': current,
                'day_type': day_type,
                'record': record
            })
            
            current += timedelta(days=1)
        
        return schedule
        
    except Exception as e:
        logger.error(f"Ошибка получения графика: {e}")
        return []

def format_month_schedule(schedule: List[Dict[str, Any]]) -> str:
    """
    Форматирование графика в текст
    """
    if not schedule:
        return "❌ Не удалось получить график"
    
    first_date = schedule[0]['date']
    month_name = first_date.strftime("%B %Y")
    
    text = f"📅 {month_name} | Ваш график\n"
    text += "─" * 30 + "\n\n"
    
    for day in schedule:
        date_str = day['date'].strftime("%d.%m")
        weekday = day['date'].strftime("%a")
        
        emoji_map = {
            'day': '🌞',
            'night': '🌙',
            'rest': '😴',
            'off': '🏠'
        }
        
        emoji = emoji_map.get(day['day_type'], '❓')
        day_type_ru = {
            'day': 'ДЕНЬ',
            'night': 'НОЧЬ',
            'rest': 'Отсыпной',
            'off': 'Выходной'
        }.get(day['day_type'], '?')
        
        status = ""
        if day['record']:
            if day['record']['day_type'] == 'work':
                status = f"✅ ({day['record']['hours']}ч)"
            elif day['record']['day_type'] == 'reinforce':
                status = f"⚡ ({day['record']['hours']}ч)"
            elif day['record']['day_type'] == 'vacation':
                status = "🏖"
            elif day['record']['day_type'] == 'sick':
                status = "🤒"
            elif day['record']['day_type'] == 'unpaid':
                status = "🕐"
        
        text += f"{weekday} {date_str} | {emoji} {day_type_ru} {status}\n"
    
    return text

def get_simple_schedule(user_id: int, year: int, month: int) -> str:
    """
    Простой график на месяц (альтернативная версия)
    """
    try:
        user = db.get_employee(user_id)
        if not user:
            return "❌ Пользователь не найден"
        
        today = date.today()
        current = date(year, month, 1)
        
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        month_name = current.strftime("%B %Y")
        result = f"📅 {month_name} | Смена {user['shift_number']}\n"
        result += "─" * 30 + "\n\n"
        
        # Только 2 недели для краткости
        days_to_show = min(14, (last_day - current).days + 1)
        
        for i in range(days_to_show):
            day_date = current + timedelta(days=i)
            day_type = get_day_type(user['shift_number'], day_date)
            
            # Эмодзи
            emoji = {
                'day': '🌞',
                'night': '🌙', 
                'rest': '😴',
                'off': '🏠'
            }.get(day_type, '❓')
            
            # Русские названия
            type_ru = {
                'day': 'День',
                'night': 'Ночь',
                'rest': 'Отсыпной',
                'off': 'Выходной'
            }.get(day_type, '?')
            
            # Дата
            date_str = day_date.strftime("%d.%m")
            weekday = day_date.strftime("%a")
            
            # Проверяем, сегодня ли это
            is_today = day_date == today
            today_mark = " 🎯" if is_today else ""
            
            result += f"{weekday} {date_str}{today_mark}: {emoji} {type_ru}\n"
            
            # Каждые 7 дней добавляем разделитель
            if (i + 1) % 7 == 0:
                result += "\n"
        
        if days_to_show < (last_day - current).days + 1:
            result += f"\n... и ещё {(last_day - current).days + 1 - days_to_show} дней"
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка простого графика: {e}")
        return "❌ Ошибка при получении графика"