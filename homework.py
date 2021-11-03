import json
import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}

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
    '''недокументированный статус домашней работы, обнаруженный в ответе API.'''


def send_message(bot, message):
    '''Отправляет сообщения в чат'''
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except Exception as error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(url, current_timestamp):
    '''Отправляет запрос к API домашки на ENDPOINT и получает данные.'''
    params = {'from_date': current_timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            error_message = (
                f'Эндпоинт не доступен, статус: {response.status_code}')
            logger.error(error_message)
            raise requests.exceptions.HTTPError(error_message)
        return response.json()
    except requests.exceptions.RequestException as error:
        error_message = f'Код ответа API: {error}'
        logger.error(error_message)
        raise requests.exceptions.RequestException(error_message)


def parse_status(homework):
    '''Проверяет не изменился ли статус'''
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_STATUSES[homework_status]
    if os.path.isfile('data.txt') and os.path.getsize('data.txt') != 0:
        with open('data.txt') as json_file:
            data = json.load(json_file)
        if data['homework_old']['status'] != homework['status']:
            data = {}
            data['homework_old'] = homework
            with open('data.txt', 'w+') as outfile:
                json.dump(data, outfile, indent=2)
            return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    elif not os.path.isfile('data.txt'):
        data = {}
        data['homework_old'] = homework
        with open('data.txt', 'w+') as outfile:
            json.dump(data, outfile, indent=2)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        data = {}
        data['homework_old'] = homework
        with open('data.txt', 'w+') as outfile:
            json.dump(data, outfile, indent=2)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    '''Проверяем содержимое ответа от API'''
    if response['homeworks'] == []:
        return {}
    if response['homeworks'][0].get('status') not in HOMEWORK_STATUSES:
        error_message = ('Неизвестный статус домашней работы!')
        logger.error(error_message)
        raise StatusError(error_message)
    return response['homeworks'][0]


def main():
    if not PRACTICUM_TOKEN:
        logger.critical(
            f'Программа остановлена. Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN')
    if not TELEGRAM_TOKEN:
        logger.critical(
            f'Программа остановлена. Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN')
    if not TELEGRAM_CHAT_ID:
        logger.critical(
            f'Программа остановлена. Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - 3000000
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
