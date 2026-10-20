/**
 * Ponte local WhatsApp Web (QR Code) para o WhatsAuto.
 * Conecta o WhatsApp da empresa via QR Code (sem precisar da Meta Cloud API),
 * repassa mensagens recebidas para o servidor Python local (server.py)
 * e detecta quando um atendente humano responde manualmente para pausar o robô.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const pino = require('pino');
const qrcodeTerminal = require('qrcode-terminal');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  makeCacheableSignalKeyStore,
  DisconnectReason,
  fetchLatestBaileysVersion,
  Browsers,
} = require('@whiskeysockets/baileys');

const BRIDGE_PORT = Number(process.env.QR_BRIDGE_PORT || 5001);
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';
const SESSION_DIR = path.join(__dirname, 'wa_session');
const silentLogger = pino({ level: 'silent' });

let sock = null;
let authObj = null;
let state = 'starting'; // starting | qr_ready | connecting | connected | disconnected
let currentQr = null;
let connectedPhone = null;
let connectedName = null;
let lastError = null;
let reconnecting = false;
let reconnectTimer = null;

// Guarda os IDs das mensagens enviadas pelo próprio robô para diferenciar de mensagens enviadas por um humano
const botSentMessageIds = new Set();

process.on('uncaughtException', (err) => {
  console.error('Erro não tratado (ignorado para manter ponte ativa):', err?.message || err);
});

process.on('unhandledRejection', (err) => {
  console.error('Promise rejeitada (ignorada para manter ponte ativa):', err?.message || err);
});

function isNonPrivateChat(jid) {
  if (!jid) return true;
  return (
    jid.endsWith('@g.us') ||
    jid === 'status@broadcast' ||
    jid.endsWith('@broadcast') ||
    jid.endsWith('@newsletter')
  );
}

function extractText(message) {
  if (!message) return '';
  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
  if (message.imageMessage?.caption) return message.imageMessage.caption;
  if (message.videoMessage?.caption) return message.videoMessage.caption;
  if (message.buttonsResponseMessage?.selectedDisplayText) {
    return message.buttonsResponseMessage.selectedDisplayText;
  }
  if (message.listResponseMessage?.title) {
    return message.listResponseMessage.title;
  }
  if (message.ephemeralMessage?.message) {
    return extractText(message.ephemeralMessage.message);
  }
  if (message.viewOnceMessage?.message) {
    return extractText(message.viewOnceMessage.message);
  }
  return '';
}

function closeActiveSocket() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (sock) {
    const old = sock;
    sock = null;
    try {
      old.ev.removeAllListeners();
    } catch (_) {}
    try {
      old.end();
    } catch (_) {}
  }
}

function clearSessionDir() {
  authObj = null;
  try {
    if (fs.existsSync(SESSION_DIR)) {
      fs.rmSync(SESSION_DIR, { recursive: true, force: true });
    }
  } catch (err) {
    console.error('Erro ao limpar pasta de sessão:', err.message);
  }
}

async function postToBackend(endpoint, payload) {
  try {
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': ADMIN_TOKEN,
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const txt = await response.text();
      console.error(`Backend (${endpoint}) respondeu ${response.status}: ${txt}`);
    }
  } catch (err) {
    console.error(`Erro ao chamar ${endpoint} no server.py:`, err.message);
  }
}

function scheduleReconnect(delayMs = 1500) {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    reconnecting = false;
    startWhatsApp();
  }, delayMs);
}

async function startWhatsApp() {
  if (reconnecting) return;
  reconnecting = true;
  try {
    closeActiveSocket();
    if (!authObj) {
      authObj = await useMultiFileAuthState(SESSION_DIR);
    }
    const { state: authState, saveCreds } = authObj;

    if (authState.creds?.me?.id) {
      state = 'connecting';
      currentQr = null;
      connectedPhone = authState.creds.me.id.split(':')[0].split('@')[0] || null;
      connectedName = authState.creds.me.name || null;
    } else {
      state = 'starting';
    }

    let version = [2, 3000, 1043857760];
    try {
      const latest = await fetchLatestBaileysVersion();
      if (latest?.version) version = latest.version;
    } catch (_) {}

    const thisSock = makeWASocket({
      version,
      auth: {
        creds: authState.creds,
        keys: makeCacheableSignalKeyStore(authState.keys, silentLogger),
      },
      printQRInTerminal: false,
      logger: silentLogger,
      browser: Browsers.ubuntu('Chrome'),
      syncFullHistory: false,
      shouldSyncHistoryMessage: () => false,
      shouldIgnoreJid: (jid) => isNonPrivateChat(jid),
      markOnlineOnConnect: false,
      keepAliveIntervalMs: 25000,
      connectTimeoutMs: 60000,
      defaultQueryTimeoutMs: 60000,
      retryRequestDelayMs: 2500,
      maxMsgRetryCount: 2,
    });

    sock = thisSock;

    thisSock.ev.on('creds.update', async () => {
      try {
        await saveCreds();
      } catch (err) {
        console.error('Erro ao salvar credenciais:', err.message);
      }
    });

    thisSock.ev.on('connection.update', async (update) => {
      if (thisSock !== sock) return;
      const { connection, lastDisconnect, qr, isNewLogin } = update;

      if (isNewLogin) {
        currentQr = null;
        state = 'connecting';
        lastError = null;
        try {
          await saveCreds();
        } catch (_) {}
      }

      if (qr && !authState.creds?.me?.id) {
        currentQr = qr;
        state = 'qr_ready';
        lastError = null;
        console.log('QR Code atualizado e disponível na Aba 2 do Painel WhatsAuto.');
      }

      if (connection === 'open') {
        currentQr = null;
        state = 'connected';
        lastError = null;
        const rawId = thisSock.user?.id || authState.creds?.me?.id || '';
        connectedPhone = rawId.split(':')[0].split('@')[0] || 'Conectado';
        connectedName = thisSock.user?.name || authState.creds?.me?.name || '';
        try {
          await saveCreds();
        } catch (_) {}
        console.log(`WhatsApp conectado com sucesso! Número: ${connectedPhone} (${connectedName})`);
      }

      if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const isLoggedOut = statusCode === DisconnectReason.loggedOut;
        const isRestartRequired = statusCode === DisconnectReason.restartRequired;
        lastError = lastDisconnect?.error?.message || `Desconectado (código ${statusCode || 'desconhecido'})`;
        console.log('Conexão WhatsApp fechada:', lastError, 'code:', statusCode);

        try {
          await saveCreds();
        } catch (_) {}

        currentQr = null;

        if (isLoggedOut) {
          console.log('Sessão desconectada pelo celular. Limpando sessão e gerando novo QR Code...');
          connectedPhone = null;
          connectedName = null;
          state = 'disconnected';
          clearSessionDir();
          scheduleReconnect(1500);
        } else {
          state = authState.creds?.me?.id ? 'connecting' : 'disconnected';
          scheduleReconnect(isRestartRequired ? 400 : 1500);
        }
      }
    });

    thisSock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (thisSock !== sock || type !== 'notify') return;
      for (const msg of messages) {
        try {
          if (!msg.message) continue;
          const remoteJid = msg.key.remoteJid || '';
          if (isNonPrivateChat(remoteJid)) continue;

          const text = extractText(msg.message).trim();
          const sender = remoteJid.replace('@s.whatsapp.net', '');

          // Se a mensagem foi enviada pelo próprio aparelho (fromMe):
          if (msg.key.fromMe) {
            if (botSentMessageIds.has(msg.key.id) || text.startsWith('🤖')) {
              botSentMessageIds.delete(msg.key.id);
              continue;
            }
            const hasHumanContent = Boolean(
              text ||
              msg.message.imageMessage ||
              msg.message.audioMessage ||
              msg.message.videoMessage ||
              msg.message.documentMessage
            );
            if (hasHumanContent) {
              await postToBackend('/api/human-activity', {
                from: sender,
                jid: remoteJid,
              });
            }
            continue;
          }

          if (!text) continue;

          const altPhone = (msg.key.remoteJidAlt || msg.key.senderPn || '')
            .replace('@s.whatsapp.net', '')
            .replace('@lid', '')
            .split(':')[0];
          const displayName = [msg.pushName || '', altPhone].filter(Boolean).join(' - ');

          await postToBackend('/api/qr-incoming', {
            id: msg.key.id,
            from: sender,
            jid: remoteJid,
            pushName: displayName,
            text,
          });
        } catch (err) {
          console.error('Erro ao processar mensagem recebida:', err.message);
        }
      }
    });
  } catch (err) {
    lastError = err.message;
    state = 'disconnected';
    console.error('Erro ao iniciar WhatsApp:', err.message);
    scheduleReconnect(2500);
    return;
  }
  reconnecting = false;
}

async function waitUntilConnected(maxWaitMs = 6000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    if (state === 'connected' && sock) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return state === 'connected' && Boolean(sock);
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 1e6) req.destroy();
    });
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  const token = req.headers['x-admin-token'] || '';
  if (ADMIN_TOKEN && token !== ADMIN_TOKEN) {
    return sendJson(res, 401, { error: 'Não autorizado' });
  }

  if (req.method === 'GET' && req.url === '/status') {
    return sendJson(res, 200, {
      state,
      qr: currentQr,
      phone: connectedPhone,
      name: connectedName,
      last_error: lastError,
    });
  }

  if (req.method === 'POST' && req.url === '/send') {
    try {
      const body = await readJsonBody(req);
      const ready = await waitUntilConnected(6000);
      if (!ready || !sock) {
        return sendJson(res, 503, { error: 'WhatsApp ainda não está conectado via QR Code' });
      }
      const rawTo = String(body.to || '').trim();
      const text = String(body.text || '').trim();
      if (!rawTo || !text) {
        return sendJson(res, 400, { error: 'Informe destinatário (to) e texto (text)' });
      }
      const jid = rawTo.includes('@') ? rawTo : `${rawTo.replace(/\D/g, '')}@s.whatsapp.net`;

      // Simula comportamento humano real: pequena pausa de leitura + status "Digitando..." (1,5s a 3s)
      try {
        await sock.presenceSubscribe(jid).catch(() => {});
        await new Promise((r) => setTimeout(r, 400 + Math.floor(Math.random() * 400)));
        await sock.sendPresenceUpdate('composing', jid);
        const typingDelayMs = 1500 + Math.floor(Math.random() * 1500);
        await new Promise((r) => setTimeout(r, typingDelayMs));
        await sock.sendPresenceUpdate('paused', jid);
      } catch (_) {}

      const sent = await sock.sendMessage(jid, { text });
      if (sent?.key?.id) {
        botSentMessageIds.add(sent.key.id);
        setTimeout(() => botSentMessageIds.delete(sent.key.id), 60000);
      }
      return sendJson(res, 200, { ok: true });
    } catch (err) {
      return sendJson(res, 500, { error: err.message });
    }
  }

  if (req.method === 'POST' && req.url === '/reset') {
    try {
      if (sock) {
        try {
          await sock.logout();
        } catch (_) {}
      }
    } catch (_) {}
    closeActiveSocket();
    clearSessionDir();
    currentQr = null;
    connectedPhone = null;
    connectedName = null;
    state = 'starting';
    reconnecting = false;
    startWhatsApp();
    return sendJson(res, 200, { ok: true });
  }

  return sendJson(res, 404, { error: 'Rota não encontrada' });
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.log(`Porta ${BRIDGE_PORT} já está em uso por outra instância da ponte. Encerrando duplicata.`);
    process.exit(0);
  }
});

server.listen(BRIDGE_PORT, '127.0.0.1', () => {
  console.log(`Ponte WhatsApp QR Code rodando em http://127.0.0.1:${BRIDGE_PORT}`);
  startWhatsApp();
});
