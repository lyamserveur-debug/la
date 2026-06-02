const WebSocket = require('ws');

// --- CONFIGURATION ---
const TOKEN = "TON_TOKEN_DISCORD_ICI";
// Liste des IDs des salons que tu veux surveiller (sous forme de chaînes)
const TARGET_CHANNELS = ["123456789012345678", "987654321098765432"]; 
// ---------------------

const GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json";

// Connexion à la Gateway Discord
const ws = new WebSocket(GATEWAY_URL);
let heartbeatIntervalId = null;

ws.on('open', () => {
    console.log("[Connexion] Connecté à la Gateway Discord.");
});

ws.on('message', (data) => {
    const payload = JSON.parse(data);
    const { op, t, d } = payload;

    // Opcode 10: Hello (reçu immédiatement après la connexion)
    if (op === 10) {
        const heartbeatInterval = d.heartbeat_interval;
        
        // Commencer à envoyer le Heartbeat à l'intervalle demandé
        startHeartbeat(ws, heartbeatInterval);
        
        // S'authentifier auprès de Discord
        identify(ws);
    }

    // Opcode 0: Dispatch (Événements Discord comme la réception de messages)
    if (op === 0) {
        if (t === "MESSAGE_CREATE") {
            const channelId = d.channel_id;

            // Vérifier si le message provient d'un salon surveillé
            if (TARGET_CHANNELS.includes(channelId)) {
                const author = d.author?.username || "Inconnu";
                const content = d.content || "";

                console.log(`\n[Nouveau Message] Salon: ${channelId}`);
                console.log(`Auteur: ${author}`);
                console.log(`Contenu: ${content}`);
                console.log("-".repeat(30));
            }
        }
    }
});

// Gérer la fermeture de la connexion
ws.on('close', (code, reason) => {
    console.log(`[Arrêt] Connexion fermée. Code: ${code}, Raison: ${reason}`);
    if (heartbeatIntervalId) clearInterval(heartbeatIntervalId);
});

// Gérer les erreurs
ws.on('error', (error) => {
    console.error("[Erreur]", error);
});

// --- FONCTIONS UTILIRES ---

function startHeartbeat(ws, interval) {
    heartbeatIntervalId = setInterval(() => {
        const heartbeatPayload = {
            op: 1, // Opcode 1: Heartbeat
            d: null
        };
        ws.send(JSON.stringify(heartbeatPayload));
        console.log("[Heartbeat] Envoyé");
    }, interval);
}

function identify(ws) {
    const identifyPayload = {
        op: 2, // Opcode 2: Identify
        d: {
            token: TOKEN,
            properties: {
                $os: "linux",
                $browser: "my_wss_script",
                $device: "my_wss_script"
            },
            // Intent 512 correspond à GUILD_MESSAGES
            intents: 512 
        }
    };
    ws.send(JSON.stringify(identifyPayload));
    console.log("[Auth] Demande d'identification envoyée.");
}
