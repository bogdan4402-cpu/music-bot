from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(unlistened: int) -> InlineKeyboardMarkup:
    listen_label = f"🎧 Слухати треки ({unlistened})" if unlistened > 0 else "🎧 Нових треків немає"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати трек", callback_data="add_track")],
        [InlineKeyboardButton(text=listen_label, callback_data="listen_next")],
        [InlineKeyboardButton(text="📋 Переглянути відгуки", callback_data="view_reviews")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel")]
    ])


def reaction_keyboard(track_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк",    callback_data=f"like_{track_id}"),
            InlineKeyboardButton(text="💔 Дизлайк", callback_data=f"dislike_{track_id}"),
        ],
        [InlineKeyboardButton(text="⏭ Пропустити трек", callback_data=f"skip_track_{track_id}")],
    ])


def skip_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустити відгук", callback_data="skip_review")]
    ])


def reviews_navigation(track_index: int, total: int, track_id: int) -> InlineKeyboardMarkup:
    buttons = []
    nav = []
    if track_index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"review_nav_{track_index - 1}"))
    if track_index < total - 1:
        nav.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"review_nav_{track_index + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
