# Импорт библиотек

# Втроенные библиотеки
from pathlib import Path
import requests
import time
import hashlib
import tarfile
import io

# Сторонние библиотеки
import json5


# Определяем пути

SCRIPT_FILE = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_FILE.parent

# Директория пользовательских данных
DATA_DIR = Path(str(SCRIPT_DIR) + "/data")
if not DATA_DIR.is_dir():
	DATA_DIR.mkdir()

# Директория логов
LOGS_DIR = Path(str(DATA_DIR) + "/logs")
if not LOGS_DIR.is_dir():
	LOGS_DIR.mkdir()

SETTINGS_PATH = Path(str(DATA_DIR) + "/settings.json5") # Путь к настройкам
LAST_UPDATE_DATA__PATH = Path(str(DATA_DIR) + "/.lastUpdData") # Путь к дате последнего обновления

# Работа с пользовательскими данными
class data:
	@staticmethod
	def get_settings(): # Получение настроек
		if SETTINGS_PATH.is_file():
			with SETTINGS_PATH.open('r', encoding='utf-8') as settings_file:
				settings = json5.parse(settings_file.read())[0]
		else:
			settings = r"""{
	"url": "https://github.com/", // Full link to the network resource
	"updateTime": 43200, // How many times in seconds will the data be checked? default: 43200 (12 hours)
	"TGbot": {
		"enabled": false, // Enable or disable sending messages in Telegram. The value must be true or false
		"token": "", // Telegram bot token
		"chatId": 0, // The ID of the chat the bot will send the message to. If you don't know the ID, enter your profile ID. You can enable ID display in Advanced Settings > Experimental Settings in the Telegram client. The value must be an integer
		"text": "", // Text of the notification sent. If the value is not specified, the standard template will be used
	},
	"proxy": {
		"enabled_for_TGBot": false, // Enable or disable proxy for Telegram messages. The value must be true or false
		"enabled_for_webStorage": false, // Enable or disable proxy for web Storage (see param url). The value must be true or false
		"url": "", // URL to proxy. Eg. "http://my_login:my_password@127.0.0.1:8080". For SOCKS proxy you must install dependencies
	},
	
	/* Logging levels
	0: DEBUG
	1: INFO
	2: WARNING
	3: ERROR
	The value must be an integer */
	"log_level": 1,
}"""
			
			with SETTINGS_PATH.open('w', encoding='utf-8') as settings_file:
				settings_file.write(settings)
			settings = json5.parse(settings)[0]
		
		return settings
	
	@staticmethod
	def get_lastUpdateData(): # Получение даты последнего обновления
		lastUpdateData = {}
		if LAST_UPDATE_DATA__PATH.is_file():
			with LAST_UPDATE_DATA__PATH.open('rb') as lastUpdateData_file:
				lastUpdateData['hash'] = lastUpdateData_file.read(32)
				lastUpdateData['time'] = int(lastUpdateData_file.read(8).hex(), 16)
				lastUpdateData['success'] = True
		else:
			# Create file
			with LAST_UPDATE_DATA__PATH.open('wb'):
				pass
			
			lastUpdateData['success'] = False
		
		return lastUpdateData
	
	@staticmethod
	def update_lastUpdateData(hash: bytes, time: bytes | int): # Обновление даты последнего обновления
		if len(hash) != 32:
			raise ValueError
		
		if isinstance(time, int):
			time = time.to_bytes(8)
		elif isinstance(time, bytes) and len(time) != 8:
			raise ValueError
		
		# Update file
		with LAST_UPDATE_DATA__PATH.open('wb') as lastUpdateData_file:
			lastUpdateData_file.write(hash + time)

# Работа с Telegram API
class TelegramAPI:
	@staticmethod
	def sendMessage(token, chatId, text, proxy: dict): # Отправка сообщения
		url = f"https://api.telegram.org/bot{token}/sendMessage"
		for _ in range(3):
			success = False
			try:
				success = requests.post(url, data={'chat_id': chatId, 'text': text, "parse_mode": "Markdown"}, proxies=proxy['url'] if proxy['enabled'] else None).ok
				break
			except requests.exceptions.Any:
				loggerForFunc.new(4, "An error occurred while trying to send a Telegram message.")
				success = False
			except Exception as e:
				loggerForFunc.new(4, f"An unknown error occurred while trying to send a Telegram message: {e}")
				success = False
				break
		if not success:
			raise Exception

# Работа с логами
class logger:
	def __init__(self, log_level: int = 1, log_file_path: Path | str = "default"):
		# Уровень логирования
		self.log_level = log_level
		
		# Путь к логу
		if isinstance(log_file_path, str):
			if log_file_path == "default":
				self.log_file_type = "default"
				log_file_path = Path(str(LOGS_DIR)+'/'+time.strftime("%Y-%m-%d", time.localtime()))
			else:
				self.log_file_type = "custom"
				log_file_path = Path(str(LOGS_DIR)+'/'+log_file_path)
		else:
			self.log_file_type = "custom"
		
		self.log_file_path = Path(log_file_path)
	
	# Уровни логирования
	log_levels = [
		"DEBUG",
		"INFO",
		"WARNING",
		"ERROR",
	]
	
	def __write_to_log(self, data: str): # Запись в лог
		with self.log_file_path.open('a', encoding='utf-8') as log_file:
			log_file.write(data + '\n')
		
	
	def new(self, log_level: int = 0, text: str = "", save_to_file: bool = True): # Новое событие
		if log_level >= self.log_level:
			level_str = self.log_levels[log_level].upper()
			log_txt = f"[{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}] [{level_str}] {text}"
			print(log_txt)
			
			if save_to_file:
				self.cheak_logFilePath()
				self.__write_to_log(log_txt)
	
	@staticmethod
	def __get_file_size_and_source(file_path: Path | str): # Получение содержимого и размера файла
		with open(Path(file_path), 'rb') as file:
			source = file.read() # Содержимое лога
			size = len(source) # Размер лога
		
		return size, source
	
	def archivate_log(self): # Архивирование лога
		log_size, log = self.__get_file_size_and_source(self.log_file_path) # Получение содержимого лога и размера лога
		last_name = self.log_file_path.name # Получение имени лога
		
		# Создание сжатого архива
		archive = io.BytesIO()
		with tarfile.open(fileobj=archive, mode='w:gz') as tar:
			metaOfLog = tarfile.TarInfo(name=last_name)
			metaOfLog.size = log_size
			tar.addfile(tarinfo=metaOfLog, fileobj=io.BytesIO(log))
		
		# Запись архива
		archive_bytes = archive.getvalue()
		if len(archive_bytes) > log_size:
			self.log_file_path.rename(str(self.log_file_path) + " (Archived)") # Изменение имени лога на имя + (Archived)
		else:
			# Запись сжатого архива на диск
			new_path = Path(str(self.log_file_path) + " (Archived).tar.gz")
			with open(new_path, 'wb') as archive_log_file:
				archive_log_file.write(archive_bytes)
			
			self.log_file_path.unlink() # Удаление старого файла лога
	
	def cheak_logFilePath(self): # Проверка нужно ли архивировать лог, и в случае чего архивирование лога
		if self.log_file_type == "default":
			estimated_log_file_path = Path(str(LOGS_DIR)+'/'+time.strftime("%Y-%m-%d", time.localtime())) # Получение предпологаемого имени лога
			if self.log_file_path != estimated_log_file_path:
				if self.log_file_path.is_file():
					self.__write_to_log("\nEnd of log")
					self.archivate_log()
				
				self.log_file_path = estimated_log_file_path

def main():
	settings = data.get_settings() # Получение настроек
	settings['updateTimeInSeconds'] = settings['updateTime']
	settings['updateTime'] = settings['updateTime'] * 1000000
	
	main_logger = logger(settings['log_level']) # Создание объекта для логирования
	
	def cycle(url, proxy: dict = {"enabled": False, "url": None}, loggerForFunc=main_logger): # Цикл получения хеша
		success = False
		for _ in range(3):
			try:
				response = requests.get(url, headers={}, proxies=proxy['url'] if proxy['enabled'] else None)
				response.raise_for_status()
				success = True
				break
			except requests.exceptions.Any:
				loggerForFunc.new(3, "Data request error.")
				time.sleep(5)
			except Exception as e:
				loggerForFunc.new(3, f"An unknown error occurred while retrieving data from the network resource: {e}")
				response = None
				break
		
		if response:
			content = response.content
			if loggerForFunc.log_level == 0: # DEBUG данные
				response_weight = len(content)
				response_time = response.elapsed.total_seconds()
				speed = response_weight / response_time
				loggerForFunc.new(0, f"""Response Debug Data
	Response weight: {response_weight} B
	Response time: {response_time} sec
	Connection speed: {speed} B*sec
	Response code: {response.status_code} ({response.reason})""")
			
			if success:
				hashOfResponse = hashlib.sha3_256(content).digest()
				
				data.update_lastUpdateData(hashOfResponse, time.time_ns())
				return hashOfResponse
			else:
				raise Exception
	
	def parse_proxySettings(nameOfEnabledKey: str, proxySettings=settings['proxy'], loggerForFunc=main_logger): # Парсирование настроек прокси
		if isinstance(proxySettings, dict):
			proxy = {}
			try:
				proxy = {
					"enabled": bool(proxySettings[nameOfEnabledKey]),
					"url": {"http": str(proxySettings['url']), "https": str(proxySettings['url'])} if bool(proxySettings[nameOfEnabledKey]) else None
				}
			except KeyError:
				loggerForFunc.new(3, "Invalid proxy settings: Missing keys.")
				proxy = {"enabled": False, "url": None}
			except ValueError:
				loggerForFunc.new(3, "Invalid proxy settings: Invalid values ​​for keys")
				proxy = {"enabled": False, "url": None}
			except Exception as e:
				loggerForFunc.new(3, f"An unknown error occurred while retrieving critical data to get proxy settings: {e}.")
				proxy = {"enabled": False, "url": None}
		else:
			loggerForFunc.new(3, f"Invalid proxy settings: Proxy settings were expected to be a table..")
			proxy = {"enabled": False, "url": None}
			
		return proxy
	
	print(f"""Web Source Updates Checker
{'='*26}
Launch time: {time.strftime("%x %X", time.localtime())}
Data update time: Once every {settings['updateTimeInSeconds']} seconds
Web Source: {settings['url']}
Logging level: {main_logger.log_levels[main_logger.log_level].upper()}
""")
	
	while True:
		lastUpdateData = data.get_lastUpdateData()
		if lastUpdateData.get('success'):
			elpased_time = time.time_ns() - lastUpdateData['time']
			if elpased_time >= settings['updateTime']:
				# Получение хеша
				success = False
				try:
					hash = cycle(settings['url'], parse_proxySettings("enabled_for_webStorage"))
					success = True
				except Exception:
					main_logger.new(3, "An error occurred while retrieving the resource hash.")
				
				if success:
					if hash != lastUpdateData['hash']:
						main_logger.new(1, f"Data has been update! URL: {settings['url']}")
						
						# Telegram
						TGbot = settings.get('TGbot')
						if TGbot:
							if TGbot.get('enabled'):
								success = False
								try:
									token = str(TGbot['token'])
									chatId = int(TGbot['chatId'])
									success = True
								except KeyError:
									main_logger.new(3, "Invalid Telegram bot settings: Missing keys.")
								except ValueError:
									main_logger.new(3, "Invalid Telegram bot settings: Invalid values ​​for keys")
								except Exception as e:
									main_logger.new(3, f"An unknown error occurred while retrieving critical data to send a message to Telegram: {e}.")
								
								proxy = parse_proxySettings("enabled_for_TGBot")
								
								if success:
									text = TGbot.get('text')
									if not text:
										text = f"New data!\nSee {settings['url']} for more information." # Default text
									
									try:
										TelegramAPI.sendMessage(token, chatId, text, proxy)
									except Exception:
										main_logger.new(2, "The Telegram message wasn`t sent.")
								else:
									main_logger.new(2, "The Telegram message wasn`t sent.")
					else:
						main_logger.new(1, "The data hasn`t been updated", False)
				else:
					# Если произошла ошибка получения хеша
					data.update_lastUpdateData(lastUpdateData['hash'], time.time_ns())
					main_logger.new(2, "The cycle has been skipped.")
			else:
				try:
					time.sleep((settings['updateTime'] - elpased_time) // 1000000 + 1) # Time sleep до момента нового цикла
				except KeyboardInterrupt:
					# Если пользователь завершил задачу через Ctrl+C
					main_logger.new(1, "The user caused the stop", False)
					exit()
		else:
			# Создание данных
			cycle(settings['url'])
			main_logger.new(1, "The data has been created")

main()
