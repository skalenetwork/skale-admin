from core.tg_bot import TgBot
from concurrent.futures import ThreadPoolExecutor as Executor


TG_API_KEY = ''
TG_CHAT_ID = ''
THREADS = 2
ITERATIONS = 2


def send(bot, message):
    print(f'Sending message {message}')
    bot.celery_send_message(message)
    print(f'Message {message} sended')


def main():
    print('here1')
    bot = TgBot(TG_API_KEY, TG_CHAT_ID)
    print('here')
    with Executor(max_workers=THREADS) as executor:
        futures = [
            executor.submit(send, bot, {'message': f'test{i}'})
            for i in range(ITERATIONS)
        ]
    for future in futures:
        future.result()


if __name__ == '__main__':
    main()
