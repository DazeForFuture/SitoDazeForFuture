import subprocess
import sys
import os
import signal
import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('servers.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

servers = [
    {
        "name": "server.py",
        "cmd": [sys.executable, "server.py"],
        "port": 5000
    },
    {
        "name": "documenti_server.py",
        "cmd": [sys.executable, "documenti_server.py"],
        "port": 5001
    },
    {
        "name": "post.py",
        "cmd": [sys.executable, "post.py"],
        "port": 5002
    },
    {
        "name": "forum.py",
        "cmd": [sys.executable, "forum.py"],
        "port": 5003
    },
    {
        "name": "centrale.py",
        "cmd": [sys.executable, "centrale.py"],
        "port": 5005
    }
]

processes = []

def start_servers():
    """Avvia tutti i server Flask."""
    logger.info("=" * 70)
    logger.info("🚀 Starting SitoDazeForFuture Backend Servers")
    logger.info("=" * 70)
    
    for server in servers:
        logger.info(f"Starting {server['name']} on port {server['port']}...")
        try:
            p = subprocess.Popen(
                server["cmd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            processes.append({
                'name': server['name'],
                'process': p,
                'port': server['port']
            })
            logger.info(f"✅ {server['name']} started (PID: {p.pid})")
        except Exception as e:
            logger.error(f"❌ Failed to start {server['name']}: {e}")
    
    logger.info("=" * 70)
    logger.info(f"✅ All servers started. ({len(processes)}/{len(servers)})")
    logger.info("=" * 70)
    logger.info(f"Listening on ports: {', '.join([str(s['port']) for s in servers])}")

def stop_servers(signum=None, frame=None):
    """Arresta tutti i server."""
    logger.info("\n" + "=" * 70)
    logger.info("🛑 Stopping all servers...")
    logger.info("=" * 70)
    
    for proc_info in processes:
        name = proc_info['name']
        p = proc_info['process']
        try:
            logger.info(f"Terminating {name} (PID: {p.pid})...")
            p.terminate()
            p.wait(timeout=5)
            logger.info(f"✅ {name} terminated")
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️  {name} did not terminate gracefully, killing...")
            p.kill()
            logger.info(f"✅ {name} killed")
        except Exception as e:
            logger.error(f"❌ Error stopping {name}: {e}")
    
    logger.info("=" * 70)
    logger.info("All servers stopped.")
    logger.info("=" * 70)

def monitor_servers():
    """Monitora i server e li riavvia se crashano."""
    logger.info("Starting server monitoring...")
    
    while True:
        try:
            for proc_info in processes:
                name = proc_info['name']
                p = proc_info['process']
                
                if p.poll() is not None:  # Process terminated
                    logger.error(f"❌ {name} crashed (exit code: {p.returncode})")
                    logger.info(f"Restarting {name}...")
                    
                    # Find original server config
                    server_config = next(s for s in servers if s['name'] == name)
                    
                    # Restart
                    try:
                        new_p = subprocess.Popen(
                            server_config["cmd"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        proc_info['process'] = new_p
                        logger.info(f"✅ {name} restarted (PID: {new_p.pid})")
                    except Exception as e:
                        logger.error(f"❌ Failed to restart {name}: {e}")
            
            time.sleep(10)  # Check every 10 seconds
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in monitor: {e}")

if __name__ == "__main__":
    # Register signal handler
    signal.signal(signal.SIGINT, stop_servers)
    signal.signal(signal.SIGTERM, stop_servers)
    
    # Check for required environment variables
    logger.info("Checking environment configuration...")
    required_env = ['FLASK_SECRET_KEY', 'ADMIN_PASSWORD']
    missing_env = [var for var in required_env if not os.environ.get(var)]
    
    if missing_env:
        logger.warning(f"⚠️  Missing environment variables: {', '.join(missing_env)}")
        logger.warning("Some features may not work properly.")
    
    # Start servers
    start_servers()
    
    # Monitor servers
    try:
        monitor_servers()
    except KeyboardInterrupt:
        stop_servers()
        sys.exit(0)