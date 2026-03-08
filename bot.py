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
from keyboards import (
    main_menu,
    cancel_keyboard,
    reaction_keyboard,
    skip_review_keyboard,
    reviews_navigation,
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())


class AddTrackState(StatesGroup):
    waiting_for_url = State()


class ReviewState(StatesGroup):
    waiting = State()


def platform_label(url: str) -> str:
    if "spotify" in url:
        return "🟢 Spotify"
    return "🔴 YouTube"


@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    unlistened = db.get_unlistened_count(uid)
    await message.answer(
        "👋 Привіт!\n\n"
        "Тут можна ділитися треками та слухати музику один одного.\n\n"
        f"Непрослуханих треків: <b>{unlistened}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )


@dp.callback_query(F.data == "main_menu")
async def go_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    unlistened = db.get_unlistened_count(uid)
    await callback.message.edit_text(
        f"🏠 Головне меню\n\nНепрослуханих треків: <b>{unlistened}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


@dp.callback_query(F.data == "add_track")
async def ask_for_url(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddTrackState.waiting_for_url)
    await callback.message.edit_text(
        "🎵 Надішли посилання на трек\n\n"
        "Підтримуються посилання <b>Spotify</b> та <b>YouTube</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@dp.message(AddTrackState.waiting_for_url)
async def receive_url(message: Message, state: FSMContext):
    uid = message.from_user.id
    url = message.text.strip() if message.text else ""

    if not url.startswith("http"):
        await message.answer(
            "⚠️ Надішли саме посилання (починається з https://)",
            reply_markup=cancel_keyboard()
        )
        return

    if "spotify.com" not in url and "youtu" not in url:
        await message.answer(
            "⚠️ Підтримуються тільки посилання Spotify або YouTube",
            reply_markup=cancel_keyboard()
        )
        return

    db.add_track(url, added_by=uid)
    await state.clear()

    platform = platform_label(url)
    unlistened = db.get_unlistened_count(uid)

    await message.answer(
        f"✅ Трек додано! {platform}\n\n🔗 <code>{url}</code>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )

    for other_uid in db.get_all_users_except(uid):
        try:
            count = db.get_unlistened_count(other_uid)
            await bot.send_message(
                other_uid,
                f"🎵 З'явився новий трек!\n"
                f"{platform} <a href='{url}'>Відкрити</a>\n\n"
                f"Непрослуханих треків: <b>{count}</b>",
                parse_mode="HTML",
                reply_markup=main_menu(count)
            )
        except Exception:
            pass


@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    unlistened = db.get_unlistened_count(uid)
    await callback.message.edit_text(
        f"❌ Скасовано.\n\nНепрослуханих треків: <b>{unlistened}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


@dp.callback_query(F.data == "listen_next")
async def listen_next(callback: CallbackQuery, state: FSMContext):
    uid   = callback.from_user.id
    track = db.get_next_unlistened(uid)

    if not track:
        await callback.message.edit_text(
            "🎉 Усі треки прослухано! Нових поки немає.\n\n"
            "Зачекай або додай свій трек 🎵",
            reply_markup=main_menu(0)
        )
        await callback.answer()
        return

    track_id   = track["id"]
    url        = track["url"]
    unlistened = db.get_unlistened_count(uid)
    platform   = platform_label(url)

    await state.update_data(current_track_id=track_id)

    await callback.message.edit_text(
        f"🎧 <b>Новий трек для тебе</b>\n\n"
        f"{platform}\n"
        f"🔗 <a href='{url}'>Натисни щоб відкрити трек</a>\n\n"
        f"📋 Залишилось непрослуханих: <b>{max(0, unlistened - 1)}</b>\n\n"
        "Послухай та постав реакцію 👇",
        parse_mode="HTML",
        reply_markup=reaction_keyboard(track_id),
        disable_web_page_preview=False
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("skip_track_"))
async def skip_track(callback: CallbackQuery, state: FSMContext):
    uid      = callback.from_user.id
    track_id = int(callback.data.split("_")[2])

    db.mark_listened(track_id, uid)
    await state.clear()

    unlistened = db.get_unlistened_count(uid)
    await callback.message.edit_text(
        "⏭ Трек пропущено.",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_reaction(callback: CallbackQuery, state: FSMContext):
    parts    = callback.data.split("_")
    reaction = parts[0]
    track_id = int(parts[1])
    uid      = callback.from_user.id

    db.set_reaction(track_id, uid, reaction)
    await state.update_data(current_track_id=track_id, reaction=reaction)

    emoji = "❤️" if reaction == "like" else "💔"

    await callback.message.edit_text(
        f"{emoji} Тепер напиши короткий відгук на трек.\n\n"
        "Враження, думки, відчуття — що завгодно 🎵\n\n"
        "Або натисни кнопку щоб пропустити відгук.",
        reply_markup=skip_review_keyboard()
    )
    await state.set_state(ReviewState.waiting)
    await callback.answer()


@dp.callback_query(F.data == "skip_review", ReviewState.waiting)
async def skip_review(callback: CallbackQuery, state: FSMContext):
    uid      = callback.from_user.id
    data     = await state.get_data()
    track_id = data["current_track_id"]

    db.mark_listened(track_id, uid)
    await state.clear()

    unlistened = db.get_unlistened_count(uid)
    await callback.message.edit_text(
        "⏭ Відгук пропущено.",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


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

    await message.answer(
        f"✅ Відгук збережено {emoji}",
        reply_markup=main_menu(unlistened)
    )

    track = db.get_track_by_id(track_id)
    if track and track["added_by"] != uid:
        try:
            sender = f"@{message.from_user.username}" if message.from_user.username else f"користувач {uid}"
            await bot.send_message(
                track["added_by"],
                f"📝 Новий відгук на твій трек від {sender}\n\n"
                f"🔗 {track['url']}\n"
                f"{emoji} {'Лайк' if reaction == 'like' else 'Дизлайк'}\n\n"
                f"💬 <i>{message.text}</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass


@dp.callback_query(F.data == "view_reviews")
async def view_reviews(callback: CallbackQuery):
    uid     = callback.from_user.id
    reviews = db.get_reviews_for_my_tracks(uid)

    if not reviews:
        unlistened = db.get_unlistened_count(uid)
        await callback.message.edit_text(
            "📋 Поки що немає відгуків на твої треки.",
            reply_markup=main_menu(unlistened)
        )
        await callback.answer()
        return

    await show_review(callback.message, reviews, index=0, edit=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("review_nav_"))
async def review_nav(callback: CallbackQuery):
    uid     = callback.from_user.id
    index   = int(callback.data.split("_")[2])
    reviews = db.get_reviews_for_my_tracks(uid)

    await show_review(callback.message, reviews, index=index, edit=True)
    await callback.answer()


async def show_review(message, reviews: list, index: int, edit: bool = False):
    total    = len(reviews)
    r        = reviews[index]
    url      = r["url"]
    reaction = r["reaction"]
    review   = r["review"]

    emoji = "❤️ Лайк" if reaction == "like" else ("💔 Дизлайк" if reaction == "dislike" else "— без реакції")
    review_text = f"💬 <i>{review}</i>" if review else "💬 <i>Без відгуку</i>"
    short_url = url[:50] + "..." if len(url) > 50 else url

    text = (
        f"📋 <b>Відгук {index + 1} з {total}</b>\n\n"
        f"🔗 <a href='{url}'>{short_url}</a>\n\n"
        f"Реакція: {emoji}\n"
        f"{review_text}"
    )

    kb = reviews_navigation(index, total, r["track_id"])

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    uid        = callback.from_user.id
    stats      = db.get_user_stats(uid)
    unlistened = db.get_unlistened_count(uid)

    await callback.message.edit_text(
        f"📊 <b>Твоя статистика</b>\n\n"
        f"🎵 Додано треків: <b>{stats['total']}</b>\n"
        f"👂 Прослухано іншими: <b>{stats['listened']}</b>\n"
        f"❤️ Лайків: <b>{stats['likes']}</b>\n"
        f"💔 Дизлайків: <b>{stats['dislikes']}</b>\n\n"
        f"🎧 Ти прослухав: <b>{stats['my_listened']}</b> треків",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


async def main():
    db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
