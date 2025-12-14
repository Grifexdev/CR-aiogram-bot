from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from utils.cr_api import cr_api
from utils.formatters import format_war_info, format_player_war_stats
from config import CLAN_TAG

router = Router()

# Сервис напоминаний будет установлен из bot.py
war_reminder_service = None


@router.message(Command("war"))
async def cmd_war(message: Message):
    """Обработчик команды /war - информация о текущей войне"""
    if not CLAN_TAG:
        await message.answer(
            "❌ Тег клана не настроен. Обратитесь к администратору бота.",
            parse_mode="HTML"
        )
        return
    
    await message.answer("⏳ Загружаю информацию о войне...")
    
    war_data = await cr_api.get_clan_war(CLAN_TAG)
    if war_data:
        text = format_war_info(war_data)
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(
            "❌ Нет активной клановой войны или не удалось получить информацию.",
            parse_mode="HTML"
        )


@router.message(Command("warstats"))
async def cmd_warstats(message: Message):
    """Обработчик команды /warstats - статистика игрока в войне"""
    if not CLAN_TAG:
        await message.answer(
            "❌ Тег клана не настроен. Обратитесь к администратору бота.",
            parse_mode="HTML"
        )
        return
    
    # Получаем тег игрока из команды
    command_parts = message.text.split()
    
    if len(command_parts) < 2:
        await message.answer(
            "❌ Укажите тег игрока.\n"
            "Пример: /warstats 2PP или /warstats #2PP",
            parse_mode="HTML"
        )
        return
    
    player_tag = command_parts[1].replace("#", "")
    
    await message.answer("⏳ Загружаю статистику игрока в войне...")
    
    war_data = await cr_api.get_clan_war(CLAN_TAG)
    if war_data:
        text = format_player_war_stats(war_data, player_tag)
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(
            "❌ Нет активной клановой войны или не удалось получить информацию.",
            parse_mode="HTML"
        )


@router.message(Command("remind"))
async def cmd_remind(message: Message):
    """Обработчик команды /remind - подписаться на напоминания"""
    if not war_reminder_service:
        await message.answer("❌ Сервис напоминаний не инициализирован.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, указан ли тег игрока
    command_parts = message.text.split()
    player_tag = None
    
    if len(command_parts) >= 2:
        player_tag = command_parts[1].replace("#", "")
    
    war_reminder_service.subscribe(user_id, chat_id, player_tag)
    
    text = "✅ Вы подписаны на напоминания об атаках в клановой войне!\n\n"
    if player_tag:
        text += f"📌 Отслеживается игрок: #{player_tag}"
    else:
        text += "📌 Вы будете получать общие напоминания о войне"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("unremind"))
async def cmd_unremind(message: Message):
    """Обработчик команды /unremind - отписаться от напоминаний"""
    if not war_reminder_service:
        await message.answer("❌ Сервис напоминаний не инициализирован.")
        return
    
    user_id = message.from_user.id
    
    if war_reminder_service.unsubscribe(user_id):
        await message.answer("❌ Вы отписаны от напоминаний об атаках в войне.")
    else:
        await message.answer("ℹ️ Вы не были подписаны на напоминания.")


@router.message(Command("remindnow"))
async def cmd_remindnow(message: Message):
    """Обработчик команды /remindnow - отправить напоминание сейчас"""
    if not war_reminder_service:
        await message.answer("❌ Сервис напоминаний не инициализирован.")
        return
    
    chat_id = message.chat.id
    
    # Проверяем, указан ли тег игрока
    command_parts = message.text.split()
    player_tag = None
    
    if len(command_parts) >= 2:
        player_tag = command_parts[1].replace("#", "")
    
    error = await war_reminder_service.send_manual_reminder(chat_id, player_tag)
    if error:
        await message.answer(error, parse_mode="HTML")

