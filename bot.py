import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers import commands, war_commands
from utils.war_reminders import WarReminderService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальный сервис напоминаний (будет инициализирован в main)
war_reminder_service: WarReminderService = None


async def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Проверьте файл .env")
        return
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Инициализация сервиса напоминаний
    global war_reminder_service
    war_reminder_service = WarReminderService(bot)
    war_reminder_service.start()
    
    # Передаем сервис в модуль war_commands
    import handlers.war_commands as wc
    wc.war_reminder_service = war_reminder_service
    
    # Регистрация роутеров
    dp.include_router(commands.router)
    dp.include_router(war_commands.router)
    
    # Запуск бота
    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        war_reminder_service.stop()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

