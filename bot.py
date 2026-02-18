# bot.py - основной файл бота
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)
import pytz
from config import BOT_TOKEN, ADMIN_CHAT_ID, SUPPLIERS
from database import create_tables, save_order, get_all_products, add_write_off
from utils import (
    calculate_order_recommendations, format_order_message,
    apply_min_order_constraints, forecast_demand
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

create_tables()
user_orders = {}


async def check_deadlines(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(pytz.timezone('Europe/Moscow')).time()
    today = datetime.now().date()
    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"][today.weekday()]
    
    for supplier, info in SUPPLIERS.items():
        if weekday_ru not in info.get('delivery_days', []):
            continue
        deadline = info['deadline']
        reminder_time = (datetime.combine(today, deadline) - timedelta(minutes=10)).time()
        if now.hour == reminder_time.hour and now.minute == reminder_time.minute:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⏰ Напоминание: через 10 минут дедлайн заказа для {supplier} ({deadline.strftime('%H:%M')})!"
            )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ['📋 Рекомендации', '📝 Списания'],
        ['📤 Сформировать заказы', '⏰ Расписание'],
        ['🆘 Помощь']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.effective_message.reply_text(
        "👋 Привет! Я бот для закупок магазина.\n"
        "Я помогу рассчитать оптимальные заказы на основе продаж и списаний.\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recommendations = calculate_order_recommendations()
    if not recommendations:
        await update.effective_message.reply_text("На сегодня нет рекомендаций. Возможно, недостаточно данных.")
        return

    context.user_data['recommendations'] = recommendations

    text = "📋 <b>РЕКОМЕНДАЦИИ ПО ЗАКАЗАМ НА СЕГОДНЯ</b>\n\n"
    for supplier, items in recommendations.items():
        text += f"<b>{supplier}:</b>\n"
        for product, qty in items.items():
            text += f"  • {product}: {qty} шт.\n"
        text += "\n"

    keyboard = [
        [InlineKeyboardButton("📤 Сформировать заказы", callback_data="create_orders")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="edit_orders")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_html(text, reply_markup=reply_markup)

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today_weekday = datetime.now().weekday()
    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"][today_weekday]
    text = "⏰ <b>РАСПИСАНИЕ ПОСТАВЩИКОВ НА СЕГОДНЯ</b>\n\n"
    for supplier, info in SUPPLIERS.items():
        if weekday_ru in info.get('delivery_days', []):
            deadline = info['deadline'].strftime('%H:%M')
            text += f"✅ <b>{supplier}</b> – заказ до {deadline}\n"
        else:
            text += f"❌ <b>{supplier}</b> – сегодня нет поставки\n"
    await update.effective_message.reply_html(text)

async def create_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recommendations = context.user_data.get('recommendations')
    if not recommendations:
        await update.effective_message.reply_text("Сначала получите рекомендации через /recommend или кнопку '📋 Рекомендации'.")
        return

    user_id = update.effective_user.id
    user_orders[user_id] = recommendations

    for supplier, items in recommendations.items():
        if items:
            msg = format_order_message(supplier, items)
            await update.effective_message.reply_html(msg)

    await update.effective_message.reply_text("✅ Заказы сформированы. Вы можете отредактировать их через кнопку '✏️ Редактировать'.")

async def edit_orders_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"edit_orders_start called by user {user_id}")

    if user_id not in user_orders or not user_orders[user_id]:
        await update.effective_message.reply_text("У вас нет активных заказов. Сначала сформируйте их через '📤 Сформировать заказы'.")
        return

    context.user_data['editing'] = True
    await update.effective_message.reply_text(
        "✏️ <b>РЕЖИМ РЕДАКТИРОВАНИЯ</b>\n\n"
        "Вводите изменения в формате:\n"
        "<code>Поставщик: Товар = новое количество</code>\n"
        "Например: <code>Pigeon: Пшеничный хлеб = 15</code>\n"
        "Чтобы удалить товар, укажите 0.\n"
        "Для завершения отправьте /done",
        parse_mode='HTML'
    )

async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing'):
        return

    text = update.message.text.strip()
    if text == '/done':
        context.user_data['editing'] = False
        await update.message.reply_text("Редактирование завершено.")
        return

    try:
        if ':' not in text or '=' not in text:
            raise ValueError("Неверный формат")
        supplier_part, rest = text.split(':', 1)
        supplier = supplier_part.strip()
        product_part, qty_part = rest.split('=', 1)
        product = product_part.strip()
        qty = int(qty_part.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат. Используйте: Поставщик: Товар = количество")
        return

    user_id = update.effective_user.id
    if user_id not in user_orders:
        await update.message.reply_text("Сначала сформируйте заказы.")
        return

    if supplier not in user_orders[user_id]:
        await update.message.reply_text(f"Поставщик {supplier} не найден в ваших заказах.")
        return

    if product not in user_orders[user_id][supplier]:
        await update.message.reply_text(f"Товар {product} не найден в заказе {supplier}.")
        return

    user_orders[user_id][supplier][product] = qty
    if qty == 0:
        del user_orders[user_id][supplier][product]

    await update.message.reply_text(f"✅ Обновлено: {supplier} – {product} = {qty} шт.")

    if not user_orders[user_id][supplier]:
        del user_orders[user_id][supplier]

    if supplier in user_orders[user_id]:
        msg = format_order_message(supplier, user_orders[user_id][supplier])
        await update.message.reply_html(msg)
    else:
        await update.message.reply_text(f"Заказ для {supplier} пуст (удалён).")


async def writeoff_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"writeoff_start called by user {update.effective_user.id}")
    await update.effective_message.reply_text(
        "Введите списание в формате: Товар = количество\n"
        "Например: Пшеничный хлеб = 2\n"
        "Для отмены отправьте /cancel"
    )
    context.user_data['awaiting_writeoff'] = True
    logger.info(f"awaiting_writeoff set to True for user {update.effective_user.id}")

async def handle_writeoff_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"handle_writeoff_input called by user {update.effective_user.id}")
    if not context.user_data.get('awaiting_writeoff'):
        logger.info("not awaiting writeoff, returning")
        return
    text = update.message.text.strip()
    logger.info(f"received text: {text}")
    if text == '/cancel':
        context.user_data['awaiting_writeoff'] = False
        await update.message.reply_text("Отменено.")
        logger.info("cancelled")
        return
    try:
        if '=' not in text:
            raise ValueError("Нет знака =")
        product, qty = text.split('=', 1)
        product = product.strip()
        qty = float(qty.strip())
        logger.info(f"parsed: product={product}, qty={qty}")
        if add_write_off(product, qty):
            await update.message.reply_text(f"✅ Списание {product} = {qty} шт. записано.")
            logger.info("write-off added successfully")
        else:
            await update.message.reply_text("❌ Товар не найден. Проверьте название.")
            logger.info("product not found")
    except Exception as e:
        logger.error(f"error parsing: {e}")
        await update.message.reply_text("Неверный формат. Используйте: Товар = количество")
    context.user_data['awaiting_writeoff'] = False
    logger.info("awaiting_writeoff reset to False")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🆘 <b>Помощь по командам</b>

📋 <b>Рекомендации</b> – показывает, сколько и чего заказать сегодня.
📝 <b>Списания</b> – вручную добавить списание товара.
📤 <b>Сформировать заказы</b> – создаёт готовые сообщения для поставщиков.
✏️ <b>Редактировать</b> – изменяет количество в заказах.
⏰ <b>Расписание</b> – когда нужно заказывать у поставщиков.
🆘 <b>Помощь</b> – эта справка.

<b>Редактирование заказов:</b>
<code>Поставщик: Товар = новое количество</code>
Например: <code>Pigeon: Пшеничный хлеб = 15</code>
Чтобы завершить редактирование, отправьте /done

<b>Запись списания:</b>
<code>Товар = количество</code>
Например: <code>Пшеничный хлеб = 2</code>
"""
    await update.effective_message.reply_html(help_text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "create_orders":
        recommendations = context.user_data.get('recommendations')
        if not recommendations:
            await query.edit_message_text("Сначала получите рекомендации через /recommend")
            return
        user_id = update.effective_user.id
        user_orders[user_id] = recommendations
        for supplier, items in recommendations.items():
            if items:
                msg = format_order_message(supplier, items)
                await query.message.reply_html(msg)
        await query.edit_message_text("✅ Заказы сформированы.")
    elif query.data == "edit_orders":
        await edit_orders_start(update, context)


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"handle_text_input called by user {update.effective_user.id}")
    if context.user_data.get('editing'):
        logger.info("routing to handle_edit")
        await handle_edit(update, context)
    elif context.user_data.get('awaiting_writeoff'):
        logger.info("routing to handle_writeoff_input")
        await handle_writeoff_input(update, context)
    else:
        logger.info("no active state, ignoring")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("recommend", recommend))

    
    app.add_handler(MessageHandler(filters.Text("📋 Рекомендации"), recommend))
    app.add_handler(MessageHandler(filters.Text("📝 Списания"), writeoff_start))
    app.add_handler(MessageHandler(filters.Text("📤 Сформировать заказы"), create_orders))
    app.add_handler(MessageHandler(filters.Text("✏️ Редактировать"), edit_orders_start))
    app.add_handler(MessageHandler(filters.Text("⏰ Расписание"), schedule))
    app.add_handler(MessageHandler(filters.Text("🆘 Помощь"), help_command))

    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    
    app.add_handler(CallbackQueryHandler(button_handler))

    
    job_queue = app.job_queue
    job_queue.run_repeating(check_deadlines, interval=60, first=10)

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()