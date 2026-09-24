import asyncio
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
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


# ==================== КОМАНДЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    expires = await get_subscription(user_id)

    if expires:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Получить ссылку в канал", callback_data="get_link")
        builder.button(text="📅 Мой статус", callback_data="my_status")
        builder.adjust(1)

        await message.answer(
            f"👋 С возвращением, <b>{message.from_user.first_name}</b>!\n\n"
            f"✅ Ваша подписка активна до <b>{expires[:10]}</b>\n\n"
            f"Что хотите сделать?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return

    builder = InlineKeyboardBuilder()
    builder.button(text=f"💎 Оформить за {PRICE_STARS} ⭐", callback_data="buy")
    builder.adjust(1)

    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🔥 Добро пожаловать в <b>Slivki VIP</b> — закрытый клуб для своих.\n\n"
        f"<b>Что внутри:</b>\n"
        f"• Эксклюзивный контент каждую неделю\n"
        f"• Закрытые разборы и материалы\n"
        f"• Поддержка и общение с единомышленниками\n\n"
        f"<b>Стоимость:</b> {PRICE_STARS} ⭐ / {SUBSCRIPTION_DAYS} дней\n"
        f"<b>Доступ:</b> мгновенно после оплаты\n\n"
        f"Жми кнопку ниже 👇",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        f"❓ <b>Помощь по боту Slivki VIP</b>\n\n"
        f"<b>Команды:</b>\n"
        f"/start — оформить или продлить подписку\n"
        f"/status — проверить срок подписки\n"
        f"/link — получить новую ссылку в канал\n"
        f"/help — это сообщение\n\n"
        f"<b>Как работает подписка:</b>\n"
        f"1. Оплачиваете {PRICE_STARS} ⭐ через Telegram\n"
        f"2. Получаете одноразовую ссылку в канал\n"
        f"3. Подписка действует {SUBSCRIPTION_DAYS} дней\n"
        f"4. За 3 дня до окончания придёт напоминание",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    expires = await get_subscription(message.from_user.id)
    if expires:
        await message.answer(
            f"📅 Ваша подписка активна до <b>{expires[:10]}</b>",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Подписки нет. Нажмите /start для оформления.")


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
        await message.answer(
            f"🔗 Ваша персональная ссылка:\n{invite.invite_link}\n\n"
            f"⚠️ Одноразовая, только для вас.",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logging.error(f"Ошибка создания ссылки: {e}")
        await message.answer("Не удалось создать ссылку. Попробуйте позже.")


# ==================== INLINE-КНОПКИ ====================

@dp.callback_query(F.data == "buy")
async def on_buy(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id

    await bot.send_invoice(
        chat_id=user_id,
        title="Подписка Slivki VIP",
        description=(
            f"Доступ к закрытому каналу на {SUBSCRIPTION_DAYS} дней. "
            f"Ссылка придёт мгновенно после оплаты."
        ),
        payload=f"sub_{user_id}_{SUBSCRIPTION_DAYS}d",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Подписка Slivki VIP", amount=PRICE_STARS)],
        start_parameter="sub",
    )


@dp.callback_query(F.data == "my_status")
async def on_status(callback: types.CallbackQuery):
    await callback.answer()
    expires = await get_subscription(callback.from_user.id)
    if expires:
        await callback.message.answer(
            f"📅 Ваша подписка активна до <b>{expires[:10]}</b>",
            parse_mode="HTML",
        )
    else:
        await callback.message.answer("❌ Подписки нет. Нажмите /start")


@dp.callback_query(F.data == "get_link")
async def on_get_link(callback: types.CallbackQuery):
    await callback.answer()
    expires = await get_subscription(callback.from_user.id)
    if not expires:
        await callback.message.answer("Сначала оформите подписку: /start")
        return

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"link_{callback.from_user.id}",
        )
        await callback.message.answer(
            f"🔗 Ваша персональная ссылка:\n{invite.invite_link}\n\n"
            f"⚠️ Одноразовая, только для вас.",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logging.error(f"Ошибка создания ссылки: {e}")
        await callback.message.answer("Не удалось создать ссылку. Попробуйте позже.")


# ==================== ОПЛАТА ====================

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
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"💎 Добро пожаловать в <b>Slivki VIP</b>!\n\n"
            f"🔗 <b>Ваша ссылка для входа:</b>\n"
            f"{invite.invite_link}\n\n"
            f"📅 Подписка активна {SUBSCRIPTION_DAYS} дней\n"
            f"⚠️ Ссылка одноразовая — только для вас\n\n"
            f"Если ссылка не сработала — нажмите /link для новой.\n"
            f"Приятного просмотра! 🔥",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logging.error(f"Ошибка создания ссылки: {e}")
        await message.answer(
            "✅ Оплата получена, но не удалось создать ссылку. "
            "Напишите администратору."
        )


# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
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
    threading.Thread(target=run_http_server, daemon=True).start()
    asyncio.run(main())


if __name__ == "__main__":
    start_background()
