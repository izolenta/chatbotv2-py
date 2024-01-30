from enum import Enum

from telegram import Update
from telegram.ext import ApplicationBuilder, ConversationHandler, CommandHandler, MessageHandler, filters, \
    CallbackContext, \
    ContextTypes
from openai import OpenAI
from dotenv import load_dotenv
from functools import wraps
import db_connection as db
import os
import logging


class AccessLevel(Enum):
    USER = 0
    POWERUSER = 1
    SUPERUSER = 2


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
load_dotenv()
client = OpenAI()


def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        username = update.effective_chat.username
        access = db.get_access_level(username)
        if access is None or access not in range(0, 3):
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text='Back off, {}, I do not know you!'.format(username))
            return
        db.update_last_visit(username)
        return await func(update, context, *args, **kwargs)

    return wrapped


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_chat.username
    access = db.get_access_level(username)
    if access == AccessLevel.USER.value:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text='Hello, {}, I\'m your ChatGPT bot'.format(username))
    elif access == AccessLevel.POWERUSER.value:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text='Glad to see you, dear {}, how can I help today?'.format(username))
    elif access == AccessLevel.SUPERUSER.value:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text='Bow to you, Master {}, I am ready to serve!'.format(username))


@restricted
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = db.get_user_text_model(update.effective_chat.username)
    message = update.message.text

    # Generate a response using ChatGPT 4
    completion = client.chat.completions.create(
        model=data[0],
        messages=[
            {"role": "system","content": data[1]},
            {"role": "user", "content": message}
        ])
    # Send the response back to the user
    await context.bot.send_message(chat_id=update.effective_chat.id, text=completion.choices[0].message.content)


def main() -> None:
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_TOKEN")).build()

    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    application.add_handler(start_handler)
    application.add_handler(echo_handler)

    application.run_polling()


if __name__ == '__main__':
    main()
