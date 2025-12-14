from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from utils.cr_api import cr_api
from config import CLAN_TAG
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("setrole"))
async def cmd_setrole(message: Message):
    """Назначить роль на основе ника в рояле"""
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат команды.\n"
            "Использование: /setrole &lt;ник_в_рояле&gt; &lt;роль&gt;\n"
            "Роли: leader, coLeader, elder, member\n\n"
            "Пример: /setrole PlayerName elder",
            parse_mode="HTML"
        )
        return
    
    royale_nickname = parts[1]
    role = parts[2].lower()
    
    if role not in ["leader", "coleader", "elder", "member"]:
        await message.answer("❌ Неверная роль. Доступные: leader, coLeader, elder, member")
        return
    
    # Ищем пользователя по нику в рояле
    users = db.get_users_with_royale_info()
    found_user = None
    
    for user in users:
        if user.get("royale_nickname", "").lower() == royale_nickname.lower():
            found_user = user
            break
    
    if not found_user:
        await message.answer(f"❌ Пользователь с ником '{royale_nickname}' не найден в базе данных.")
        return
    
    # Устанавливаем роль
    db.set_user_role(found_user["telegram_id"], role)
    
    await message.answer(
        f"✅ Роль установлена!\n\n"
        f"👤 Пользователь: {found_user.get('royale_nickname')} #{found_user.get('royale_tag')}\n"
        f"👑 Роль: {role}"
    )


@router.message(Command("syncroles"))
async def cmd_syncroles(message: Message):
    """Синхронизировать роли с кланом"""
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    if not CLAN_TAG:
        await message.answer("❌ Тег клана не настроен.")
        return
    
    await message.answer("⏳ Синхронизирую роли с кланом...")
    
    # Получаем информацию о клане
    clan_data = await cr_api.get_clan_info(CLAN_TAG)
    if not clan_data:
        await message.answer("❌ Не удалось получить информацию о клане.")
        return
    
    # Получаем участников клана
    members_data = await cr_api.get_clan_members(CLAN_TAG)
    if not members_data:
        await message.answer("❌ Не удалось получить список участников клана.")
        return
    
    # Создаем словарь: тег -> роль
    clan_roles = {}
    for member in members_data:
        tag = member.get("tag", "").replace("#", "").upper()
        role = member.get("role", "member").lower()
        clan_roles[tag] = role
    
    # Обновляем роли в базе данных
    users = db.get_users_with_royale_info()
    updated = 0
    
    for user in users:
        user_tag = user.get("royale_tag", "").replace("#", "").upper()
        if user_tag in clan_roles:
            db.set_user_role(user["telegram_id"], clan_roles[user_tag])
            updated += 1
    
    await message.answer(
        f"✅ Синхронизация завершена!\n\n"
        f"🔄 Обновлено ролей: {updated}"
    )

