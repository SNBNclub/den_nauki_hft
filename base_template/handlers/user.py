from aiogram.filters import Command, CommandStart
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from handlers.errors import safe_send_message
from keyboards.keyboards import get_admin_kb, get_user_kb, get_cancel_kb, get_confirm_kb, get_confirm_message_kb
from instance import bot, logger
from database.req import *

router = Router()


class BroadcastState(StatesGroup):
    waiting_for_message = State()


class NumberState(StatesGroup):
    waiting_for_number = State()

class QuestionState(StatesGroup):
    waiting_for_question = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(
            message.from_user.id,
            name=message.from_user.full_name,
            username=message.from_user.username
        )

    is_admin = await is_user_admin(message.from_user.id)

    if is_admin:
        await safe_send_message(
            bot,
            message,
            text=f"Здравствуйте, {message.from_user.full_name}! Вы вошли как администратор розыгрыша.",
            reply_markup=get_admin_kb()
        )
    else:
        await safe_send_message(
            bot,
            message,
            text=f"Здравствуйте, {message.from_user.full_name}! Добро пожаловать в розыгрыш.\n\n"
                 f"Правила просты: отправьте натуральное число. Побеждает участник, "
                 f"приславший минимальное уникальное число.",
            reply_markup=get_user_kb()
        )


@router.message(Command('admin'))
async def cmd_admin(message: Message):
    admin_ids = await get_admin_ids()

    if not admin_ids:
        await set_admin(message.from_user.id)
        await safe_send_message(
            bot,
            message,
            text="Вы назначены администратором розыгрыша!",
            reply_markup=get_admin_kb()
        )
        return

    if message.from_user.id in admin_ids:
        await safe_send_message(
            bot,
            message,
            text="Вы уже являетесь администратором розыгрыша.",
            reply_markup=get_admin_kb()
        )
    else:
        await safe_send_message(
            bot,
            message,
            text="У вас нет прав администратора розыгрыша."
        )


async def is_user_admin(user_id: int) -> bool:
    admin_ids = await get_admin_ids()
    return user_id in admin_ids


@router.message(F.text == "🎮 Начать розыгрыш")
async def start_raffle(message: Message):
    if not await is_user_admin(message.from_user.id):
        await safe_send_message(bot, message, text="У вас нет прав администратора.")
        return

    try:
        raffle_id = await create_raffle()
        await safe_send_message(
            bot,
            message,
            text=f"Розыгрыш #{raffle_id} успешно начат! Участники теперь могут отправлять свои числа."
        )

        async with async_session() as session:
            res = await session.execute(select(User))
            users = res.scalars().all()
            result = await session.execute(select(User).where(User.is_superuser == True))
            admins = result.scalars().all()
            admin_ids = [admin.id for admin in admins]

            for user in users:
                if user.id not in admin_ids:
                    try:
                        await safe_send_message(
                            bot,
                            user.id,
                            text="🎉 Внимание! Начался новый розыгрыш!\n\n"
                                "Отправьте натуральное число. Побеждает участник, приславший минимальное уникальное число."
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю {user.id}: {e}")

    except Error409:
        await safe_send_message(bot, message, text="Розыгрыш уже активен!")


@router.message(F.text == "🏁 Завершить розыгрыш")
async def end_raffle_cmd(message: Message):
    # Проверяем, является ли пользователь администратором
    if not await is_user_admin(message.from_user.id):
        await safe_send_message(bot, message, text="У вас нет прав администратора.")
        return

    raffle = await get_active_raffle()
    if not raffle:
        await safe_send_message(bot, message, text="В данный момент нет активного розыгрыша.")
        return

    await safe_send_message(
        bot,
        message,
        text=f"Вы уверены, что хотите завершить розыгрыш #{raffle.id}?",
        reply_markup=get_confirm_kb()
    )


@router.callback_query(F.data == "confirm_yes")
async def confirm_end_raffle(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return

    raffle = await get_active_raffle()
    if not raffle:
        await callback.answer("В данный момент нет активного розыгрыша.")
        await safe_send_message(bot, callback, text="В данный момент нет активного розыгрыша.")
        return

    winner_id, winning_number = await end_raffle(raffle.id)

    if winner_id is None:
        await safe_send_message(
            bot,
            callback,
            text=f"Розыгрыш #{raffle.id} завершен!\n\n"
                 f"К сожалению, не было отправлено ни одного уникального числа. Победитель не определен.",
            reply_markup=get_admin_kb()
        )
    else:
        winner = await get_user(winner_id)
        winner_name = winner.name if winner else f"Пользователь {winner_id}"
        winner_username = f"@{winner.username}" if winner and winner.username else ""

        # Сообщение для администратора
        await safe_send_message(
            bot,
            callback,
            text=f"Розыгрыш #{raffle.id} завершен!\n\n"
                 f"Победитель: {winner_name} {winner_username} (ID: {winner_id})\n"
                 f"Выигрышное число: {winning_number} (минимальное уникальное)",
            reply_markup=get_admin_kb()
        )

        # Уведомляем всех участников о результатах розыгрыша
        participants = await get_raffle_participants(raffle.id)
        for participant_id in participants:
            try:
                if participant_id == winner_id:
                    await safe_send_message(
                        bot,
                        participant_id,
                        text=f"🎉 Поздравляем! Вы победили в розыгрыше #{raffle.id}!\n\n"
                             f"Ваше число {winning_number} оказалось минимальным уникальным."
                    )
                else:
                    await safe_send_message(
                        bot,
                        participant_id,
                        text=f"Розыгрыш #{raffle.id} завершен.\n\n"
                             f"К сожалению, вы не выиграли. Победило число {winning_number}."
                    )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю {participant_id}: {e}")

    await callback.answer()


@router.callback_query(F.data == "confirm_no")
async def cancel_end_raffle(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return

    await safe_send_message(
        bot,
        callback,
        text="Розыгрыш продолжается.",
        reply_markup=get_admin_kb()
    )
    await callback.answer()


@router.message(F.text == "📣 Сделать объявление")
async def broadcast_command(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if not await is_user_admin(message.from_user.id):
        await safe_send_message(bot, message, text="У вас нет прав администратора.")
        return

    await safe_send_message(
        bot,
        message,
        text="Введите сообщение, которое хотите отправить всем участникам розыгрыша:",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(BroadcastState.waiting_for_message)


@router.message(BroadcastState.waiting_for_message, F.text == "❌ Отмена")
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await safe_send_message(
        bot,
        message,
        text="Отправка объявления отменена.",
        reply_markup=get_admin_kb()
    )


@router.message(BroadcastState.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    # Сохраняем сообщение для рассылки
    await state.update_data(broadcast_message=message.text)

    await safe_send_message(
        bot,
        message,
        text=f"Вы собираетесь отправить следующее сообщение всем участникам:\n\n"
             f"{message.text}\n\n"
             f"Подтверждаете отправку?",
        reply_markup=get_confirm_message_kb()
    )


@router.callback_query(BroadcastState.waiting_for_message, F.data == "confirm_yes_message")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    # Получаем сохраненное сообщение
    data = await state.get_data()
    broadcast_message = data.get("broadcast_message")

    if not broadcast_message:
        await safe_send_message(
            bot,
            callback,
            text="Произошла ошибка: сообщение не найдено.",
            reply_markup=get_admin_kb()
        )
        await state.clear()
        return

    users = await get_all_users()
    admin_ids = await get_admin_ids()
    success_count = 0
    fail_count = 0

    for user in users:
        if user.id not in admin_ids:
            try:
                await safe_send_message(
                    bot,
                    user.id,
                    text=f"📣 Объявление от организатора розыгрыша:\n\n{broadcast_message}"
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {user.id}: {e}")
                fail_count += 1

    await safe_send_message(
        bot,
        callback,
        text=f"Сообщение успешно отправлено {success_count} участникам.\n"
             f"Не удалось отправить {fail_count} участникам.",
        reply_markup=get_admin_kb()
    )

    await state.clear()
    await callback.answer()


@router.callback_query(BroadcastState.waiting_for_message, F.data == "confirm_no_message")
async def cancel_confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_send_message(
        bot,
        callback,
        text="Отправка объявления отменена.",
        reply_markup=get_admin_kb()
    )
    await callback.answer()


@router.message(F.text == "🔢 Мое число")
async def enter_number_command(message: Message, state: FSMContext):
    # Проверяем, активен ли розыгрыш
    raffle = await get_active_raffle()
    if not raffle:
        await safe_send_message(
            bot,
            message,
            text="В данный момент нет активного розыгрыша. Дождитесь начала нового розыгрыша."
        )
        return

    await safe_send_message(
        bot,
        message,
        text="Введите натуральное число для участия в розыгрыше:",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(NumberState.waiting_for_number)


@router.message(NumberState.waiting_for_number, F.text == "❌ Отмена")
async def cancel_number_input(message: Message, state: FSMContext):
    await state.clear()
    await safe_send_message(
        bot,
        message,
        text="Ввод числа отменен.",
        reply_markup=get_user_kb()
    )


@router.message(NumberState.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    try:
        # Проверяем, что введено натуральное число
        number = int(message.text)
        if number <= 0:
            raise ValueError("Число должно быть положительным")

        # Сохраняем число в базе данных
        await add_raffle_entry(message.from_user.id, number)

        await safe_send_message(
            bot,
            message,
            text=f"Ваше число {number} принято для участия в розыгрыше!",
            reply_markup=get_user_kb()
        )

        # Отправляем сообщение администраторам
        admin_ids = await get_admin_ids()
        for admin_id in admin_ids:
            user_tag = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
            await safe_send_message(
                bot,
                admin_id,
                text=f"Участник {user_tag} (ID: {message.from_user.id}) отправил число: {number}"
            )

        await state.clear()
    except ValueError:
        await safe_send_message(
            bot,
            message,
            text="Пожалуйста, введите корректное натуральное число."
        )
    except Error404:
        await safe_send_message(
            bot,
            message,
            text="В данный момент нет активного розыгрыша.",
            reply_markup=get_user_kb()
        )
        await state.clear()


@router.message(F.text == "📊 Статистика розыгрыша")
async def get_raffle_stats(message: Message):
    if not await is_user_admin(message.from_user.id):
        await safe_send_message(bot, message, text="У вас нет прав администратора.")
        return

    raffle = await get_active_raffle()
    if not raffle:
        await safe_send_message(
            bot,
            message,
            text="В данный момент нет активного розыгрыша."
        )
        return

    entries = await get_user_entries(raffle.id)
    participants_count = len(set([entry.user_id for entry in entries]))

    numbers_stats = {}
    for entry in entries:
        if entry.number in numbers_stats:
            numbers_stats[entry.number] += 1
        else:
            numbers_stats[entry.number] = 1

    unique_numbers = [num for num, count in numbers_stats.items() if count == 1]
    min_unique = min(unique_numbers) if unique_numbers else None

    stats_text = f"Статистика розыгрыша #{raffle.id}:\n\n" \
                f"Всего участников: {participants_count}\n" \
                f"Всего чисел: {len(entries)}\n" \
                f"Уникальных чисел: {len([n for n, c in numbers_stats.items() if c == 1])}\n" \
                f"Повторяющихся чисел: {len([n for n, c in numbers_stats.items() if c > 1])}\n"

    if min_unique:
        stats_text += f"\nМинимальное уникальное число: {min_unique}"
    else:
        stats_text += "\nПока нет уникальных чисел."

    await safe_send_message(bot, message, text=stats_text)


@router.message(F.text == "ℹ️ Задать вопрорс")
async def show_info(message: Message, state: FSMContext):
    await safe_send_message(
        bot,
        message,
        text="Задайте свой вопрос, и я постараюсь на него ответить.",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(QuestionState.waiting_for_question)
    await message.answer("Задайте свой вопрос, и я постараюсь на него ответить.")


@router.message(QuestionState.waiting_for_question)
async def process_question(message: Message, state: FSMContext):
    try:
        question = message.text

        if message.text == "❌ Отмена":
            await state.clear()
            await safe_send_message(
                bot,
                message,
                text="Ввод вопроса отменен.",
                reply_markup=get_user_kb()
            )
            return

        await safe_send_message(
            bot,
            message,
            text="Ваш вопрос принят!",
            reply_markup=get_user_kb()
        )

        admin_ids = await get_admin_ids()
        for admin_id in admin_ids:
            user_tag = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
            await safe_send_message(
                bot,
                admin_id,
                text=f"Участник {user_tag} (ID: {message.from_user.id}) задал вопрос: {question}"
            )

        await state.clear()
    except Error404:
        await safe_send_message(
            bot,
            message,
            text="В данный момент нет активного розыгрыша.",
            reply_markup=get_user_kb()
        )
        await state.clear()

