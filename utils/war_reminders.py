from datetime import datetime, timedelta
from typing import Dict, List, Optional
from aiogram import Bot
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.cr_api import cr_api
from config import CLAN_TAG, WAR_REMINDER_HOURS
import logging

logger = logging.getLogger(__name__)


class WarReminderService:
    """Сервис для напоминаний об атаках в клановой войне"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.subscribers: Dict[int, Dict] = {}  # user_id -> {chat_id, player_tag}
        self._setup_scheduler()
    
    def _setup_scheduler(self):
        """Настройка расписания напоминаний"""
        # Напоминание каждый день в указанное время
        self.scheduler.add_job(
            self._check_and_send_reminders,
            CronTrigger(hour=WAR_REMINDER_HOURS, minute=0),
            id='war_reminder_daily'
        )
        
        # Дополнительное напоминание за 1 час до окончания дня войны (обычно в 23:00)
        self.scheduler.add_job(
            self._check_and_send_reminders,
            CronTrigger(hour=23, minute=0),
            id='war_reminder_final'
        )
    
    def start(self):
        """Запуск сервиса напоминаний"""
        self.scheduler.start()
        logger.info("Сервис напоминаний о войне запущен")
    
    def stop(self):
        """Остановка сервиса напоминаний"""
        self.scheduler.shutdown()
        logger.info("Сервис напоминаний о войне остановлен")
    
    def subscribe(self, user_id: int, chat_id: int, player_tag: Optional[str] = None):
        """Подписаться на напоминания"""
        self.subscribers[user_id] = {
            'chat_id': chat_id,
            'player_tag': player_tag
        }
        logger.info(f"Пользователь {user_id} подписан на напоминания")
    
    def unsubscribe(self, user_id: int):
        """Отписаться от напоминаний"""
        if user_id in self.subscribers:
            del self.subscribers[user_id]
            logger.info(f"Пользователь {user_id} отписан от напоминаний")
            return True
        return False
    
    def is_subscribed(self, user_id: int) -> bool:
        """Проверить, подписан ли пользователь"""
        return user_id in self.subscribers
    
    async def _check_and_send_reminders(self):
        """Проверить статус войны и отправить напоминания"""
        if not CLAN_TAG:
            return
        
        war_data = await cr_api.get_clan_war(CLAN_TAG)
        if not war_data:
            return
        
        # Проверяем, есть ли активная война
        state = war_data.get('state', '').lower()
        if state not in ['collectionDay', 'warDay']:
            return
        
        # Формируем сообщение
        message = self._format_war_reminder(war_data)
        
        # Отправляем напоминания всем подписчикам
        for user_id, sub_data in self.subscribers.items():
            try:
                chat_id = sub_data['chat_id']
                player_tag = sub_data.get('player_tag')
                
                # Если указан тег игрока, проверяем его статус
                if player_tag:
                    player_status = await self._check_player_war_status(war_data, player_tag)
                    if player_status:
                        message += f"\n\n{player_status}"
                
                await self.bot.send_message(chat_id, message, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
    
    def _format_war_reminder(self, war_data: Dict) -> str:
        """Форматирование напоминания о войне"""
        state = war_data.get('state', 'unknown')
        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        
        if state == 'collectionDay':
            state_text = "📦 <b>День сбора карт!</b>"
            reminder_text = "Не забудьте собрать карты для клановой войны!"
        elif state == 'warDay':
            state_text = "⚔️ <b>День битвы!</b>"
            reminder_text = "Не забудьте сделать атаки в клановой войне!"
        else:
            return ""
        
        text = f"{state_text}\n\n"
        text += f"🏰 <b>Ваш клан:</b> {clan.get('name', 'N/A')}\n"
        
        if opponent:
            text += f"⚔️ <b>Противник:</b> {opponent.get('name', 'N/A')}\n"
        
        text += f"\n{reminder_text}"
        
        # Информация о прогрессе
        if state == 'warDay':
            clan_crowns = war_data.get('clan', {}).get('crowns', 0)
            opponent_crowns = war_data.get('opponent', {}).get('crowns', 0)
            text += f"\n\n🏆 Счет: {clan_crowns} - {opponent_crowns}"
        
        return text
    
    async def _check_player_war_status(self, war_data: Dict, player_tag: str) -> Optional[str]:
        """Проверить статус игрока в войне"""
        try:
            # Ищем участника в списке участников войны
            participants = war_data.get('participants', [])
            clean_tag = player_tag.replace('#', '').upper()
            
            for participant in participants:
                tag = participant.get('tag', '').replace('#', '').upper()
                if tag == clean_tag:
                    name = participant.get('name', 'N/A')
                    attacks = participant.get('battlesPlayed', 0)
                    max_attacks = participant.get('battlesPlayed', 0) + participant.get('battlesRemaining', 0)
                    
                    if attacks < max_attacks:
                        remaining = max_attacks - attacks
                        return f"👤 <b>{name}</b>: Осталось атак: {remaining}/{max_attacks}"
                    else:
                        return f"👤 <b>{name}</b>: ✅ Все атаки выполнены!"
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса игрока: {e}")
        
        return None
    
    async def send_manual_reminder(self, chat_id: int, player_tag: Optional[str] = None):
        """Отправить напоминание вручную"""
        if not CLAN_TAG:
            return "❌ Тег клана не настроен"
        
        war_data = await cr_api.get_clan_war(CLAN_TAG)
        if not war_data:
            return "❌ Нет активной клановой войны"
        
        message = self._format_war_reminder(war_data)
        
        if player_tag:
            player_status = await self._check_player_war_status(war_data, player_tag)
            if player_status:
                message += f"\n\n{player_status}"
        
        await self.bot.send_message(chat_id, message, parse_mode="HTML")
        return None

