# utils.py - вспомогательные функции (прогноз, форматирование, праздники)
from datetime import datetime, timedelta
import holidays
from database import get_sales_history, get_write_offs_history, get_current_stock, get_all_products
from config import SUPPLIERS, HOLIDAYS, STORE_NAME, STORE_PHONE, STORE_CONTACT_PERSON


ru_holidays = holidays.Russia()

def is_holiday(date):
    
    if date in ru_holidays:
        return True
    
    if date.strftime('%m-%d') in HOLIDAYS:
        return True
    return False

def forecast_demand(product_name, target_date=None):
    
    if target_date is None:
        target_date = datetime.now().date()

   
    sales = get_sales_history(product_name, days=30)
    if not sales:
        return 0.0  

   
    sales_dict = {}
    for d_str, qty in sales:
        d = datetime.strptime(d_str, '%Y-%m-%d').date()
        sales_dict[d] = qty

    
    target_weekday = target_date.weekday()
    same_weekday_qty = []
    for d, qty in sales_dict.items():
        if d.weekday() == target_weekday:
            same_weekday_qty.append(qty)

    if same_weekday_qty:
        avg_sales = sum(same_weekday_qty) / len(same_weekday_qty)
    else:
       
        avg_sales = sum(sales_dict.values()) / len(sales_dict)

    
    if is_holiday(target_date):
        avg_sales *= 1.5   

    
    write_offs = get_write_offs_history(product_name, days=30)
    if write_offs:
        wo_dict = {}
        for d_str, qty in write_offs:
            d = datetime.strptime(d_str, '%Y-%m-%d').date()
            wo_dict[d] = qty
        same_weekday_wo = [qty for d, qty in wo_dict.items() if d.weekday() == target_weekday]
        if same_weekday_wo:
            avg_wo = sum(same_weekday_wo) / len(same_weekday_wo)
        else:
            avg_wo = sum(wo_dict.values()) / len(wo_dict) if wo_dict else 0
        avg_sales += avg_wo   

    return round(avg_sales, 1)

def calculate_order_recommendations(target_date=None):
    
    if target_date is None:
        target_date = datetime.now().date()

    recommendations = {}
    products = get_all_products()   

    for name, supplier, min_stock, par_level, price in products:
        forecast = forecast_demand(name, target_date)
        current = get_current_stock(name)

        
        if current < min_stock:
            needed = par_level - current + forecast
        else:
            needed = forecast - current
            if needed < 0:
                needed = 0

       
        recommended = int(needed)  
        if recommended < 0:
            recommended = 0

        if recommended > 0:
            if supplier not in recommendations:
                recommendations[supplier] = {}
            recommendations[supplier][name] = recommended

    return recommendations

def apply_min_order_constraints(recommendations):
   
    warnings = []
    for supplier, items in list(recommendations.items()):
        info = SUPPLIERS.get(supplier)
        if not info:
            continue

       
        min_items = info.get('min_order_items', 0)
        if len(items) < min_items:
            warnings.append(f"У {supplier} мало позиций ({len(items)} из {min_items})")

       
        total_amount = 0
        

    return recommendations, warnings

def format_order_message(supplier, items):
    
    info = SUPPLIERS.get(supplier, {})
    lines = []
    lines.append(f"📦 <b>ЗАКАЗ ДЛЯ {supplier}</b>")
    lines.append(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}")
    lines.append(f"🏪 Магазин: {STORE_NAME}")
    lines.append(f"📞 Телефон: {STORE_PHONE}")
    lines.append(f"👤 Контакт: {STORE_CONTACT_PERSON}")
    lines.append("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")

    total_qty = 0
    for product, qty in items.items():
        lines.append(f"• {product}: <b>{qty} шт.</b>")
        total_qty += qty

    lines.append(f"\n<b>ИТОГО: {total_qty} шт.</b>")
    lines.append("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")

    if info:
        lines.append(f"📞 Телефон поставщика: {info.get('phone', 'не указан')}")
        lines.append(f"👤 Менеджер: {info.get('contact_person', 'не указан')}")
        lines.append(f"⏰ Дедлайн: {info['deadline'].strftime('%H:%M')}")
        lines.append(f"📝 Примечание: {info.get('notes', '')}")

    lines.append("\n<i>Вы можете отредактировать заказ, отправив сообщение в формате:</i>")
    lines.append("<code>Поставщик: Товар = новое количество</code>")
    return "\n".join(lines)