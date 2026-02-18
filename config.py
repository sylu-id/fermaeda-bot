# config.py - настройки бота
import os
from datetime import time
DATABASE_PATH = os.path.join("data", "procurement.db")


BOT_TOKEN = "7665250970:AAEPhxBpT-iA-nyaPghpqvfMzczzKSlA7Hw"          
ADMIN_CHAT_ID =  704043591                      


STORE_NAME = "Ферма Еда"
STORE_PHONE = "+7 904 765-33-95"
STORE_CONTACT_PERSON = "Сотрудник"


SUPPLIERS = {
    "Pigeon": {
        "phone": "+7 900 345-66-77",
        "contact_person": "Менеджер Pigeon",
        "deadline": time(15, 0),          
        "min_order_amount": 500,           
        "min_order_items": 5,               
        "delivery_days": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
        "notes": "Заказ до 15:00"
    },
    "Пестречинка": {
        "phone": "+7 917 003-67-55",
        "contact_person": "Менеджер Пестречинки",
        "deadline": time(17, 0),
        "min_order_amount": 1000,
        "min_order_items": 3,
        "delivery_days": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
        "notes": "Заказ до 17:00"
    },
    "Пекарня": {
        "phone": "+7 930 456-88-02",
        "contact_person": "Менеджер Пекарни",
        "deadline": time(18, 0),
        "min_order_amount": 300,
        "min_order_items": 4,
        "delivery_days": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
        "notes": "Заказ до 18:00"
    },
    "ПП-еда": {
        "phone": "+7 939 987-12-43",
        "contact_person": "Менеджер ПП-еды",
        "deadline": time(19, 0),
        "min_order_amount": 800,
        "min_order_items": 2,
        "delivery_days": ["пн", "вт", "ср", "чт", "пт"],
        "notes": "Заказ до 19:00 (только будни)"
    },
    "SoulKitchen": {
        "phone": "+7 900 320-23-19",
        "contact_person": "Менеджер SoulKitchen",
        "deadline": time(21, 0),
        "min_order_amount": 600,
        "min_order_items": 3,
        "delivery_days": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
        "notes": "Заказ до 21:00"
    }
}


HOLIDAYS = [
    "01-01", "01-02", "01-03", "01-04", "01-05", "01-06", "01-07", "01-08",  
    "02-23", "03-08", "05-01", "05-09", "06-12", "11-04", "09-01", "12-29", "12-30", "12-31" 
]


DATABASE_PATH = os.path.join("data", "procurement.db")