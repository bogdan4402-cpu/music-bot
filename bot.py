import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import BOT_TOKEN
from keyboards import main_menu, reaction_keyboard, skip_review_keyboard

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())


class ReviewState(StatesGroup):
    waiting = State()


# ── /start ───────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    unlistened = db.get_unlistened_count(uid)
    await message.answer(
        "👋 Привет!\n\n"
        "🎵 <b>Отправь ссылку</b> на трек (Spotify или YouTube) — добавлю в очередь.\n"
        "🎧 <b>Нажми кнопку ниже</b>, чтобы слушать треки от других.\n\n"
        f"Непрослушанных треков: <b>{unlistened}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )


# ── Приём ссылок ─────────────────────────────────────────────

@dp.message(F.text.regexp(r'https?://'))
async def handle_link(message: Message):
    uid = message.from_user.id
    url = message.text.strip()

    if "spotify.com" not in url and "youtu" not in url:
        await message.answer("⚠️ Отправляй только ссылки Spotify или YouTube.")
        return

    db.add_track(url, added_by=uid)
    platform = "🟢 Spotify" if "spotify" in url else "🔴 YouTube"

    await message.answer(
        f"✅ Трек добавлен! {platform}\n🔗 <code>{url}</code>",
        parse_mode="HTML"
    )

    # Уведомить всех остальных пользователей
    for other_uid in db.get_all_users_except(uid):
        try:
            count = db.get_unlistened_count(other_uid)
            await bot.send_message(
                other_uid,
                f"🎵 Новый трек в очереди! Непрослушанных: <b>{count}</b>",
                parse_mode="HTML",
                reply_markup=main_menu(count)
            )
        except Exception:
            pass


# ── Слушать следующий трек ───────────────────────────────────

@dp.callback_query(F.data == "listen_next")
async def listen_next(callback: CallbackQuery, state: FSMContext):
    uid   = callback.from_user.id
    track = db.get_next_unlistened(uid)

    if not track:
        await callback.message.edit_text("🎉 Все треки прослушаны! Жди новых 🎵")
        await callback.answer()
        return

    track_id   = track["id"]
    url        = track["url"]
    unlistened = db.get_unlistened_count(uid)
    platform   = "🟢 Spotify" if "spotify" in url else "🔴 YouTube"

    await state.update_data(current_track_id=track_id)
    await callback.message.edit_text(
        f"🎧 {platform}\n\n"
        f"🔗 <a href='{url}'>Открыть трек</a>\n\n"
        f"📋 Осталось непрослушанных: <b>{max(0, unlistened - 1)}</b>\n\n"
        "Послушай и поставь реакцию 👇",
        parse_mode="HTML",
        reply_markup=reaction_keyboard(track_id),
        disable_web_page_preview=False
    )
    await callback.answer()


# ── Реакция ──────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_reaction(callback: CallbackQuery, state: FSMContext):
    reaction = callback.data.split("_")[0]
    track_id = int(callback.data.split("_")[1])
    uid      = callback.from_user.id

    db.set_reaction(track_id, uid, reaction)
    await state.update_data(current_track_id=track_id, reaction=reaction)

    emoji = "❤️" if reaction == "like" else "💔"
    await callback.message.edit_text(
        f"{emoji} Теперь напиши короткий отзыв.\n\n"
        "Впечатления, ощущения — что угодно 🎵\n"
        "Или нажми кнопку, чтобы пропустить.",
        reply_markup=skip_review_keyboard()
    )
    await state.set_state(ReviewState.waiting)
    await callback.answer()


# ── Пропустить отзыв ─────────────────────────────────────────

@dp.callback_query(F.data == "skip_review", ReviewState.waiting)
async def skip_review(callback: CallbackQuery, state: FSMContext):
    uid      = callback.from_user.id
    data     = await state.get_data()
    track_id = data["current_track_id"]

    db.mark_listened(track_id, uid)
    await state.clear()

    unlistened = db.get_unlistened_count(uid)
    await callback.message.edit_text("⏭ Отзыв пропущен.", reply_markup=main_menu(unlistened))
    await callback.answer()


# ── Текст отзыва ─────────────────────────────────────────────

@dp.message(ReviewState.waiting)
async def receive_review(message: Message, state: FSMContext):
    uid      = message.from_user.id
    data     = await state.get_data()
    track_id = data["current_track_id"]
    reaction = data.get("reaction", "like")

    db.save_review(track_id, uid, message.text)
    db.mark_listened(track_id, uid)
    await state.clear()

    emoji      = "❤️" if reaction == "like" else "💔"
    unlistened = db.get_unlistened_count(uid)
    await message.answer(f"✅ Отзыв сохранён {emoji}", reply_markup=main_menu(unlistened))

    # Уведомить автора трека
    track = db.get_track_by_id(track_id)
    if track and track["added_by"] != uid:
        try:
            sender = f"@{message.from_user.username}" if message.from_user.username else f"id{uid}"
            await bot.send_message(
                track["added_by"],
                f"📝 Отзыв на твой трек от {sender}\n\n"
                f"🔗 {track['url']}\n"
                f"{emoji} {'Лайк' if reaction == 'like' else 'Дизлайк'}\n\n"
                f"💬 <i>{message.text}</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ── Статистика ───────────────────────────────────────────────

@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    uid   = callback.from_user.id
    stats = db.get_user_stats(uid)
    unlistened = db.get_unlistened_count(uid)

    await callback.message.edit_text(
        f"📊 <b>Твоя статистика</b>\n\n"
        f"🎵 Добавлено треков: <b>{stats['total']}</b>\n"
        f"👂 Прослушано другими: <b>{stats['listened']}</b>\n"
        f"❤️ Лайков: <b>{stats['likes']}</b>\n"
        f"💔 Дизлайков: <b>{stats['dislikes']}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


# ── Запуск ───────────────────────────────────────────────────

async def main():
    db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
