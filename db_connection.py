import os
import mysql.connector
import datetime


def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        database=os.environ.get("DB_NAME")
    )


def get_db_cursor():
    conn = get_db_connection()
    return conn.cursor()


def get_access_level(user_name):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT access_level FROM users WHERE user_name = %s", (user_name,))
        result = cursor.fetchone()
        if result is None:
            return None
        return result[0]


def get_user_text_model(user_name):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT model_name, system_prompt FROM chatbotv2.users u INNER JOIN chatbotv2.models m WHERE text_model_id = model_id AND user_name = %s", (user_name,))
        result = cursor.fetchone()
        return result


def update_last_visit(user_name):
    current_datetime = datetime.datetime.now()
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE users SET last_active=%s WHERE user_name = %s", (current_datetime, user_name,))
        conn.commit()
