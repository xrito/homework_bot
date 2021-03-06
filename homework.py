import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}
headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logging.basicConfig(
    level=logging.INFO,
    filename='program.log',
    filemode='w+',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


class StatusError(Exception):
    """недокументированный статус домашней работы в ответе API."""


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на ENDPOINT и получает данные."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(url, headers=headers, params=params)
    except requests.exceptions.RequestException as error:
        error_message = f'Код ответа API: {error}'
        logger.error(error_message)
        raise requests.exceptions.RequestException(error_message)
    finally:
        if response.status_code != HTTPStatus.OK:
            error_message = (
                f'Эндпоинт не доступен, статус: {response.status_code}')
            logger.error(error_message)
            raise requests.exceptions.HTTPError(error_message)
    return response.json()


def parse_status(homework):
    """Проверяет не изменился ли статус."""
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if homework_status is None:
        error_message = f'Ошибка. Значение статуса пусто: {homework_status}'
        logger.error(error_message)
        raise IndexError(error_message)
    if homework_name is None:
        error_message = f'Ошибка. Значение имени работы пусто: {homework_name}'
        logger.error(error_message)
        raise StatusError(error_message)
    verdict = VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверяет содержимое ответа от API."""
    if 'homeworks' not in response:
        error_message = 'Ошибка в ответе API, ключ homeworks не найден.'
        logger.error(error_message)
        raise KeyError(error_message)
    if not response['homeworks']:
        logger.info('Словарь homeworks пуст.')
        return {}
    if response['homeworks'][0].get('status') not in VERDICTS:
        error_message = 'Неизвестный статус домашней работы!'
        logger.error(error_message)
        raise StatusError(error_message)
    return response['homeworks'][0]


def checking_variables():
    """Проверяет токены."""
    for token in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if not token:
            logger.critical('Программа остановлена.'
                            'Отсутствует обязательная переменная окружения.')
            raise SystemExit


def main():
    """Главная функция."""
    checking_variables()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework)
                if message:
                    send_message(bot, message)
            logger.info('Следующий опрос API через 10 минут')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
