from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_kb():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Начать розыгрыш"), KeyboardButton(text="🏁 Завершить розыгрыш")],
            [KeyboardButton(text="📣 Сделать объявление"), KeyboardButton(text="📊 Статистика розыгрыша")]
        ],
        resize_keyboard=True
    )
    return kb


def get_user_kb():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔢 Мое число"), KeyboardButton(text="ℹ️ Задать вопрорс")]
        ],
        resize_keyboard=True
    )
    return kb


def get_cancel_kb():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return kb


def get_confirm_kb():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")
            ]
        ]
    )
    return kb

def get_confirm_message_kb():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes_message"),
                InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no_message")
            ]
        ]
    )
    return kb