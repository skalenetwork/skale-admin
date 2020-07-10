from core.tg_bot import TgBot
from concurrent.futures import ThreadPoolExecutor as Executor


TG_API_KEY = ''
TG_CHAT_ID = ''

THREADS = 4
ITERATIONS = 1


def send(bot, message):
    print(f'Sending message {message}')
    bot.celery_send_message(message)
    print(f'Message {message} sended')


def main():
    bot = TgBot(TG_API_KEY, TG_CHAT_ID)
    with Executor(max_workers=THREADS) as executor:
        futures = [
            executor.submit(send, bot, {'message': f'1test{i}'})
            for i in range(ITERATIONS)
        ]
    for future in futures:
        print(future.result())


if __name__ == '__main__':
    main()
