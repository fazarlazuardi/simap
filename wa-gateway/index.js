// Suppress noisy debug logs from Baileys internals
process.env.DEBUG = '';
process.env.NODE_ENV = 'production';

const { 
    default: makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason 
} = require("@whiskeysockets/baileys");
const { Boom } = require("@hapi/boom");
const pino = require("pino");
const qrcode = require("qrcode-terminal");
const express = require("express");
const cors = require("cors");

// Redirect noisy internal logs to /dev/null
const noopLogger = pino({ level: 'silent' });

const app = express();
const port = 3000;

app.use(cors());
app.use(express.json());

let sock;
let connected = false;

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');
    
    // Suppress verbose session debug logs from Baileys
    const origLog = console.log;
    console.log = function(...args) {
        const msg = args.join(' ');
        if (msg.includes('SessionEntry') || msg.includes('closing session') || msg.includes('Closing session') ||
            msg.includes('chainKey') || msg.includes('ephemeralKeyPair') || msg.includes('registrationId') ||
            msg.includes('currentRatchet') || msg.includes('indexInfo') || msg.includes('session_record')) {
            return;
        }
        origLog.apply(console, args);
    };

    sock = makeWASocket({
        printQRInTerminal: true,
        auth: state,
        logger: noopLogger,
        emitOwnEvents: false,
        browser: ['BAZNAS Gateway', 'Chrome', ''],
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            console.log('--- SCAN QR CODE INI DENGAN WHATSAPP ANDA ---');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            connected = false;
            const shouldReconnect = (lastDisconnect.error instanceof Boom) 
                ? lastDisconnect.error.output.statusCode !== DisconnectReason.loggedOut 
                : true;
            console.log('Koneksi terputus karena ', lastDisconnect.error, ', mencoba hubungkan kembali...', shouldReconnect);
            if (shouldReconnect) {
                connectToWhatsApp();
            }
        } else if (connection === 'open') {
            connected = true;
            console.log('--- WHATSAPP GATEWAY BAZNAS TERHUBUNG ---');
        }
    });

    sock.ev.on('creds.update', saveCreds);
}

// Health check endpoint
app.get("/health", (req, res) => {
    res.json({
        status: connected ? "connected" : "disconnected",
        ready: !!sock,
        timestamp: new Date().toISOString()
    });
});

// API Endpoint untuk kirim pesan dari Django
app.post("/send-message", async (req, res) => {
    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({ status: false, message: "Parameter 'number' dan 'message' wajib diisi" });
    }

    if (!sock) {
        return res.status(503).json({ status: false, message: "Gateway belum siap" });
    }

    try {
        // Format nomor (pastikan berawalan 62)
        let formattedNumber = number.replace(/[^0-9]/g, '');
        if (formattedNumber.startsWith('0')) {
            formattedNumber = '62' + formattedNumber.slice(1);
        }
        if (!formattedNumber.endsWith('@s.whatsapp.net')) {
            formattedNumber += '@s.whatsapp.net';
        }

        await sock.sendMessage(formattedNumber, { text: message });
        console.log(`Pesan terkirim ke: ${formattedNumber}`);
        res.json({ status: true, message: "Pesan berhasil dikirim" });
    } catch (err) {
        console.error("Gagal kirim pesan:", err);
        res.status(500).json({ status: false, message: "Gagal kirim pesan" });
    }
});

app.listen(port, () => {
    console.log(`Server API Gateway berjalan di http://localhost:${port}`);
    connectToWhatsApp();
});
