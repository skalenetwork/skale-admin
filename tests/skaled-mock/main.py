import json
import logging
from logging import StreamHandler

from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    handlers=[
        StreamHandler(),
    ],
    level=logging.INFO
)

logger = logging.getLogger(__name__)

HOST = '127.0.0.1'
PORT = 10003


class RequestsHanlder(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    @classmethod
    def _get_raw_response(cls, data):
        return json.dumps(data).encode()

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        if length > 0:
            raw_data = self.rfile.read(length)
            logger.info(f'raw_data {type(raw_data)} {raw_data}')
            data = json.loads(raw_data)
            logger.info(f'data {type(data)} {data}')
        else:
            data = {}

        logger.info(f'Route {self.path}')
        code = data['exit_code']
        self._set_headers(200)
        raw_response = RequestsHanlder._get_raw_response({})
        self.wfile.write(raw_response)

        logger.info('Exitting with code %d', code)
        exit(code)


def main():
    http_server = HTTPServer((HOST, PORT), RequestsHanlder)
    logger.info('Starting test server host: %s port: %d', HOST, PORT)
    http_server.serve_forever()


if __name__ == '__main__':
    main()
