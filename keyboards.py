from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(unlistened: int) -> InlineKeyboardMarkup:
    label = f"🎧 Слушать треки ({unlistened})" if unlistened > 0 else "🎧 Новых треков нет"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data="listen_next")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
    ])


def reaction_keyboard(track_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❤️ Лайк",    callback_data=f"like_{track_id}"),
        InlineKeyboardButton(text="💔 Дизлайк", callback_data=f"dislike_{track_id}"),
    ]])


def skip_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить отзыв", callback_data="skip_review")
    ]])
