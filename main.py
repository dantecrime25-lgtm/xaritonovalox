import asyncio
import json
import os
from typing import Optional, List, Dict

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

DATA_FILE = "data.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Установи переменную окружения BOT_TOKEN в Replit
OWNER_ID = 7322925570  # твой owner id

default_data = {
    "message": "Привет! Это автосообщение.",
    "interval_min": 10,
    "running": False,
    "chats": []
}


def load_data() -> Dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        save_data(default_data)
        return default_data.copy()


def save_data(data: Dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def owner_only(func):
    async def wrapper(message: Message):
        if message.from_user is None or message.from_user.id != OWNER_ID:
            await message.answer("Доступ запрещён — только владелец может управлять ботом.")
            return
        return await func(message)
    return wrapper


def chat_repr(c: Dict) -> str:
    return f"chat_id={c['chat_id']}" + (f", topic_id={c['topic_id']}" if c.get("topic_id") else "")


sender_task: Optional[asyncio.Task] = None


async def sender_loop():
    try:
        while data.get("running"):
            interval = int(data.get("interval_min", 10))
            if interval < 1:
                interval = 1
            elif interval > 60:
                interval = 60
            text = data.get("message", "")
            chats: List[Dict] = data.get("chats", [])
            if text and chats:
                for c in chats:
                    chat_id = c["chat_id"]
                    topic_id = c.get("topic_id")
                    try:
                        if topic_id:
                            await bot.send_message(chat_id, text, message_thread_id=topic_id)
                        else:
                            await bot.send_message(chat_id, text)
                    except Exception as e:
                        print(f"Ошибка при отправке в {chat_id} topic={topic_id}: {e}")
            else:
                print("Нет текста или списка чатов — пропускаю отправку.")
            await asyncio.sleep(interval * 60)
    except asyncio.CancelledError:
        print("Sender loop cancelled")


async def start_sender_if_needed():
    global sender_task
    if data.get("running") and (sender_task is None or sender_task.done()):
        sender_task = asyncio.create_task(sender_loop())
        print("Sender started.")


async def stop_sender_if_running():
    global sender_task
    if sender_task and not sender_task.done():
        sender_task.cancel()
        try:
            await sender_task
        except asyncio.CancelledError:
            pass
        sender_task = None
        print("Sender stopped.")


@dp.message(Command(commands=["start", "help"]))
async def cmd_start(message: Message):
    await message.reply(
        "Я бот-автопостер.\n\n"
        "/owner — показать owner id\n"
        "/setmessage <текст>\n"
        "/setinterval <1-60>\n"
        "/addchat <chat_id> [topic_id]\n"
        "/removechat <chat_id> [topic_id]\n"
        "/list — настройки\n"
        "/startautopost — включить рассылку\n"
        "/stopautopost — выключить рассылку\n"
        "/sendnow — отправить сразу"
    )


@dp.message(Command(commands=["owner"]))
async def cmd_owner(message: Message):
    await message.reply(f"Owner id: {OWNER_ID}")


@dp.message(Command(commands=["setmessage"]))
@owner_only
async def cmd_setmessage(message: Message):
    args = message.get_args()
    if not args:
        await message.reply("Использование: /setmessage <текст>")
        return
    data["message"] = args
    save_data(data)
    await message.reply("Текст обновлён.")


@dp.message(Command(commands=["setinterval"]))
@owner_only
async def cmd_setinterval(message: Message):
    args = message.get_args()
    if not args:
        await message.reply("Использование: /setinterval <1-60>")
        return
    try:
        m = int(args.strip())
        if not (1 <= m <= 60):
            raise ValueError
    except:
        await message.reply("Интервал должен быть 1-60.")
        return
    data["interval_min"] = m
    save_data(data)
    await message.reply(f"Интервал: {m} мин.")
    await stop_sender_if_running()
    if data.get("running"):
        await start_sender_if_needed()


@dp.message(Command(commands=["addchat"]))
@owner_only
async def cmd_addchat(message: Message):
    args = message.get_args().split()
    if not args:
        await message.reply("Использование: /addchat <chat_id> [topic_id]")
        return
    try:
        chat_id = int(args[0])
    except:
        await message.reply("chat_id должен быть числом")
        return
    topic_id = int(args[1]) if len(args) > 1 else None
    entry = {"chat_id": chat_id, "topic_id": topic_id}
    if entry not in data["chats"]:
        data["chats"].append(entry)
        save_data(data)
        await message.reply(f"Добавлен: {chat_repr(entry)}")
    else:
        await message.reply("Уже есть.")


@dp.message(Command(commands=["removechat"]))
@owner_only
async def cmd_removechat(message: Message):
    args = message.get_args().split()
    if not args:
        await message.reply("Использование: /removechat <chat_id> [topic_id]")
        return
    chat_id = int(args[0])
    topic_id = int(args[1]) if len(args) > 1 else None
    before = len(data["chats"])
    data["chats"] = [c for c in data["chats"] if not (c["chat_id"] == chat_id and c.get("topic_id") == topic_id)]
    save_data(data)
    if len(data["chats"]) < before:
        await message.reply("Удалил.")
    else:
        await message.reply("Не найдено.")


@dp.message(Command(commands=["list"]))
@owner_only
async def cmd_list(message: Message):
    txt = [
        f"Текст: {data.get('message','')}",
        f"Интервал: {data.get('interval_min')} мин",
        f"Работает: {data.get('running')}",
        "Чаты:"
    ]
    if data.get("chats"):
        for c in data["chats"]:
            txt.append(" - " + chat_repr(c))
    else:
        txt.append(" (пусто)")
    await message.reply("\n".join(txt))


@dp.message(Command(commands=["startautopost"]))
@owner_only
async def cmd_startautopost(message: Message):
    if data.get("running"):
        await message.reply("Уже работает.")
        return
    data["running"] = True
    save_data(data)
    await start_sender_if_needed()
    await message.reply("Авторассылка запущена.")


@dp.message(Command(commands=["stopautopost"]))
@owner_only
async def cmd_stopautopost(message: Message):
    if not data.get("running"):
        await message.reply("Уже остановлено.")
        return
    data["running"] = False
    save_data(data)
    await stop_sender_if_running()
    await message.reply("Остановлено.")


@dp.message(Command(commands=["sendnow"]))
@owner_only
async def cmd_sendnow(message: Message):
    text = data.get("message", "")
    chats = data.get("chats", [])
    if not text or not chats:
        await message.reply("Нет текста или чатов.")
        return
    sent = 0
    for c in chats:
        try:
            if c.get("topic_id"):
                await bot.send_message(c["chat_id"], text, message_thread_id=c["topic_id"])
            else:
                await bot.send_message(c["chat_id"], text)
            sent += 1
        except Exception as e:
            print("Ошибка:", e)
    await message.reply(f"Отправлено {sent}/{len(chats)}")


async def on_startup():
    await start_sender_if_needed()


async def on_shutdown():
    await stop_sender_if_running()
    await bot.session.close()


if __name__ == "__main__":
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.run_polling(bot)
