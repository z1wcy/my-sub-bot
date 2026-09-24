import asyncio
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from dotenv import load_dotenv

from database import init_db, save_subscription, get_subscription

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
PRICE_STARS = int(os.getenv("PRICE_STARS", 300))
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", 30))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ==================== ХЭНДЛЕРЫ БОТА ====================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    expires = await get_subscription(user_id)

    if expires:
        await message.answer(
            f"✅ У вас активна подписка до {expires[:10]}.\n"
            f"Получить ссылку: /link"
        )
        return

    await bot.send_invoice(
        chat_id=user_id,
        title="Подписка на закрытый канал",
        description=f"Доступ на {SUBSCRIPTION_DAYS} дней",
        payload=f"sub_{user_id}_{SUBSCRIPTION_DAYS}d",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Подписка", amount=PRICE_STARS)],
    )


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id

    await save_subscription(
        user_id, SUBSCRIPTION_DAYS, "stars", payment.telegram_payment_charge_id
    )

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"access_{user_id}",
        )
        await message.answer(
            f"✅ Оплата получена! Ваша ссылка:\n{invite.invite_link}\n\n"
            f"⚠️ Ссылка действительна только для вас и одноразовая."
        )
    except Exception as e:
        logging.error(f"Ошибка создания ссылки: {e}")
        await message.answer(
            "✅ Оплата получена, но не удалось создать ссылку. "
            "Напишите администратору."
        )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    expires = await get_subscription(message.from_user.id)
    if expires:
        await message.answer(f"Подписка активна до {expires[:10]}")
    else:
        await message.answer("Подписки нет. Нажмите /start для оплаты.")


@dp.message(Command("link"))
async def cmd_link(message: Message):
    expires = await get_subscription(message.from_user.id)
    if not expires:
        await message.answer("Сначала оформите подписку: /start")
        return

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"relink_{message.from_user.id}",
        )
        await message.answer(f"Новая ссылка: {invite.invite_link}")
    except Exception as e:
        logging.error(f"Ошибка создания ссылки: {e}")
        await message.answer("Не удалось создать ссылку. Попробуйте позже.")


# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        # Отключаем стандартные логи веб-сервера, чтобы не засорять вывод
        return


def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info(f"HTTP-сервер запущен на порту {port}")
    server.serve_forever()


# ==================== ЗАПУСК ====================

async def main():
    await init_db()
    me = await bot.get_me()
    logging.info(f"Бот запущен: @{me.username}")
    await dp.start_polling(bot)


def start_background():
    # Запускаем HTTP-сервер в фоне (Render требует открытый порт)
    threading.Thread(target=run_http_server, daemon=True).start()
    # Запускаем бота в основном потоке
    asyncio.run(main())


if __name__ == "__main__":
    start_background()