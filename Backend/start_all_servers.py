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
        "cmd": [sys.executable, "documenti.py"]
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
    while True:
        cmd = input("Scrivi 'start' per avviare i server, 'stop' per fermarli, 'restart' per riavviarli, o 'exit' per uscire dal programma: ").strip().lower()
        if cmd == "start":
            start_servers()
        elif cmd == "stop":
            stop_servers()
        elif cmd == "restart":
            stop_servers()
            time.sleep(2)
            start_servers()
        elif cmd == "exit":
            stop_servers()
            break
        else:
            print("Comando sconosciuto.")