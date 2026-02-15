from flask import Flask, request

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    ip_client = request.remote_addr
    parametri = request.args
    print(f"\n[!] CONTATTO RICEVUTO!")
    print(f"    Provenienza IP: {ip_client}")
    print(f"    Rotta chiamata: /{path}")
    print(f"    Dati inviati:  {dict(parametri)}")
    return "OK - Ricevuto", 200

if __name__ == '__main__':
    print("=== MONITORAGGIO TRAFFICO ARDUINO ===")
    print("In ascolto su http://0.0.0.0:8888 ...")
    print("Premi CTRL+C per fermare.")
    #app.run(host='0.0.0.0', port=8888)