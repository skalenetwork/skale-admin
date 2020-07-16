from concurrent.futures import ThreadPoolExecutor as Executor

from tools.notifications.messages import send_message


TG_API_KEY = ''
TG_CHAT_ID = ''
THREADS = 6
ITERATIONS = 6


def send(message):
    print(f'Sending message {message}')
    send_message(message, TG_API_KEY, TG_CHAT_ID)
    print(f'Message {message} sended')


def main():
    print('here1')
    print('here')
    with Executor(max_workers=THREADS) as executor:
        futures = [
            executor.submit(send, {'message': f'xtest{i}'})
            for i in range(ITERATIONS)
        ]
    for future in futures:
        future.result()


if __name__ == '__main__':
    main()
