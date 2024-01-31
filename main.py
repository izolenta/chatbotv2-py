import io

from PIL import Image
from PIL.Image import Resampling
from telegram import Update
import telegram.ext
from openai import OpenAI
from dotenv import load_dotenv
from functools import wraps
import db_connection as db
import os
import logging

from constants import AccessLevel, CTX_MODE
from img_helpers import image_to_base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
load_dotenv()
client = OpenAI()


def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: telegram.ext.CallbackContext, *args, **kwargs):
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
async def start(update: Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
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
async def set_assistant(update: Update, context: telegram.ext.CallbackContext):
    username = update.effective_chat.username
    person = 'a friendly personal assistant'
    if len(context.args) > 0:
        person = ' '.join(context.args)
    db.set_assistant(username, person)
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Assistant: {}'.format(person))


@restricted
async def reset_assistant(update: Update, context: telegram.ext.CallbackContext):
    username = update.effective_chat.username
    person = 'a friendly personal assistant'
    db.set_assistant(username, person)
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Assistant: {}'.format(person))


@restricted
async def check_ctx(update: Update, context: telegram.ext.CallbackContext):
    username = update.effective_chat.username
    ctx = db.get_context_status(username)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text='Current chat mode: {}'.format('context' if ctx[0] == 1 else 'simple'))


@restricted
async def set_ctx(update: Update, context: telegram.ext.CallbackContext):
    username = update.effective_chat.username
    db.set_context_mode(username, 1)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text='Current chat mode: context, history is reset')


@restricted
async def reset_ctx(update: Update, context: telegram.ext.CallbackContext):
    username = update.effective_chat.username
    db.set_context_mode(username, 0)
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Current chat mode: simple')


@restricted
async def image(update: Update, context: telegram.ext.CallbackContext):
    username = update.effective_chat.username
    response = client.images.generate(
        model="dall-e-3",
        prompt=' '.join(context.args),
        size="1024x1024",
        quality="standard",
        n=1,
    )

    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=response.data[0].url)


@restricted
async def echo(update: Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    data = db.get_user_text_model(update.effective_chat.username)
    message = update.message.text
    keep_ctx = data[3]
    if keep_ctx == CTX_MODE.SIMPLE.value:
        await simple_echo(update, context, data[0], data[1], message)
    else:
        await content_echo(update, context, data[0], data[1], message)
    # Generate a response using ChatGPT 4


async def simple_echo(update, context, model, person, message):
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are {}".format(person)},
            {"role": "user", "content": message}
        ])

    response = completion.choices[0].message.content
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)


async def content_echo(update, context, model, person, message):
    username = update.effective_chat.username
    msgs, is_new = db.get_context_array(username)
    if is_new:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text='Your context is empty or too old, creating a new one')

    ctx_arr = [{"role": "system", "content": "You are {}".format(person)}]
    ctx_arr.extend(msgs)
    user_message = {"role": "user", "content": message}
    ctx_arr.extend([user_message])

    completion = client.chat.completions.create(model=model, messages=ctx_arr)
    response = completion.choices[0].message.content
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    assistant_message = {"role": "assistant", "content": response}
    db.add_to_context_array(username, user_message, assistant_message)


@restricted
async def voice_echo(update: Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    message = update.message.text.split()
    message = ' '.join(message[1:])

    response = client.audio.speech.create(
        model="tts-1",
        voice="shimmer",
        input=message,
    )
    await context.bot.send_voice(chat_id=update.effective_chat.id, voice=response.content)


@restricted
async def vision_echo(update: Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    bb = await photo_file.download_as_bytearray()
    byte_stream = io.BytesIO(bb)
    img = Image.open(byte_stream)
    img.thumbnail((200, 200), Resampling.BILINEAR)
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    img_bytes = byte_arr.getvalue()
    base = image_to_base64(img_bytes)
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the attached image"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": base,
                            "detail": "low"
                        }
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=response.choices[0].message.content)


def main() -> None:
    application = telegram.ext.ApplicationBuilder().token(os.environ.get("TELEGRAM_TOKEN")).build()

    ctx_handler = telegram.ext.CommandHandler('mode', check_ctx)
    set_ctx_handler = telegram.ext.CommandHandler('context', set_ctx)
    reset_ctx_handler = telegram.ext.CommandHandler('simple', reset_ctx)
    img_handler = telegram.ext.CommandHandler('image', image)
    start_handler = telegram.ext.CommandHandler('start', start)
    set_assistant_handler = telegram.ext.CommandHandler('setassistant', set_assistant)
    reset_assistant_handler = telegram.ext.CommandHandler('resetassistant', reset_assistant)
    voice_handler = telegram.ext.CommandHandler('voice', voice_echo)

    echo_handler = telegram.ext.MessageHandler(telegram.ext.filters.TEXT & (~telegram.ext.filters.COMMAND), echo)
    vision_handler = telegram.ext.MessageHandler(telegram.ext.filters.PHOTO, vision_echo)

    application.add_handler(start_handler)
    application.add_handler(ctx_handler)
    application.add_handler(set_ctx_handler)
    application.add_handler(img_handler)
    application.add_handler(reset_ctx_handler)
    application.add_handler(set_assistant_handler)
    application.add_handler(reset_assistant_handler)
    application.add_handler(voice_handler)
    application.add_handler(echo_handler)
    application.add_handler(vision_handler)

    application.run_polling()


if __name__ == '__main__':
    main()
