
import argparse
import concurrent.futures
import logging
import sys
from threading import Lock
from queue import Queue

import grpc
import chat_pb2
import chat_pb2_grpc

class Chat(chat_pb2_grpc.ChatServicer):

    def __init__(self):
        self.lock = Lock()
        self.queues = []

    def get_queue(self):
        queue = Queue()
        print('get_queue() id =', id(queue))
        with self.lock:
            self.queues.append(queue)
            logging.info('number of queues: {0}'.format(len(self.queues)))
        return queue

    def put_queue(self, queue):
        print('put_queue() id =', id(queue))
        with self.lock:
            self.queues.remove(queue)

    def PostMessage(self, request, context):
        logging.info('PostMessage(): nick="{0}", text="{1}"'\
            .format(request.nick, request.text))
        with self.lock:
            for queue in self.queues:
                message = chat_pb2.Message(nick=request.nick, text=request.text)
                queue.put(message)
        return chat_pb2.Empty()

    def GetMessages(self, request, context):
        # xxx: leaks queues!
        queue = self.get_queue()
        while True: # todo: completion from client?
            try:
                message = queue.get(timeout=10)
            except Queue.Empty:
                message = chat_pb2.Message(nick='server', text='ping')
            yield message

        self.put_queue(queue) # todo: with or try block

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--port', type=int, help='port number', default=8080)
    parser.add_argument('--threads', type=int, help='number of worker threads', default=10)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')

    chat = Chat()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.threads)
    server = grpc.server(executor)
    chat_pb2_grpc.add_ChatServicer_to_server(chat, server)
    addr = '[::]:{0}'.format(args.port)
    logging.info('listening on port {0}'.format(args.port))
    server.add_insecure_port(addr)
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    sys.exit(main())
