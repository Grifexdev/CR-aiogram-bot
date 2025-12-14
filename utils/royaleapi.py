import aiohttp
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import re
from config import ROYALEAPI_BASE_URL


class RoyaleAPI:
    """Класс для работы с RoyaleAPI через веб-скрапинг"""
    
    def __init__(self):
        self.base_url = ROYALEAPI_BASE_URL
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def get_player_stats(self, player_tag: str) -> Optional[Dict]:
        """Получить расширенную статистику игрока с RoyaleAPI"""
        try:
            # Убираем # из тега
            clean_tag = player_tag.replace("#", "").upper()
            url = f"{self.base_url}/player/{clean_tag}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Парсим основную информацию
                        player_data = {}
                        
                        # Имя игрока
                        name_elem = soup.find('h1', class_=re.compile('player.*name', re.I))
                        if name_elem:
                            player_data['name'] = name_elem.get_text(strip=True)
                        
                        # Пытаемся найти трофеи в различных местах страницы
                        # Ищем все элементы с текстом, содержащим "trophies" или числа
                        all_text = soup.get_text()
                        trophies_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*(?:trophies|трофеев)', all_text, re.I)
                        if trophies_match:
                            player_data['trophies'] = int(trophies_match.group(1).replace(',', ''))
                        
                        # Ищем уровень
                        level_match = re.search(r'level\s*(\d+)|уровень\s*(\d+)', all_text, re.I)
                        if level_match:
                            player_data['level'] = int(level_match.group(1) or level_match.group(2))
                        
                        # Ищем победы
                        wins_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*(?:wins|побед)', all_text, re.I)
                        if wins_match:
                            player_data['wins'] = int(wins_match.group(1).replace(',', ''))
                        
                        player_data['tag'] = f"#{clean_tag}"
                        return player_data
                    return None
        except Exception as e:
            print(f"Ошибка при получении статистики игрока с RoyaleAPI: {e}")
            return None
    
    async def get_clan_war_stats(self, clan_tag: str) -> Optional[Dict]:
        """Получить статистику клановой войны"""
        try:
            clean_tag = clan_tag.replace("#", "").upper()
            url = f"{self.base_url}/clan/{clean_tag}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        war_data = {}
                        
                        # Ищем информацию о текущей войне
                        war_section = soup.find('section', class_=re.compile('war|война', re.I))
                        if war_section:
                            # Статус войны
                            status_elem = war_section.find(string=re.compile('Collection|Battle|Сбор|Битва', re.I))
                            if status_elem:
                                war_data['status'] = status_elem.get_text(strip=True)
                            
                            # Участники войны
                            participants = []
                            member_elems = war_section.find_all('div', class_=re.compile('member|участник', re.I))
                            for member_elem in member_elems:
                                name = member_elem.find(string=re.compile(r'\w+'))
                                if name:
                                    participants.append(name.get_text(strip=True))
                            
                            war_data['participants'] = participants
                        
                        return war_data
                    return None
        except Exception as e:
            print(f"Ошибка при получении статистики войны с RoyaleAPI: {e}")
            return None


royale_api = RoyaleAPI()

