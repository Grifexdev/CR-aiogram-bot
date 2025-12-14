from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from utils.cr_api import cr_api
from config import CLAN_TAG
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = Router()


class BroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_photo = State()
    waiting_for_caption = State()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Отправить сообщение", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="📸 Отправить фото", callback_data="admin_photo")
        ],
        [
            InlineKeyboardButton(text="⚔️ Напомнить о КВ", callback_data="admin_war_remind"),
            InlineKeyboardButton(text="🔔 Напомнить неактивным", callback_data="admin_inactive")
        ],
        [
            InlineKeyboardButton(text="👥 Управление админами", callback_data="admin_manage"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")
        ]
    ])
    return keyboard


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Открыть админ-панель"""
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    text = (
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery):
    """Закрыть админ-панель"""
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Начать отправку сообщения"""
    await callback.message.edit_text(
        "📢 <b>Отправка сообщения</b>\n\n"
        "Отправьте текст сообщения, которое хотите разослать всем участникам.\n"
        "Используйте /cancel для отмены.",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.answer()


@router.message(BroadcastState.waiting_for_message)
async def admin_broadcast_process(message: Message, state: FSMContext):
    """Обработка сообщения для рассылки"""
    text = message.text or message.caption or ""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить всем", callback_data=f"broadcast_confirm_all"),
            InlineKeyboardButton(text="👥 Только с ником", callback_data=f"broadcast_confirm_nickname")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
    ])
    
    await state.update_data(broadcast_text=text, broadcast_photo=None)
    await message.answer(
        f"📝 <b>Предпросмотр сообщения:</b>\n\n{text}\n\n"
        f"Выберите, кому отправить:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("broadcast_confirm_"))
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext):
    """Отправить рассылку"""
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    send_to_all = callback.data == "broadcast_confirm_all"
    
    await callback.message.edit_text("⏳ Отправляю сообщения...")
    
    if send_to_all:
        users = db.get_all_users()
    else:
        users = db.get_users_with_royale_info()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            user_id = user["telegram_id"]
            mention = f"@{user.get('username', '')}" if user.get("username") else f"<a href='tg://user?id={user_id}'>{user.get('royale_nickname', 'Игрок')}</a>"
            
            message_text = f"{mention}\n\n{text}"
            
            await callback.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML"
            )
            sent += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке пользователю {user_id}: {e}")
            failed += 1
    
    await callback.message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Отменить рассылку"""
    await callback.message.edit_text("❌ Рассылка отменена.")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_photo")
async def admin_photo_start(callback: CallbackQuery, state: FSMContext):
    """Начать отправку фото"""
    await callback.message.edit_text(
        "📸 <b>Отправка фото</b>\n\n"
        "Отправьте фото, которое хотите разослать.\n"
        "Используйте /cancel для отмены.",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_for_photo)
    await callback.answer()


@router.message(BroadcastState.waiting_for_photo, F.photo)
async def admin_photo_process(message: Message, state: FSMContext):
    """Обработка фото"""
    photo = message.photo[-1]  # Берем фото наибольшего размера
    file_id = photo.file_id
    
    await state.update_data(broadcast_photo=file_id)
    await message.answer(
        "📝 Теперь отправьте подпись к фото (или отправьте /skip чтобы без подписи):"
    )
    await state.set_state(BroadcastState.waiting_for_caption)


@router.message(BroadcastState.waiting_for_caption)
async def admin_photo_caption(message: Message, state: FSMContext):
    """Обработка подписи к фото"""
    caption = message.text if message.text != "/skip" else ""
    data = await state.get_data()
    file_id = data.get("broadcast_photo")
    await state.update_data(broadcast_caption=caption)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить всем", callback_data="photo_confirm_all"),
            InlineKeyboardButton(text="👥 Только с ником", callback_data="photo_confirm_nickname")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="photo_cancel")]
    ])
    
    await message.answer_photo(
        photo=file_id,
        caption=f"📝 <b>Предпросмотр:</b>\n\n{caption}\n\nВыберите, кому отправить:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("photo_confirm_"))
async def admin_photo_send(callback: CallbackQuery, state: FSMContext):
    """Отправить фото"""
    data = await state.get_data()
    file_id = data.get("broadcast_photo")
    caption = data.get("broadcast_caption", "")
    send_to_all = callback.data == "photo_confirm_all"
    
    await callback.message.edit_text("⏳ Отправляю фото...")
    
    if send_to_all:
        users = db.get_all_users()
    else:
        users = db.get_users_with_royale_info()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            user_id = user["telegram_id"]
            mention = f"@{user.get('username', '')}" if user.get("username") else f"<a href='tg://user?id={user_id}'>{user.get('royale_nickname', 'Игрок')}</a>"
            
            photo_caption = f"{mention}\n\n{caption}" if caption else mention
            
            await callback.bot.send_photo(
                chat_id=user_id,
                photo=file_id,
                caption=photo_caption,
                parse_mode="HTML"
            )
            sent += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке фото пользователю {user_id}: {e}")
            failed += 1
    
    await callback.message.edit_text(
        f"✅ Рассылка фото завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_war_remind")
async def admin_war_remind(callback: CallbackQuery):
    """Напомнить всем о начале КВ"""
    if not CLAN_TAG:
        await callback.answer("❌ Тег клана не настроен", show_alert=True)
        return
    
    await callback.message.edit_text("⏳ Проверяю статус войны...")
    
    war_data = await cr_api.get_clan_war(CLAN_TAG)
    if not war_data:
        await callback.message.edit_text("❌ Нет активной клановой войны.")
        await callback.answer()
        return
    
    state = war_data.get("state", "")
    if state == "collectionDay":
        message_text = (
            "📦 <b>Напоминание о клановой войне!</b>\n\n"
            "Начался день сбора карт! Не забудьте собрать карты для участия в войне."
        )
    elif state == "warDay":
        message_text = (
            "⚔️ <b>Напоминание о клановой войне!</b>\n\n"
            "Начался день битвы! Не забудьте сделать атаки в клановой войне!"
        )
    else:
        await callback.message.edit_text("❌ Война не активна.")
        await callback.answer()
        return
    
    users = db.get_users_with_royale_info()
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await callback.bot.send_message(
                chat_id=user["telegram_id"],
                text=message_text,
                parse_mode="HTML"
            )
            sent += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")
            failed += 1
    
    await callback.message.edit_text(
        f"✅ Напоминания отправлены!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_inactive")
async def admin_inactive_remind(callback: CallbackQuery):
    """Напомнить неактивным участникам об атаках"""
    if not CLAN_TAG:
        await callback.answer("❌ Тег клана не настроен", show_alert=True)
        return
    
    await callback.message.edit_text("⏳ Проверяю участников войны...")
    
    war_data = await cr_api.get_clan_war(CLAN_TAG)
    if not war_data or war_data.get("state") != "warDay":
        await callback.message.edit_text("❌ Сейчас не день битвы в клановой войне.")
        await callback.answer()
        return
    
    # Получаем участников войны
    participants = war_data.get("clan", {}).get("participants", [])
    participants_dict = {p.get("tag", "").replace("#", "").upper(): p for p in participants}
    
    # Получаем пользователей с указанными тегами
    users = db.get_users_with_royale_info()
    
    inactive_users = []
    for user in users:
        user_tag = user.get("royale_tag", "").replace("#", "").upper()
        participant = participants_dict.get(user_tag)
        
        if participant:
            attacks = participant.get("battlesPlayed", 0)
            max_attacks = participant.get("battlesPlayed", 0) + participant.get("battlesRemaining", 0)
            
            if attacks < max_attacks:
                inactive_users.append((user, attacks, max_attacks))
    
    if not inactive_users:
        await callback.message.edit_text("✅ Все участники выполнили атаки!")
        await callback.answer()
        return
    
    sent = 0
    failed = 0
    
    for user, attacks, max_attacks in inactive_users:
        try:
            user_id = user["telegram_id"]
            nickname = user.get("royale_nickname", "Игрок")
            mention = f"@{user.get('username', '')}" if user.get("username") else f"<a href='tg://user?id={user_id}'>{nickname}</a>"
            
            remaining = max_attacks - attacks
            message_text = (
                f"⚔️ {mention}\n\n"
                f"Напоминание: у вас осталось <b>{remaining}</b> атак в клановой войне!\n"
                f"Не забудьте сделать атаки!"
            )
            
            await callback.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML"
            )
            sent += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")
            failed += 1
    
    await callback.message.edit_text(
        f"✅ Напоминания отправлены неактивным участникам!\n\n"
        f"👥 Найдено неактивных: {len(inactive_users)}\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_manage")
async def admin_manage(callback: CallbackQuery):
    """Управление админами"""
    text = "👥 <b>Управление админами</b>\n\n"
    text += "Отправьте команду:\n"
    text += "/addadmin &lt;telegram_id&gt; - Добавить админа\n"
    text += "/removeadmin &lt;telegram_id&gt; - Удалить админа\n"
    text += "/listadmins - Список админов"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message):
    """Добавить админа"""
    from config import SUPER_ADMIN_ID
    
    # Проверяем, что команду использует супер-админ
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    user_id = None
    target_user = None
    username = None
    
    # Проверяем, есть ли аргумент (тег)
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        # Пытаемся найти пользователя по тегу
        tag = parts[1].strip()
        user_data = db.get_user_by_royale_tag(tag)
        
        if not user_data:
            await message.answer(
                f"❌ Пользователь с тегом <code>{tag}</code> не найден в базе данных.\n\n"
                f"Убедитесь, что пользователь указал свой ник командой /setnick",
                parse_mode="HTML"
            )
            return
        
        user_id = user_data["telegram_id"]
        username = user_data.get("royale_nickname", "N/A")
        
    # Если нет аргумента, проверяем ответ на сообщение
    elif message.reply_to_message:
        target_user = message.reply_to_message.from_user
        user_id = target_user.id
        
        # Проверяем, не является ли пользователь ботом
        if target_user.is_bot:
            await message.answer("❌ Нельзя добавить бота в админы.")
            return
        
        username = f"@{target_user.username}" if target_user.username else target_user.first_name
        
        # Добавляем пользователя в базу данных, если его там нет
        db.add_user(user_id, target_user.username)
    
    else:
        await message.answer(
            "❌ Укажите тег игрока или ответьте на сообщение пользователя.\n\n"
            "<b>Использование:</b>\n"
            "• <code>/addadmin 2PP</code> - добавить по тегу\n"
            "• Ответить на сообщение командой <code>/addadmin</code> - добавить того, кому ответили",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, не является ли пользователь уже админом
    if db.is_admin(user_id):
        await message.answer(
            f"⚠️ Пользователь <b>{username}</b> (ID: {user_id}) уже является администратором.",
            parse_mode="HTML"
        )
        return
    
    # Добавляем пользователя в админы
    db.add_admin(user_id, message.from_user.id)
    
    royale_tag = ""
    if user_data:
        royale_tag = f" #{user_data.get('royale_tag', '')}"
    
    await message.answer(
        f"✅ Пользователь <b>{username}</b>{royale_tag} (ID: {user_id}) добавлен в админы.",
        parse_mode="HTML"
    )


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message):
    """Удалить админа"""
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите telegram_id пользователя.\nПример: /removeadmin 123456789")
        return
    
    try:
        user_id = int(parts[1])
        db.remove_admin(user_id)
        await message.answer(f"✅ Пользователь {user_id} удален из админов.")
    except ValueError:
        await message.answer("❌ Неверный формат telegram_id.")


@router.message(Command("listadmins"))
async def cmd_listadmins(message: Message):
    """Список админов"""
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    admins = db.get_all_admins()
    if not admins:
        await message.answer("📋 Список админов пуст.")
        return
    
    text = "👥 <b>Список админов:</b>\n\n"
    for admin_id in admins:
        user = db.get_user(admin_id)
        if user:
            text += f"• {user.get('royale_nickname', 'N/A')} (@{user.get('username', 'N/A')}) - {admin_id}\n"
        else:
            text += f"• ID: {admin_id}\n"
    
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Статистика"""
    total_users = len(db.get_all_users())
    users_with_nick = len(db.get_users_with_royale_info())
    admins_count = len(db.get_all_admins())
    
    text = (
        "📊 <b>Статистика бота:</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🎮 С указанным ником: {users_with_nick}\n"
        f"👑 Админов: {admins_count}"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отменить текущее действие"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Действие отменено.")
    else:
        await message.answer("ℹ️ Нет активных действий для отмены.")

