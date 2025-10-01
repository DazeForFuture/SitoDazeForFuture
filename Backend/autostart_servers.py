import subprocess
import sys
import os
import signal
import time

servers = [
    {
        "name": "server.py",
        "cmd": [sys.executable, "server.py"]
    },
    {
        "name": "documenti.py",
        "cmd": [sys.executable, "documenti_server.py"]
    },

    {
        "name": "post.py",
        "cmd": [sys.executable, "post.py"]
    }
]

processes = []

def start_servers():
    for server in servers:
        print(f"Starting {server['name']}...")
        p = subprocess.Popen(server["cmd"])
        processes.append(p)
    print("Ho aperto tutti i server.")

def stop_servers():
    print("Sto chiudendo tutti i server...")
    for p in processes:
        try:
            p.terminate()
        except Exception as e:
            print(f"Errore nella chiusura del processo: {e}")
    print("Tutti i server chiusi.")

if __name__ == "__main__":
    start_servers()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_servers()