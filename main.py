import asyncio
import json
import websockets

# --- CONFIGURATION ---
TOKEN = "MTUwMzgyODI1MTgzNDA1NjcxNg.GGsovA.sJIqPgTY5o3hoI0cZSmiZ0Mpu8rbCrUAzgid1I"
# Ajoute ici les IDs des salons textuels que tu veux cibler
TARGET_CHANNELS = ["1511400681469247490", "1511400700280832120"] 
# ---------------------

GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

async def send_heartbeat(ws, interval):
    """Maintient la connexion ouverte en envoyant un 'ping' régulier (Heartbeat)."""
    while True:
        await asyncio.sleep(interval / 1000)
        payload = {
            "op": 1,  # Opcode 1 : Heartbeat
            "d": None
        }
        await ws.send(json.dumps(payload))
        print("[Gateway] Heartbeat envoyé.")

async def identify(ws):
    """Envoie le token d'authentification et configure les permissions (Intents)."""
    payload = {
        "op": 2,  # Opcode 2 : Identify
        "d": {
            "token": TOKEN,
            "properties": {
                "$os": "windows",
                "$browser": "mon_script_wss",
                "$device": "mon_script_wss"
            },
            # Intent 512 = GUILD_MESSAGES (messages des salons publics)
            "intents": 512 
        }
    }
    await ws.send(json.dumps(payload))
    print("[Auth] Tentative d'authentification...")

async def main():
    async with websockets.connect(GATEWAY_URL) as ws:
        print("[Connexion] Connecté aux serveurs de Discord.")
        
        while True:
            # Attente de la réception d'un paquet de données
            message = await ws.recv()
            packet = json.loads(message)
            
            op = packet.get("op")
            t = packet.get("t")  # Type d'événement
            d = packet.get("d")  # Données de l'événement

            # Événement 10: Hello (reçu au tout début de la connexion)
            if op == 10:
                heartbeat_interval = d["heartbeat_interval"]
                # Lance la boucle du Heartbeat en tâche de fond (asynchrone)
                asyncio.create_task(send_heartbeat(ws, heartbeat_interval))
                # Envoie immédiatement l'identification
                await identify(ws)

            # Événement 0: Dispatch (Discord transmet un événement classique)
            elif op == 0:
                if t == "MESSAGE_CREATE":
                    channel_id = d.get("channel_id")
                    
                    # On vérifie si l'ID du salon correspond à ta liste
                    if channel_id in TARGET_CHANNELS:
                        author = d.get("author", {}).get("username", "Inconnu")
                        content = d.get("content", "")
                        
                        print(f"\n--- Nouveau Message ({channel_id}) ---")
                        print(f"Utilisateur : {author}")
                        print(f"Message     : {content}")
                        print("-" * 40)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Arrêt] Script coupé proprement.")
