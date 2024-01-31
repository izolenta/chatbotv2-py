import os
import mysql.connector
import datetime
import json


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
        cursor.execute("SELECT model_name, system_prompt, context_ref, keep_context FROM chatbotv2.users u INNER JOIN chatbotv2.models m WHERE text_model_id = model_id AND user_name = %s", (user_name,))
        result = cursor.fetchone()
        return result


def get_context_status(user_name):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT keep_context FROM chatbotv2.users  WHERE user_name = %s", (user_name,))
        result = cursor.fetchone()
        return result


def set_context_mode(user_name, mode):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE users SET keep_context=%s WHERE user_name = %s", (mode, user_name,))
        conn.commit()
        cursor.execute("SELECT context_ref FROM chatbotv2.users  WHERE user_name = %s", (user_name,))
        result = cursor.fetchone()
        ctx_ref = result[0]
        if ctx_ref is not None:
            cursor.execute("DELETE FROM context_data  WHERE context_ref = %s", (ctx_ref,))
            cursor.execute("DELETE FROM contexts  WHERE context_id = %s", (ctx_ref,))
            cursor.execute("UPDATE users SET context_ref=NULL WHERE user_name = %s", (user_name,))
            cursor.execute("INSERT INTO contexts (last_used) VALUES (NOW())")
            ctx_ref = cursor.lastrowid
            cursor.execute("UPDATE users SET context_ref=%s WHERE user_name = %s", (ctx_ref, user_name,))
            conn.commit()


def set_assistant(user_name, person):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE users SET system_prompt=%s WHERE user_name = %s", (person, user_name,))
        conn.commit()


def update_last_visit(user_name):
    current_datetime = datetime.datetime.now()
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE users SET last_active=%s WHERE user_name = %s", (current_datetime, user_name,))
        conn.commit()


def get_context_array(user_name):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT context_ref FROM chatbotv2.users  WHERE user_name = %s", (user_name,))
        result = cursor.fetchone()
        ctx_ref = result[0]
        need_to_create_new = ctx_ref is None
        if not need_to_create_new:
            cursor.execute("SELECT last_used FROM chatbotv2.contexts  WHERE context_id = %s", (ctx_ref,))
            result = cursor.fetchone()
            current_datetime = datetime.datetime.now()
            diff = current_datetime - result[0]
            need_to_create_new = diff.total_seconds() > 2 * 3600  # 2 hours
            if need_to_create_new:
                cursor.execute("DELETE FROM context_data  WHERE context_ref = %s", (ctx_ref,))
                cursor.execute("DELETE FROM contexts  WHERE context_id = %s", (ctx_ref,))
                cursor.execute("UPDATE users SET context_ref=NULL WHERE user_name = %s", (user_name,))
                conn.commit()

        if need_to_create_new:
            cursor.execute("INSERT INTO contexts (last_used) VALUES (NOW())")
            ctx_ref = cursor.lastrowid
            cursor.execute("UPDATE users SET context_ref=%s WHERE user_name = %s", (ctx_ref, user_name,))
            conn.commit()

        cursor.execute("SELECT record_data FROM context_data  WHERE context_ref = %s ORDER BY record_id", (ctx_ref,))
        result = cursor.fetchall()
        dict_array = []
        for json_str in result:
            dict_array.append(json.loads(json_str[0]))
        return dict_array, need_to_create_new


def add_to_context_array(user_name, user_message, assistant_message):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT context_ref FROM chatbotv2.users  WHERE user_name = %s", (user_name,))
        result = cursor.fetchone()
        ctx_ref = result[0]
        cursor.execute("INSERT INTO context_data (context_ref, record_data) VALUES (%s, %s)", (ctx_ref, json.dumps(user_message),))
        cursor.execute("INSERT INTO context_data (context_ref, record_data) VALUES (%s, %s)", (ctx_ref, json.dumps(assistant_message),))
        current_datetime = datetime.datetime.now()
        cursor.execute("UPDATE contexts SET last_used=%s WHERE context_id = %s", (current_datetime, ctx_ref,))
        conn.commit()
