// Suppress noisy debug logs from Baileys internals
process.env.DEBUG = '';
process.env.NODE_ENV = process.env.NODE_ENV || 'production';

const { 
    default: makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason 
} = require("@whiskeysockets/baileys");
const { Boom } = require("@hapi/boom");
const pino = require("pino");
const qrcodeTerminal = require("qrcode-terminal");
const QRCode = require("qrcode");
const express = require("express");
const cors = require("cors");
const path = require("path");
const fs = require("fs-extra");

// Silent logger for Baileys internal event spam
const noopLogger = pino({ level: 'silent' });

const AUTH_DIR = path.join(__dirname, 'auth_info_baileys');
const LOGS_DIR = path.join(__dirname, 'logs');

// Ensure required directories exist
fs.ensureDirSync(AUTH_DIR);
fs.ensureDirSync(LOGS_DIR);

// Circular Log Buffer for Live Web Console (Max 300 lines)
const maxLogBuffer = 300;
const logBuffer = [];

function pushToLogBuffer(type, args) {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const msg = args.map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
    logBuffer.push(`[${timestamp}] [${type}] ${msg}`);
    if (logBuffer.length > maxLogBuffer) {
        logBuffer.shift();
    }
}

const origLog = console.log;
const origError = console.error;
const origWarn = console.warn;

console.log = function(...args) {
    pushToLogBuffer('INFO', args);
    origLog.apply(console, args);
};
console.error = function(...args) {
    pushToLogBuffer('ERROR', args);
    origError.apply(console, args);
};
console.warn = function(...args) {
    pushToLogBuffer('WARN', args);
    origWarn.apply(console, args);
};

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

let sock = null;
let connected = false;
let isReconnecting = false;
let retryDelay = 3000; // Initial reconnect delay (3 seconds)

// Status & QR State Management
// Status enum: "CONNECTED" | "SCAN_QR" | "CONNECTING" | "DISCONNECTED"
let connectionStatus = "DISCONNECTED";
let latestRawQr = null;
let latestQrImage = null;


// ============================================================================
// IN-MEMORY TASK QUEUE WITH CONCURRENCY = 1 & HUMAN-LIKE JITTER DELAY
// ============================================================================
class AsyncMessageQueue {
    constructor() {
        this.queue = [];
        this.isProcessing = false;
        this.stats = {
            totalEnqueued: 0,
            processedCount: 0,
            failedCount: 0
        };
    }

    getRandomJitter() {
        return Math.floor(Math.random() * 3000) + 2000;
    }

    enqueue(job) {
        const jobId = `job_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
        const queueItem = {
            id: jobId,
            number: job.number,
            message: job.message,
            metadata: job.metadata || {},
            enqueuedAt: new Date()
        };

        this.queue.push(queueItem);
        this.stats.totalEnqueued++;

        setImmediate(() => this.processNext());

        return {
            jobId: queueItem.id,
            pending: this.queue.length,
            estimatedDelaySeconds: Math.ceil((this.queue.length * 3.5))
        };
    }

    enqueueBulk(jobs) {
        const enqueuedJobs = [];
        for (const j of jobs) {
            if (j && j.number && j.message) {
                const res = this.enqueue({ number: j.number, message: j.message, metadata: j.metadata });
                enqueuedJobs.push(res);
            }
        }
        return {
            totalQueued: enqueuedJobs.length,
            pending: this.queue.length,
            estimatedDelaySeconds: Math.ceil((this.queue.length * 3.5))
        };
    }

    async processNext() {
        if (this.isProcessing || this.queue.length === 0) {
            return;
        }

        this.isProcessing = true;
        const currentJob = this.queue.shift();

        try {
            if (!sock || !connected) {
                console.warn(`[QUEUE] Socket belum terhubung. Menunda pekerjaan (${currentJob.id}) kembali ke antrean...`);
                this.queue.unshift(currentJob);
                this.isProcessing = false;
                setTimeout(() => this.processNext(), 5000);
                return;
            }

            const formattedJid = currentJob.number;
            console.log(`[QUEUE] Memproses pengiriman (${currentJob.id}) ke ${formattedJid}...`);

            try {
                await sock.sendPresenceUpdate('composing', formattedJid);
                await new Promise(resolve => setTimeout(resolve, 1000));
            } catch (presErr) {
                console.warn(`[QUEUE] Warning presence update (${formattedJid}):`, presErr.message);
            }

            await sock.sendMessage(formattedJid, { text: currentJob.message });
            
            try {
                await sock.sendPresenceUpdate('paused', formattedJid);
            } catch (_) {}

            this.stats.processedCount++;
            console.log(`[QUEUE] ✅ Sukses terkirim (${currentJob.id}) ke ${formattedJid}`);

        } catch (err) {
            this.stats.failedCount++;
            console.error(`[QUEUE] ❌ Gagal pengiriman (${currentJob.id}) ke ${currentJob.number}:`, err.message);
        } finally {
            const jitterMs = this.getRandomJitter();
            console.log(`[QUEUE] Jeda anti-ban (${jitterMs} ms) sebelum pengiriman berikutnya...`);
            await new Promise(resolve => setTimeout(resolve, jitterMs));

            this.isProcessing = false;
            this.processNext();
        }
    }

    getStatus() {
        return {
            pending: this.queue.length,
            isProcessing: this.isProcessing,
            stats: this.stats
        };
    }
}

const msgQueue = new AsyncMessageQueue();

// ============================================================================
// PHONE NUMBER VALIDATION & FORMATTING HELPER
// ============================================================================
function formatWaNumber(rawNumber) {
    if (!rawNumber) return null;
    let cleaned = String(rawNumber).replace(/[^0-9]/g, '');
    
    if (cleaned.startsWith('0')) {
        cleaned = '62' + cleaned.slice(1);
    } else if (cleaned.startsWith('8')) {
        cleaned = '628' + cleaned.slice(1);
    }

    if (!cleaned.endsWith('@s.whatsapp.net')) {
        cleaned += '@s.whatsapp.net';
    }

    const digitsOnly = cleaned.split('@')[0];
    if (/^628\d{7,12}$/.test(digitsOnly)) {
        return cleaned;
    }
    
    return null;
}

// ============================================================================
// BAILEYS SOCKET & CONNECTION LIFECYCLE MANAGEMENT
// ============================================================================
async function connectToWhatsApp() {
    if (isReconnecting) return;
    isReconnecting = true;
    connectionStatus = "CONNECTING";

    try {
        console.log('[AUTH] Membaca status kredensial multi-file auth...');
        const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

        sock = makeWASocket({
            printQRInTerminal: true,
            auth: state,
            logger: noopLogger,
            emitOwnEvents: false,
            browser: ['SIMAP BAZNAS Gateway', 'Chrome', '1.0.0'],
            connectTimeoutMs: 60000,
            defaultQueryTimeoutMs: 60000,
            keepAliveIntervalMs: 25000,
        });

        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                connectionStatus = "SCAN_QR";
                latestRawQr = qr;
                try {
                    latestQrImage = await QRCode.toDataURL(qr, { margin: 2, scale: 6 });
                } catch (qrErr) {
                    console.error('[QR] Error generating base64 QR Data URL:', qrErr.message);
                }

                console.log('\n============================================================');
                console.log('--- SCAN QR CODE DI BAWAH INI UNTUK OTENTIKASI WHATSAPP ---');
                console.log('============================================================\n');
                qrcodeTerminal.generate(qr, { small: true });
            }

            if (connection === 'close') {
                connected = false;
                const statusCode = lastDisconnect?.error instanceof Boom 
                    ? lastDisconnect.error.output?.statusCode 
                    : lastDisconnect?.error?.output?.statusCode;

                const isLoggedOut = statusCode === DisconnectReason.loggedOut;
                console.log(`[CONN] Koneksi terputus. Status Code: ${statusCode || 'unknown'}. LoggedOut: ${isLoggedOut}`);

                if (isLoggedOut) {
                    connectionStatus = "SCAN_QR";
                    console.warn('[AUTH] Sesi WhatsApp telah Logged Out. Membersihkan folder auth_info_baileys...');
                    try {
                        sock?.ws?.close();
                    } catch (_) {}
                    sock = null;
                    latestRawQr = null;
                    latestQrImage = null;
                    fs.emptyDirSync(AUTH_DIR);
                    console.log('[AUTH] Folder sesi berhasil dibersihkan. Memulai ulang socket untuk QR baru...');
                    retryDelay = 3000;
                    isReconnecting = false;
                    setTimeout(() => connectToWhatsApp(), 2000);
                } else {
                    connectionStatus = "CONNECTING";
                    console.log(`[CONN] Menjadwalkan reconnect otomatis dalam ${retryDelay / 1000} detik...`);
                    sock = null;
                    isReconnecting = false;
                    setTimeout(() => {
                        retryDelay = Math.min(Math.floor(retryDelay * 1.5), 60000);
                        connectToWhatsApp();
                    }, retryDelay);
                }
            } else if (connection === 'open') {
                connected = true;
                connectionStatus = "CONNECTED";
                isReconnecting = false;
                retryDelay = 3000;
                latestRawQr = null;
                latestQrImage = null;
                console.log('\n============================================================');
                console.log('✅ WHATSAPP GATEWAY SIMAP BAZNAS BERHASIL TERHUBUNG!');
                console.log('============================================================\n');
            }
        });

        sock.ev.on('creds.update', saveCreds);

    } catch (err) {
        connectionStatus = "DISCONNECTED";
        console.error('[CONN ERROR] Terjadi kesalahan saat inisialisasi socket:', err);
        isReconnecting = false;
        setTimeout(() => connectToWhatsApp(), 5000);
    }
}

// ============================================================================
// EXPRESS REST API ENDPOINTS
// ============================================================================

// Comprehensive Status Endpoint (JSON for Web UI & Dashboard HUD)
app.get("/status", (req, res) => {
    res.json({
        status: connectionStatus,
        ready: connected,
        qrCode: latestRawQr,
        qr_image: latestQrImage,
        uptime_seconds: Math.floor(process.uptime()),
        queue: msgQueue.getStatus(),
        timestamp: new Date().toISOString()
    });
});

// Health check endpoint (compatible alias)
app.get("/health", (req, res) => {
    res.json({
        status: connectionStatus === "CONNECTED" ? "connected" : connectionStatus.toLowerCase(),
        ready: connected,
        connection_status: connectionStatus,
        qr_image: latestQrImage,
        uptime_seconds: Math.floor(process.uptime()),
        queue: msgQueue.getStatus(),
        timestamp: new Date().toISOString()
    });
});

// Detailed queue status endpoint
app.get("/queue-status", (req, res) => {
    res.json({
        status: "active",
        queue: msgQueue.getStatus()
    });
});

// Live Log Stream Endpoint for Web Terminal Console Modal
app.get("/logs", async (req, res) => {
    try {
        let fileLogs = [];
        const outLogPath = path.join(LOGS_DIR, 'out.log');
        const errLogPath = path.join(LOGS_DIR, 'error.log');

        if (fs.existsSync(outLogPath)) {
            try {
                const content = await fs.readFile(outLogPath, 'utf8');
                const lines = content.split('\n').filter(l => l.trim());
                fileLogs.push(...lines.slice(-150));
            } catch (_) {}
        }

        if (fs.existsSync(errLogPath)) {
            try {
                const content = await fs.readFile(errLogPath, 'utf8');
                const lines = content.split('\n').filter(l => l.trim()).map(l => '[ERR FILE] ' + l);
                fileLogs.push(...lines.slice(-50));
            } catch (_) {}
        }

        const logsToReturn = fileLogs.length > 0 ? fileLogs : logBuffer;

        res.json({
            status: true,
            logs: logsToReturn,
            line_count: logsToReturn.length,
            timestamp: new Date().toISOString()
        });
    } catch (err) {
        res.json({ status: true, logs: logBuffer, error: err.message });
    }
});


// API Endpoint untuk restart koneksi socket Baileys (1-Click Action)
app.post("/restart", async (req, res) => {
    try {
        console.log("[API] Permintaan restart koneksi WA Gateway diterima.");
        if (sock) {
            try { sock.ws?.close(); } catch (_) {}
            sock = null;
        }
        connected = false;
        isReconnecting = false;
        retryDelay = 3000;
        connectionStatus = "CONNECTING";
        
        setTimeout(() => connectToWhatsApp(), 1000);

        return res.json({ 
            status: true, 
            message: "Koneksi WA Gateway sedang dimuat ulang...",
            connection_status: connectionStatus
        });
    } catch (err) {
        return res.status(500).json({ status: false, message: err.message });
    }
});

// API Endpoint untuk reset sesi / logout (1-Click Action)
app.post("/logout", async (req, res) => {
    try {
        console.log("[API] Permintaan reset sesi / logout WA Gateway diterima.");
        if (sock) {
            try { await sock.logout(); } catch (_) {}
            try { sock.ws?.close(); } catch (_) {}
            sock = null;
        }
        connected = false;
        isReconnecting = false;
        retryDelay = 3000;
        latestRawQr = null;
        latestQrImage = null;
        connectionStatus = "SCAN_QR";
        
        fs.emptyDirSync(AUTH_DIR);
        console.log("[AUTH] Folder auth_info_baileys telah dibersihkan.");

        setTimeout(() => connectToWhatsApp(), 1500);

        return res.json({ 
            status: true, 
            message: "Sesi WhatsApp berhasil diputus dan dibersihkan. Memuat QR Code baru...",
            connection_status: connectionStatus
        });
    } catch (err) {
        return res.status(500).json({ status: false, message: err.message });
    }
});

// API Endpoint untuk kirim single pesan dari Django (HTTP 202 Accepted Non-Blocking)
app.post("/send-message", (req, res) => {
    const rawNumber = req.body.number || req.body.to;
    const messageText = req.body.message;

    if (!rawNumber || !messageText) {
        return res.status(400).json({ 
            status: false, 
            message: "Parameter 'number' / 'to' dan 'message' wajib diisi" 
        });
    }

    const formattedJid = formatWaNumber(rawNumber);
    if (!formattedJid) {
        return res.status(400).json({ 
            status: false, 
            message: `Format nomor telepon tidak valid: '${rawNumber}'. Wajib nomor Indonesia berawalan 08/628.` 
        });
    }

    const queueInfo = msgQueue.enqueue({
        number: formattedJid,
        message: messageText,
        metadata: req.body.metadata || {}
    });

    return res.status(202).json({
        status: true,
        message: "Pesan telah berhasil masuk ke antrean pengiriman WA Gateway",
        job_id: queueInfo.jobId,
        recipient: formattedJid,
        queue: {
            pending: queueInfo.pending,
            estimated_delay_seconds: queueInfo.estimatedDelaySeconds
        }
    });
});

// API Endpoint untuk kirim pesan massal / bulk (HTTP 202 Accepted Non-Blocking)
app.post("/send-bulk", (req, res) => {
    const messagesList = req.body.messages;

    if (!Array.isArray(messagesList) || messagesList.length === 0) {
        return res.status(400).json({ 
            status: false, 
            message: "Parameter 'messages' wajib berupa array berisi objek { number, message }" 
        });
    }

    const validJobs = [];
    const invalidNumbers = [];

    for (const item of messagesList) {
        const rawNum = item.number || item.to;
        const msgText = item.message;
        if (!rawNum || !msgText) continue;

        const formattedJid = formatWaNumber(rawNum);
        if (formattedJid) {
            validJobs.push({ number: formattedJid, message: msgText, metadata: item.metadata || {} });
        } else {
            invalidNumbers.push(rawNum);
        }
    }

    if (validJobs.length === 0) {
        return res.status(400).json({
            status: false,
            message: "Tidak ada nomor tujuan valid yang dapat dimasukkan ke antrean",
            invalid_numbers: invalidNumbers
        });
    }

    const bulkResult = msgQueue.enqueueBulk(validJobs);

    return res.status(202).json({
        status: true,
        message: `${bulkResult.totalQueued} pesan massal berhasil dimasukkan ke antrean WA Gateway`,
        total_queued: bulkResult.totalQueued,
        invalid_numbers_count: invalidNumbers.length,
        queue: {
            pending: bulkResult.pending,
            estimated_delay_seconds: bulkResult.estimatedDelaySeconds
        }
    });
});

// ============================================================================
// SERVER INITIALIZATION & GRACEFUL SHUTDOWN HANDLERS
// ============================================================================
const server = app.listen(port, () => {
    console.log(`\n============================================================`);
    console.log(`🚀 WA Gateway API Server berjalan di http://localhost:${port}`);
    console.log(`   Endpoints: GET /status | POST /restart | POST /logout`);
    console.log(`============================================================\n`);
    connectToWhatsApp();
});

function gracefulShutdown(signal) {
    console.log(`\n[SYSTEM] Menerima sinyal ${signal}. Memulai Graceful Shutdown WA Gateway...`);
    
    server.close(() => {
        console.log('[SYSTEM] Express HTTP server telah ditutup.');
        
        if (sock) {
            try {
                console.log('[SYSTEM] Menutup koneksi WebSocket Baileys secara bersih...');
                sock.ws?.close();
            } catch (err) {
                console.error('[SYSTEM] Error closing socket:', err.message);
            }
        }
        
        console.log('[SYSTEM] Process shutdown selesai.');
        process.exit(0);
    });

    setTimeout(() => {
        console.error('[SYSTEM] Forced shutdown karena timeout.');
        process.exit(1);
    }, 10000);
}

process.on('SIGINT', () => gracefulShutdown('SIGINT'));
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

process.on('unhandledRejection', (reason, promise) => {
    console.error('[ERROR] Unhandled Rejection:', reason);
});

process.on('uncaughtException', (err) => {
    console.error('[ERROR] Uncaught Exception:', err);
});
