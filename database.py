# database.py - работа с SQLite
import sqlite3
import os
import json
from datetime import datetime, timedelta
import logging
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

def get_connection():
    
    return sqlite3.connect(DATABASE_PATH)

def create_tables():
    
    conn = get_connection()
    cursor = conn.cursor()

   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            supplier TEXT NOT NULL,
            min_stock INTEGER DEFAULT 2,
            par_level INTEGER DEFAULT 10,
            unit TEXT DEFAULT 'шт',
            price REAL DEFAULT 0,
            active BOOLEAN DEFAULT 1
        )
    ''')

   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            sale_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            UNIQUE(product_id, sale_date)
        )
    ''')

    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS write_offs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            write_off_date DATE NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            stock_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            UNIQUE(product_id, stock_date)
        )
    ''')

    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier TEXT NOT NULL,
            order_date DATE NOT NULL,
            items TEXT NOT NULL,  -- JSON-строка {product: qty}
            total_amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Таблицы созданы или уже существуют")


def add_product(name, category, supplier, min_stock, par_level, price=0):
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO products (name, category, supplier, min_stock, par_level, price)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, category, supplier, min_stock, par_level, price))
    conn.commit()
    conn.close()

def get_all_products(supplier=None):
    
    conn = get_connection()
    cursor = conn.cursor()
    if supplier:
        cursor.execute('''
            SELECT name, supplier, min_stock, par_level, price
            FROM products
            WHERE supplier = ? AND active = 1
        ''', (supplier,))
    else:
        cursor.execute('''
            SELECT name, supplier, min_stock, par_level, price
            FROM products
            WHERE active = 1
        ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_product_id(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM products WHERE name = ?', (name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def add_sale(product_name, quantity, sale_date=None):
    
    if sale_date is None:
        sale_date = datetime.now().strftime('%Y-%m-%d')
    product_id = get_product_id(product_name)
    if not product_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sales (product_id, quantity, sale_date)
        VALUES (?, ?, ?)
        ON CONFLICT(product_id, sale_date) DO UPDATE SET quantity = excluded.quantity
    ''', (product_id, quantity, sale_date))
    conn.commit()
    conn.close()
    return True

def get_sales_history(product_name, days=90):
    
    product_id = get_product_id(product_name)
    if not product_id:
        return []
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sale_date, quantity FROM sales
        WHERE product_id = ? AND sale_date >= ?
        ORDER BY sale_date
    ''', (product_id, start_date))
    rows = cursor.fetchall()
    conn.close()
    return rows


def add_write_off(product_name, quantity, reason="", write_off_date=None):
    if write_off_date is None:
        write_off_date = datetime.now().strftime('%Y-%m-%d')
    product_id = get_product_id(product_name)
    if not product_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO write_offs (product_id, quantity, write_off_date, reason)
        VALUES (?, ?, ?, ?)
    ''', (product_id, quantity, write_off_date, reason))
    conn.commit()
    conn.close()
    return True

def get_write_offs_history(product_name, days=90):
    product_id = get_product_id(product_name)
    if not product_id:
        return []
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT write_off_date, quantity FROM write_offs
        WHERE product_id = ? AND write_off_date >= ?
        ORDER BY write_off_date
    ''', (product_id, start_date))
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_stock(product_name, quantity, stock_date=None):
    
    if stock_date is None:
        stock_date = datetime.now().strftime('%Y-%m-%d')
    product_id = get_product_id(product_name)
    if not product_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO stock (product_id, quantity, stock_date)
        VALUES (?, ?, ?)
        ON CONFLICT(product_id, stock_date) DO UPDATE SET quantity = excluded.quantity
    ''', (product_id, quantity, stock_date))
    conn.commit()
    conn.close()
    return True

def get_current_stock(product_name):
    
    product_id = get_product_id(product_name)
    if not product_id:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT quantity FROM stock
        WHERE product_id = ?
        ORDER BY stock_date DESC LIMIT 1
    ''', (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def save_order(supplier, items, total_amount):
    
    conn = get_connection()
    cursor = conn.cursor()
    order_date = datetime.now().strftime('%Y-%m-%d')
    items_json = json.dumps(items)
    cursor.execute('''
        INSERT INTO orders (supplier, order_date, items, total_amount)
        VALUES (?, ?, ?, ?)
    ''', (supplier, order_date, items_json, total_amount))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id


def populate_test_data():
    
    test_products = [
        # Pigeon
        ("Пшеничный хлеб", "Хлеб", "Pigeon", 2, 10, 50),
        ("Чиабатта", "Хлеб", "Pigeon", 3, 12, 60),
        # Пестречинка
        ("Молоко 3.2%", "Молочка", "Пестречинка", 5, 25, 80),
        ("Сметана", "Молочка", "Пестречинка", 4, 20, 70),
        # Пекарня
        ("Неженка с малиной", "Выпечка", "Пекарня", 3, 15, 45),
        ("Самса с курицей", "Выпечка", "Пекарня", 6, 30, 90),
        # ПП-еда
        ("Курица с картошкой", "Готовая еда", "ПП-еда", 3, 12, 120),
        ("Паста с курицей", "Готовая еда", "ПП-еда", 4, 15, 110),
        # SoulKitchen
        ("Ролл курица", "Готовая еда", "SoulKitchen", 4, 20, 150),
        ("Сэндвич курица", "Готовая еда", "SoulKitchen", 5, 25, 130),
    ]
    for prod in test_products:
        add_product(*prod)

    
    import random
    from datetime import timedelta
    products = get_all_products()
    start_date = datetime.now() - timedelta(days=90)
    for i in range(90):
        sale_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        for name, supplier, min_stock, par_level, price in products:
            
            qty = random.randint(1, 10)
            add_sale(name, qty, sale_date)
    
    for name, _, _, _, _ in products:
        update_stock(name, random.randint(5, 20))
    logger.info("Тестовые данные добавлены")