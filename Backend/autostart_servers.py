import subprocess
import sys
import os
import signal
import time
import logging

servers = [
    {
        "name": "server.py",
        "cmd": [sys.executable, "server.py"]
    },
    {
        "name": "documenti_server.py",
        "cmd": [sys.executable, "documenti_server.py"]
    },
    {
        "name": "forum.py",
        "cmd": [sys.executable, "forum.py"]
    },
    {
        "name": "centrale.py",
        "cmd": [sys.executable, "centrale.py"]
    },
    {
        "name": "post.py",
        "cmd": [sys.executable, "post.py"]
    }
]

processes = []

def start_servers():
    for server in servers:
        logging.info(f"Sto avviando {server['name']}...")
        p = subprocess.Popen(server["cmd"])
        processes.append(p)
    logging.info("Ho aperto tutti i server.")

def stop_servers():
    logging.info("Sto chiudendo tutti i server...")
    for p in processes:
        try:
            p.terminate()
        except Exception as e:
            logging.error(f"Errore nella chiusura del processo: {e}")
    logging.info("Tutti i server chiusi.")

if __name__ == "__main__":
    start_servers()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_servers()