import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import BOT_TOKEN, ADMIN_ID
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


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


# ── /start ───────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id

    if not db.is_allowed(uid) and not is_admin(uid):
        await message.answer("⛔️ У тебе немає доступу до цього бота.")
        return

    # Автоматично додаємо адміна якщо його ще немає
    if is_admin(uid) and not db.is_allowed(uid):
        db.add_user(uid, message.from_user.full_name)

    unlistened = db.get_unlistened_count(uid)
    await message.answer(
        "👋 Привіт!\n\n"
        "Тут можна ділитися треками та слухати музику один одного.\n\n"
        f"Непрослуханих треків: <b>{unlistened}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )


# ── Головне меню ─────────────────────────────────────────────

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


# ── Адмін команди ────────────────────────────────────────────

@dp.message(Command("adduser"))
async def cmd_adduser(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Використання: /adduser ID Ім'я\n"
            "Приклад: /adduser 123456789 Богдан"
        )
        return

    user_id = int(parts[1])
    name    = " ".join(parts[2:])
    db.add_user(user_id, name)
    await message.answer(f"✅ Користувач <b>{name}</b> ({user_id}) додан.", parse_mode="HTML")


@dp.message(Command("removeuser"))
async def cmd_removeuser(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Використання: /removeuser ID")
        return

    user_id = int(parts[1])
    db.remove_user(user_id)
    await message.answer(f"✅ Користувач {user_id} видалений.")


@dp.message(Command("addpair"))
async def cmd_addpair(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Використання: /addpair ID_A ID_B\n"
            "Приклад: /addpair 123456789 987654321\n"
            "Після цього A бачить треки B і навпаки."
        )
        return

    user_a = int(parts[1])
    user_b = int(parts[2])
    db.add_pair(user_a, user_b)
    await message.answer(f"✅ Пара {user_a} ↔ {user_b} створена.")


@dp.message(Command("removepair"))
async def cmd_removepair(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Використання: /removepair ID_A ID_B")
        return

    user_a = int(parts[1])
    user_b = int(parts[2])
    db.remove_pair(user_a, user_b)
    await message.answer(f"✅ Пара {user_a} ↔ {user_b} видалена.")


@dp.message(Command("users"))
async def cmd_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = db.get_all_users()
    if not users:
        await message.answer("📋 Користувачів немає.")
        return

    text = "📋 <b>Користувачі:</b>\n\n"
    for u in users:
        text += f"• <b>{u['name']}</b> — <code>{u['id']}</code>\n"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("pairs"))
async def cmd_pairs(message: Message):
    if not is_admin(message.from_user.id):
        return

    pairs = db.get_all_pairs()
    users = {u["id"]: u["name"] for u in db.get_all_users()}

    if not pairs:
        await message.answer("📋 Пар немає.")
        return

    text = "🔗 <b>Активні пари:</b>\n\n"
    for p in pairs:
        name1 = users.get(p["u1"], f"id{p['u1']}")
        name2 = users.get(p["u2"], f"id{p['u2']}")
        text += f"• <b>{name1}</b> ↔ <b>{name2}</b>\n"

    await message.answer(text, parse_mode="HTML")

    
# ── Додати трек ──────────────────────────────────────────────

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


# ... (початок коду без змін)

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

    # Спрощена перевірка для Spotify та YouTube
    if "spotify.com" not in url and "youtu" not in url:
        await message.answer(
            "⚠️ Підтримуються тільки посилання Spotify або YouTube",
            reply_markup=cancel_keyboard()
        )
        return

    db.add_track(url, added_by=uid)
    await state.clear()

    platform   = platform_label(url)
    unlistened = db.get_unlistened_count(uid)

    await message.answer(
        f"✅ Трек додано! {platform}\n\n🔗 <code>{url}</code>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )

    # ВИПРАВЛЕНО: Визначаємо sender один раз перед циклом
    sender = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name

    for other_uid in db.get_all_users_except(uid):
        try:
            count = db.get_unlistened_count(other_uid)
            await bot.send_message(
                other_uid,
                f"🎵 Новий трек від <b>{sender}</b>!\n"
                f"{platform} <a href='{url}'>Відкрити</a>\n\n"
                f"Непрослуханих треків: <b>{count}</b>",
                parse_mode="HTML",
                reply_markup=main_menu(count)
            )
        except Exception:
            pass

# ... (код до listen_next без змін)

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

    # Отримуємо ім'я автора
    author_row = next((u for u in db.get_all_users() if u["id"] == track["added_by"]), None)
    author_name = author_row["name"] if author_row else f"id{track['added_by']}"

    # ВИПРАВЛЕНО: Залишено лише один виклик edit_text та answer
    await callback.message.edit_text(
        f"🎧 <b>Новий трек від {author_name}</b>\n\n"
        f"{platform}\n"
        f"🔗 <a href='{url}'>Натисни щоб відкрити трек</a>\n\n"
        f"📋 Залишилось непрослуханих: <b>{max(0, unlistened - 1)}</b>\n\n"
        "Послухай та постав реакцію 👇",
        parse_mode="HTML",
        reply_markup=reaction_keyboard(track_id),
        disable_web_page_preview=False
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid        = callback.from_user.id
    unlistened = db.get_unlistened_count(uid)
    await callback.message.edit_text(
        f"❌ Скасовано.\n\nНепрослуханих треків: <b>{unlistened}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(unlistened)
    )
    await callback.answer()


# ── Слухати трек ─────────────────────────────────────────────

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

    author_row = next((u for u in db.get_all_users() if u["id"] == track["added_by"]), None)
    author_name = author_row["name"] if author_row else f"id{track['added_by']}"

    await callback.message.edit_text(
        f"🎧 <b>Новий трек від {author_name}</b>\n\n"
        f"{platform}\n"
        f"🔗 <a href='{url}'>Натисни щоб відкрити трек</a>\n\n"
        f"📋 Залишилось непрослуханих: <b>{max(0, unlistened - 1)}</b>\n\n"
        "Послухай та постав реакцію 👇",
        parse_mode="HTML",
        reply_markup=reaction_keyboard(track_id),
        disable_web_page_preview=False
    )
    await callback.answer()

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


# ── Пропустити трек ──────────────────────────────────────────

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


# ── Реакція ──────────────────────────────────────────────────

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


# ── Пропустити відгук ────────────────────────────────────────

@dp.callback_query(F.data == "skip_review", ReviewState.waiting)
async def skip_review(callback: CallbackQuery, state: FSMContext):
    uid      = callback.from_user.id
    data     = await state.get_data()
    track_id = data["current_track_id"]

    db.mark_listened(track_id, uid)
    await state.clear()

    # Автоматично показуємо наступний трек
    track = db.get_next_unlistened(uid)
    if track:
        next_id    = track["id"]
        url        = track["url"]
        unlistened = db.get_unlistened_count(uid)
        platform   = platform_label(url)
        await state.update_data(current_track_id=next_id)
        await callback.message.edit_text(
            f"🎧 <b>Наступний трек</b>\n\n"
            f"{platform}\n"
            f"🔗 <a href='{url}'>Натисни щоб відкрити трек</a>\n\n"
            f"📋 Залишилось непрослуханих: <b>{max(0, unlistened - 1)}</b>\n\n"
            "Послухай та постав реакцію 👇",
            parse_mode="HTML",
            reply_markup=reaction_keyboard(next_id),
            disable_web_page_preview=False
        )
    else:
        await callback.message.edit_text(
            "🎉 Усі треки прослухано!",
            reply_markup=main_menu(0)
        )
    await callback.answer()


# ── Текст відгуку ────────────────────────────────────────────

@dp.message(ReviewState.waiting)
async def receive_review(message: Message, state: FSMContext):
    uid = message.from_user.id
    data = await state.get_data()
    track_id = data["current_track_id"]
    reaction = data.get("reaction", "like")

    # Зберігаємо в базу хоча б позначку, що відгук був
    review_content = message.text if message.text else "[Голосове повідомлення]"
    db.save_review(track_id, uid, review_content)
    db.mark_listened(track_id, uid)
    await state.clear()

    emoji = "❤️" if reaction == "like" else "💔"
    track = db.get_track_by_id(track_id)

    # Відправка автору
    if track and track["added_by"] != uid:
        try:
            target_id = track["added_by"]
            sender = f"@{message.from_user.username}" if message.from_user.username else f"ID: {uid}"
            caption = (
                f"📝 Відгук від {sender}\n"
                f"{emoji} {'Лайк' if reaction == 'like' else 'Дизлайк'}"
            )

            if message.voice:
                # ВІДПРАВЛЯЄМО ГОЛОСОВЕ
                await bot.send_voice(target_id, message.voice.file_id, caption=caption)
            elif message.text:
                # ВІДПРАВЛЯЄМО ТЕКСТ
                await bot.send_message(target_id, f"{caption}\n\n💬 {message.text}")
            else:
                # ЯКЩО СТІКЕР ЧИ ІНШЕ
                await bot.send_message(target_id, caption + "\n(Надіслано медіа-файл)")
        
        except Exception as e:
            logging.error(f"Помилка пересилки: {e}")

    # Перехід до наступного треку
    next_track = db.get_next_unlistened(uid)
    if next_track:
        next_id = next_track["id"]
        url = next_track["url"]
        await state.update_data(current_track_id=next_id)
        await state.set_state(ReviewState.waiting)
        await message.answer(
            f"✅ Відгук надіслано!\n\n🎧 <b>Наступний трек:</b>\n{url}",
            parse_mode="HTML",
            reply_markup=reaction_keyboard(next_id)
        )
    else:
        await message.answer("✅ Відгук надіслано!\n\n🎉 Це був останній трек.", reply_markup=main_menu(0))


    # Автоматично показуємо наступний трек
    next_track = db.get_next_unlistened(uid)
    if next_track:
        next_id    = next_track["id"]
        url        = next_track["url"]
        unlistened = db.get_unlistened_count(uid)
        platform   = platform_label(url)
        await state.update_data(current_track_id=next_id)
        await state.set_state(ReviewState.waiting)
        await message.answer(
            f"✅ Відгук збережено {emoji}\n\n"
            f"🎧 <b>Наступний трек</b>\n\n"
            f"{platform}\n"
            f"🔗 <a href='{url}'>Натисни щоб відкрити трек</a>\n\n"
            f"📋 Залишилось непрослуханих: <b>{max(0, unlistened - 1)}</b>\n\n"
            "Послухай та постав реакцію 👇",
            parse_mode="HTML",
            reply_markup=reaction_keyboard(next_id),
            disable_web_page_preview=False
        )
    else:
        await message.answer(
            f"✅ Відгук збережено {emoji}\n\n🎉 Усі треки прослухано!",
            reply_markup=main_menu(0)
        )


# ── Перегляд відгуків ────────────────────────────────────────

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

    emoji       = "❤️ Лайк" if reaction == "like" else ("💔 Дизлайк" if reaction == "dislike" else "— без реакції")
    review_text = f"💬 <i>{review}</i>" if review else "💬 <i>Без відгуку</i>"
    short_url   = url[:50] + "..." if len(url) > 50 else url

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


# ── Статистика ───────────────────────────────────────────────

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


# ── Запуск ───────────────────────────────────────────────────

async def main():
    db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


