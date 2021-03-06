#
# gRPC chat demo client
#
# Threaded, tkinter-based chat client using gRPC to send and recieve messages.
# A background thread reads messages from the server using a streaming gRPC.
# We periodically read the recieve queue with a tk timer, since we can only
# update the UI from the main thread.
#

import tkinter as tk
import tkinter.scrolledtext as scrolledtext
import threading
import queue
import argparse
import logging
import sys
import grpc
import chat_pb2
import chat_pb2_grpc

class ChatClientRPC:
    def __init__(self, hostname, port):
        self.running = False
        addr = '{0}:{1}'.format(hostname, port)
        self.channel = grpc.insecure_channel(addr)
        self.stub = chat_pb2_grpc.ChatStub(self.channel)
        self.messages = None  # generator
        self.send_thread = threading.Thread(target=self._post_messages)
        self.recv_thread = threading.Thread(target=self._get_messages)
        self.send_queue = queue.Queue()
        self.recv_queue = queue.Queue()

    def shutdown(self):
        self.running = False
        if self.messages:
            self.messages.cancel()
        self.send_queue.put(None)
        self.send_thread.join()
        self.recv_thread.join()
        self.channel.close()

    def post_message(self, nick, text):
        element = (nick, text)
        self.send_queue.put(element)

    def start(self):
        self.running = True
        self.send_thread.start()
        self.recv_thread.start()

    def _post_messages(self):
        while self.running:
            element = self.send_queue.get()
            if element is None:
                break;
            try:
                message = chat_pb2.Message(nick=element[0], text=element[1])
                self.stub.PostMessage(message)
            except grpc.RpcError as e:
                logging.error('RPC error: {0}'.format(e))

    def _get_messages(self):
        empty = chat_pb2.Empty()
        while self.running:
            self.messages = self.stub.GetMessages(empty)
            try:
                for message in self.messages:
                    self.recv_queue.put(message)
            except grpc.RpcError as e:
                if not e.cancelled():
                    logging.error('RPC error: {0}'.format(e))
        self.messages = None

    def get_next_message(self):
        try:
            yield self.recv_queue.get_nowait()
        except queue.Empty:
            pass

class ChatClientApp:
    def __init__(self, root, nick, hostname, port):
        self.root = root
        self.nick = nick
        self.rpc = ChatClientRPC(hostname, port)
        self.create_app()

    def run(self):
        self.rpc.start()
        self._update_messages()
        self.root.mainloop()

    def create_app(self):
        self.root.title('Chat Client')
        frame = tk.Frame(self.root, width=200, height=200)
        frame.pack(fill='both', expand=True)
        self.create_widgets(frame)
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.root.bind('<Return>', self.post)

    def on_close(self):
        self.rpc.shutdown()
        self.root.destroy()

    def create_widgets(self, parent):
        self.textarea = scrolledtext.ScrolledText(
                    master=parent,
                    wrap=tk.WORD,
                    height=10)
        self.textarea.pack(padx=10, pady=10, fill='both', expand=True)
        self.entry = tk.Entry(parent)
        self.ok = tk.Button(parent, text='Ok', command=self.post)
        self.entry.pack(padx=10, pady=10, side='left', fill='both', expand=True)
        self.ok.pack(padx=10, pady=10, side='right')
        self.entry.focus_set()
        self.ok.bind('<Button-1>', self.post)

    def post(self, event=None):
        text = self.entry.get().strip()
        if text:
            self.rpc.post_message(self.nick, text)
            self.entry.delete(0, 'end')

    def _update_messages(self):
        for message in self.rpc.get_next_message():
            self.textarea.insert('end', '[{0}]: '.format(message.nick))
            self.textarea.insert('end', message.text)
            if not message.text.endswith('\n'):
                self.textarea.insert('end', '\n')
            self.textarea.see('end')
            self.textarea.update_idletasks()
        self.textarea.after(100, self._update_messages)

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--nick', help='user nickname', default='nickname')
    parser.add_argument('--hostname', help='chat server hostname', default='localhost')
    parser.add_argument('--port', type=int, help='chat server port number', default='8080')
    args = parser.parse_args()
    logging.basicConfig()

    root = tk.Tk()
    app = ChatClientApp(root, args.nick, args.hostname, args.port)
    app.run()

if __name__ == '__main__':
    sys.exit(main())
