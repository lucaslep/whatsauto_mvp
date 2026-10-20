"""Servidor WhatsAuto Empresarial: QR Code, Menu Inicial, Pausa Humana, Sinônimos e Horário Comercial."""
import hashlib
import hmac
import os
import re
import sqlite3
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

ENV_PATH = Path(__file__).with_name('.env')
load_dotenv(ENV_PATH, override=True)
app = Flask(__name__)
DB = os.getenv('DATABASE_PATH', str(Path(__file__).with_name('whatsauto.db')))
LOCK = threading.RLock()
SIMULATION_MODE = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'

DEFAULT_SETTINGS = {
    'bot_prefix': os.getenv('BOT_PREFIX', '🤖 *Atendimento Automático (Robô):*'),
    'welcome_enabled': '1',
    'welcome_message': (
        'Olá! Seja bem-vindo(a) ao nosso atendimento. Como podemos ajudar hoje?\n\n'
        'Digite o número da opção desejada:\n'
        '*1* - Preços e Orçamentos\n'
        '*2* - Horário de Funcionamento\n'
        '*3* - Endereço e Localização\n'
        '*4* - Falar com um Atendente Humano'
    ),
    'welcome_cooldown_hours': '1',
    'human_handoff_keywords': '4, atendente, humano, falar com atendente, vendedor',
    'human_handoff_reply': (
        'Certo! Já avisei nossa equipe e um atendente humano vai continuar seu atendimento '
        'por aqui em instantes.\n_(O atendimento automático foi pausado para você)_.'
    ),
    'human_close_reply': (
        '✅ *Atendimento Encerrado:* Encerramos seu atendimento por aqui. '
        'Agradecemos o seu contato! Sempre que precisar novamente, basta enviar uma nova mensagem.'
    ),
    'human_pause_minutes': '15',
    'cooldown_minutes': '1',
    'bh_enabled': '1',
    'bh_start': '08:30',
    'bh_end': '17:38',
    'bh_weekends': '0',
    'bh_message': (
        'Olá! Recebemos sua mensagem, mas no momento estamos fora do nosso horário de atendimento '
        '(Segunda a Sexta, das 08:30 às 17:38). Assim que retornarmos, nossa equipe responderá você!'
    ),
}


def conn():
    connection = sqlite3.connect(DB, timeout=20)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_text(value):
    """Remove acentos e converte para minúsculas para comparação flexível."""
    nfd = unicodedata.normalize('NFD', str(value or '').casefold().strip())
    return ''.join(ch for ch in nfd if unicodedata.category(ch) != 'Mn')


def clean_phone(sender):
    return (
        str(sender or '')
        .replace('@s.whatsapp.net', '')
        .replace('@lid', '')
        .split(':')[0]
        .split('@')[0]
        .strip()
    )


def setup():
    with conn() as db:
        db.execute(
            'CREATE TABLE IF NOT EXISTS rules ('
            'id INTEGER PRIMARY KEY, '
            'keyword TEXT NOT NULL UNIQUE, '
            'reply TEXT NOT NULL, '
            'enabled INTEGER NOT NULL DEFAULT 1)'
        )
        db.execute(
            'CREATE TABLE IF NOT EXISTS events ('
            'message_id TEXT PRIMARY KEY, '
            'sender TEXT NOT NULL, '
            'incoming TEXT NOT NULL, '
            'reply TEXT, '
            'status TEXT NOT NULL, '
            'received_at TEXT NOT NULL, '
            'push_name TEXT DEFAULT "")'
        )
        try:
            db.execute("ALTER TABLE events ADD COLUMN push_name TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        db.execute(
            'CREATE TABLE IF NOT EXISTS paused_contacts ('
            'sender TEXT PRIMARY KEY, '
            'paused_until TEXT NOT NULL, '
            'reason TEXT)'
        )
        db.execute(
            'CREATE TABLE IF NOT EXISTS active_sessions ('
            'sender TEXT PRIMARY KEY, '
            'jid TEXT NOT NULL, '
            'push_name TEXT DEFAULT "", '
            'expires_at TEXT NOT NULL, '
            'session_type TEXT DEFAULT "bot")'
        )
        db.execute(
            'CREATE TABLE IF NOT EXISTS settings ('
            'key TEXT PRIMARY KEY, '
            'value TEXT NOT NULL)'
        )
        for k, v in DEFAULT_SETTINGS.items():
            db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, str(v)))

        # Sincroniza contatos que já estavam em paused_contacts com active_sessions
        for prow in db.execute('SELECT sender, paused_until FROM paused_contacts').fetchall():
            p_phone = clean_phone(prow['sender'])
            ev_row = db.execute(
                'SELECT sender, push_name FROM events WHERE sender LIKE ? ORDER BY rowid DESC LIMIT 1',
                (f'{p_phone}%',),
            ).fetchone()
            jid_val = ev_row['sender'] if ev_row else p_phone
            pname_val = (ev_row['push_name'] or '') if ev_row else ''
            db.execute(
                'INSERT OR IGNORE INTO active_sessions (sender, jid, push_name, expires_at, session_type) '
                'VALUES (?, ?, ?, ?, ?)',
                (p_phone, jid_val, pname_val, prow['paused_until'], 'human'),
            )

        # Garante que o intervalo de inatividade seja 15 min, repetição do menu 1h e horário 08:30 às 17:38
        db.execute("UPDATE settings SET value='1' WHERE key='welcome_cooldown_hours' AND value='12'")
        db.execute("UPDATE settings SET value='15' WHERE key='human_pause_minutes' AND value IN ('60', '120')")
        db.execute("UPDATE settings SET value='1' WHERE key='cooldown_minutes' AND value='30'")
        db.execute("UPDATE settings SET value='08:30' WHERE key='bh_start' AND value='08:00'")
        db.execute("UPDATE settings SET value='17:38' WHERE key='bh_end' AND value='18:00'")
        db.execute(
            "UPDATE settings SET value='Olá! Recebemos sua mensagem, mas no momento estamos fora do nosso horário de atendimento (Segunda a Sexta, das 08:30 às 17:38). Assim que retornarmos, nossa equipe responderá você!' "
            "WHERE key='bh_message' AND value LIKE '%08:00 às 18:00%'"
        )

        # Atualiza regras iniciais simples para incluir números do menu e sinônimos
        db.execute(
            "UPDATE rules SET keyword='1, preço, valor, quanto custa, orçamento' WHERE keyword='preço'"
        )
        db.execute(
            "UPDATE rules SET keyword='2, horário, expediente, aberto, funciona' WHERE keyword='horário'"
        )
        db.execute(
            "UPDATE rules SET reply='Atendemos de segunda a sexta, das 08:30 às 17:38.' "
            "WHERE keyword LIKE '2,%' AND reply='Atendemos de segunda a sexta, das 9h às 18h.'"
        )
        db.execute(
            "UPDATE rules SET keyword='3, endereço, localização, onde fica' WHERE keyword='endereço'"
        )

        existing_count = db.execute('SELECT COUNT(*) FROM rules').fetchone()[0]
        if existing_count == 0:
            db.execute(
                'INSERT OR IGNORE INTO rules (keyword, reply) VALUES (?, ?)',
                (
                    '1, preço, valor, quanto custa, orçamento',
                    'Olá! Conte qual produto ou serviço você procura para enviarmos os valores e detalhes.',
                ),
            )
            db.execute(
                'INSERT OR IGNORE INTO rules (keyword, reply) VALUES (?, ?)',
                (
                    '2, horário, expediente, aberto, funciona',
                    'Atendemos de segunda a sexta, das 08:30 às 17:38.',
                ),
            )
            db.execute(
                'INSERT OR IGNORE INTO rules (keyword, reply) VALUES (?, ?)',
                (
                    '3, endereço, localização, onde fica',
                    'Estamos à disposição! Solicite nossa localização exata ou fale com um atendente digitando 4.',
                ),
            )


def get_settings():
    cfg = dict(DEFAULT_SETTINGS)
    with conn() as db:
        for row in db.execute('SELECT key, value FROM settings').fetchall():
            cfg[row['key']] = row['value']
    return cfg


def secret_equal(actual, expected):
    return bool(expected) and hmac.compare_digest(str(actual), str(expected))


def admin_ok():
    supplied = request.headers.get('X-Admin-Token', '')
    return secret_equal(supplied, os.getenv('ADMIN_TOKEN', ''))


def auth_error():
    return jsonify({'error': 'Não autorizado'}), 401


def format_bot_reply(reply_text, cfg=None):
    if not reply_text:
        return None
    if cfg is None:
        cfg = get_settings()
    prefix = str(cfg.get('bot_prefix', '')).strip()
    if not prefix or reply_text.startswith('🤖') or reply_text.startswith(prefix):
        return reply_text
    return f'{prefix}\n{reply_text}'


def keyword_matches(keyword_expr, norm_body, body_tokens):
    """Verifica se qualquer sinônimo separado por vírgula corresponde à mensagem."""
    parts = [normalize_text(p) for p in str(keyword_expr or '').split(',')]
    parts = [p for p in parts if p]
    parts.sort(key=len, reverse=True)
    for kw in parts:
        if len(kw) <= 2 or kw.isdigit():
            if norm_body == kw or kw in body_tokens:
                return True
        else:
            if kw in norm_body:
                return True
    return False


def is_outside_business_hours(cfg):
    if str(cfg.get('bh_enabled', '0')) != '1':
        return False
    now = datetime.now()
    if now.weekday() >= 5 and str(cfg.get('bh_weekends', '0')) != '1':
        return True
    start_str = str(cfg.get('bh_start', '08:00')).strip()
    end_str = str(cfg.get('bh_end', '18:00')).strip()
    try:
        sh, sm = [int(x) for x in start_str.split(':')[:2]]
        eh, em = [int(x) for x in end_str.split(':')[:2]]
        now_mins = now.hour * 60 + now.minute
        start_mins = sh * 60 + sm
        end_mins = eh * 60 + em
        return now_mins < start_mins or now_mins >= end_mins
    except Exception:
        return False


def resolve_whatsapp_jid(sender_or_phone):
    raw = str(sender_or_phone or '').strip()
    if '@' in raw:
        return raw, ''
    phone = clean_phone(raw)
    if not phone:
        return raw, ''
    with conn() as db:
        srow = db.execute(
            'SELECT jid, push_name FROM active_sessions WHERE sender=?', (phone,)
        ).fetchone()
        if srow and srow['jid']:
            return srow['jid'], (srow['push_name'] or '')
        erow = db.execute(
            'SELECT sender, push_name FROM events WHERE sender LIKE ? ORDER BY rowid DESC LIMIT 1',
            (f'{phone}%',),
        ).fetchone()
        if erow and erow['sender']:
            return erow['sender'], (erow['push_name'] or '')
    return phone, ''


def touch_active_session(sender, push_name='', session_type='bot', minutes=None):
    phone = clean_phone(sender)
    if not phone:
        return
    cfg = get_settings()
    if minutes is None:
        minutes = int(cfg.get('human_pause_minutes', '15') or '15')
    if minutes <= 0:
        return
    jid, prev_name = resolve_whatsapp_jid(sender)
    final_jid = sender if '@' in str(sender or '') else jid
    final_name = push_name or prev_name
    expires_iso = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    with conn() as db:
        db.execute(
            'INSERT OR REPLACE INTO active_sessions (sender, jid, push_name, expires_at, session_type) '
            'VALUES (?, ?, ?, ?, ?)',
            (phone, final_jid, final_name, expires_iso, session_type),
        )


def finish_attendance(sender_or_phone, close_reason='Encerrado por inatividade (15 min)'):
    """Encerra o atendimento do cliente, remove das tabelas ativas e envia a mensagem de encerramento no WhatsApp."""
    phone = clean_phone(sender_or_phone)
    if not phone:
        return False

    with LOCK:
        jid, push_name = resolve_whatsapp_jid(sender_or_phone)
        with conn() as db:
            p_del = db.execute(
                'DELETE FROM paused_contacts WHERE sender=? OR sender LIKE ?',
                (phone, f'{phone}%'),
            ).rowcount
            s_del = db.execute(
                'DELETE FROM active_sessions WHERE sender=? OR sender LIKE ?',
                (phone, f'{phone}%'),
            ).rowcount
            if p_del == 0 and s_del == 0:
                return False

        cfg = get_settings()
        raw_close = str(cfg.get('human_close_reply', '')).strip()
        if not raw_close:
            return True

        close_text = format_bot_reply(raw_close, cfg)
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        mid = f'close-{phone}-{int(now_dt.timestamp() * 1000)}'

        try:
            send_whatsapp(jid, close_text)
            st = 'closed_session'
        except Exception:
            app.logger.exception('Falha ao enviar mensagem de encerramento para %s', jid)
            st = 'error'

        with conn() as db:
            db.execute(
                'INSERT OR REPLACE INTO events (message_id, sender, incoming, reply, status, received_at, push_name) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (mid, jid, f'[{close_reason}]', close_text, st, now_iso, push_name),
            )
    return True


def expire_due_sessions():
    """Verifica todos os atendimentos cujo tempo de inatividade (15 min) já esgotou e envia mensagem de encerramento."""
    now_iso = datetime.now(timezone.utc).isoformat()
    expired_phones = set()
    with conn() as db:
        for r in db.execute(
            'SELECT sender FROM paused_contacts WHERE paused_until <= ?', (now_iso,)
        ).fetchall():
            expired_phones.add(clean_phone(r['sender']))
        for r in db.execute(
            'SELECT sender FROM active_sessions WHERE expires_at <= ?', (now_iso,)
        ).fetchall():
            expired_phones.add(clean_phone(r['sender']))

    for phone in expired_phones:
        if phone:
            finish_attendance(phone, close_reason='Atendimento encerrado após 15 min sem conversa')


def is_contact_paused(sender):
    phone = clean_phone(sender)
    if not phone:
        return False
    expire_due_sessions()
    now_dt = datetime.now(timezone.utc)
    cfg = get_settings()
    pause_mins = int(cfg.get('human_pause_minutes', '15') or '15')
    with conn() as db:
        row = db.execute(
            'SELECT sender, paused_until, reason FROM paused_contacts WHERE sender=? OR sender LIKE ?',
            (sender, f'{phone}%'),
        ).fetchone()
        if row and pause_mins > 0:
            # Cliente falou durante o atendimento: renova o cronômetro de 15 min de inatividade
            new_until = (now_dt + timedelta(minutes=pause_mins)).isoformat()
            db.execute(
                'UPDATE paused_contacts SET paused_until = ? WHERE sender = ?',
                (new_until, row['sender']),
            )
    if row and pause_mins > 0:
        touch_active_session(sender, session_type='human', minutes=pause_mins)
    return bool(row)


def pause_contact(sender, minutes=15, reason='Atendimento humano', push_name=''):
    phone = clean_phone(sender)
    if not phone or minutes <= 0:
        return
    until_iso = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    with conn() as db:
        db.execute(
            'INSERT OR REPLACE INTO paused_contacts (sender, paused_until, reason) VALUES (?, ?, ?)',
            (phone, until_iso, reason),
        )
    touch_active_session(sender, push_name=push_name, session_type='human', minutes=minutes)


def had_recent_welcome(sender, hours=1.0, cfg=None):
    """Verifica se o cliente já recebeu o Menu de Boas-Vindas dentro da janela de `hours` (padrão 1h)."""
    if hours <= 0 or not sender:
        return False
    phone = clean_phone(sender)
    if cfg is None:
        cfg = get_settings()
    welcome_snippet = str(cfg.get('welcome_message', '')).strip()[:28] or 'Seja bem-vindo'
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with conn() as db:
        row = db.execute(
            "SELECT 1 FROM events WHERE (sender=? OR sender LIKE ?) "
            "AND status IN ('sent', 'simulated') "
            "AND (reply LIKE ? OR reply LIKE '%Seja bem-vindo%' OR reply LIKE '%opção desejada%') "
            "AND received_at >= ? LIMIT 1",
            (sender, f'{phone}%', f'%{welcome_snippet}%', cutoff),
        ).fetchone()
    return bool(row)


def should_send_welcome_menu(sender, cfg=None):
    """Retorna True SOMENTE quando for:
    1) A primeira mensagem do dia dessa pessoa; OU
    2) Quando passaram >= 15 min sem nenhuma conversa de ambos os lados
       (ou quando o atendimento anterior já foi encerrado)."""
    if not sender:
        return False
    if cfg is None:
        cfg = get_settings()
    phone = clean_phone(sender)
    inactivity_mins = float(cfg.get('welcome_inactivity_minutes', cfg.get('human_pause_minutes', '15')) or '15')
    now_utc = datetime.now(timezone.utc)
    inactivity_cutoff = (now_utc - timedelta(minutes=inactivity_mins)).isoformat()

    with conn() as db:
        last_ev = db.execute(
            'SELECT message_id, status, received_at FROM events '
            'WHERE (sender=? OR sender LIKE ?) ORDER BY rowid DESC LIMIT 1',
            (sender, f'{phone}%'),
        ).fetchone()

    if not last_ev:
        return True

    # Se o atendimento anterior já foi encerrado (por 15 min de inatividade ou manualmente), reinicia com o Menu Inicial
    if last_ev['status'] in ('closed_session', 'paused_human') or str(last_ev['message_id'] or '').startswith('close-'):
        return True

    raw_ts = str(last_ev['received_at'] or '')
    if not raw_ts or raw_ts <= inactivity_cutoff:
        return True

    # Verifica se é a primeira mensagem do dia (no fuso horário local da máquina)
    try:
        ev_dt_local = datetime.fromisoformat(raw_ts).astimezone()
        now_local = datetime.now().astimezone()
        if ev_dt_local.date() < now_local.date():
            return True
    except Exception:
        pass

    return False


GREETING_WORDS = {
    'oi', 'oii', 'oiii', 'ola', 'opa', 'bom dia', 'boa tarde', 'boa noite',
    'menu', 'inicio', 'iniciar', 'comecar', 'ajuda', 'hello', 'hi', 'eae', 'e ai',
}


def is_simple_greeting(norm_body, body_tokens):
    if norm_body in GREETING_WORDS:
        return True
    # Se a mensagem curta contém apenas saudação (ex.: "oi bom dia", "ola tudo bem")
    if len(body_tokens) <= 4 and any(g in norm_body for g in ('oi', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'opa')):
        return True
    return False


def decide_for_message(body, sender='', is_simulation=False, push_name=''):
    """Retorna (reply_text, decision_type) onde decision_type pode ser:
    'rule', 'human_handoff', 'outside_hours', 'welcome', ou 'no_rule'."""
    norm_body = normalize_text(body)
    if not norm_body:
        return None, 'no_rule'
    body_tokens = set(re.findall(r'[a-z0-9]+', norm_body))
    cfg = get_settings()
    welcome_on = str(cfg.get('welcome_enabled', '1')) == '1'

    # 1. Verifica se o cliente pediu explicitamente para falar com atendente humano (opção 4 / atendente)
    handoff_kw = cfg.get('human_handoff_keywords', '')
    if handoff_kw and keyword_matches(handoff_kw, norm_body, body_tokens):
        if is_outside_business_hours(cfg):
            return format_bot_reply(cfg.get('bh_message', ''), cfg), 'outside_hours'
        if not is_simulation and sender:
            pause_mins = int(cfg.get('human_pause_minutes', '15') or '15')
            reason_txt = f'Solicitou atendente ({push_name})' if push_name else 'Solicitou atendente no menu'
            pause_contact(sender, minutes=pause_mins, reason=reason_txt, push_name=push_name)
        return format_bot_reply(cfg.get('human_handoff_reply', ''), cfg), 'human_handoff'

    # 2. Verifica regras pré-definidas (1 - Preços, 2 - Horário, 3 - Endereço, etc.)
    with conn() as db:
        rules = db.execute(
            'SELECT keyword, reply FROM rules WHERE enabled = 1 ORDER BY length(keyword) DESC'
        ).fetchall()
    for rule in rules:
        if keyword_matches(rule['keyword'], norm_body, body_tokens):
            return format_bot_reply(rule['reply'], cfg), 'rule'

    # 3. Se não bateu em nenhuma regra pré-definida e está fora do horário comercial
    if is_outside_business_hours(cfg):
        return format_bot_reply(cfg.get('bh_message', ''), cfg), 'outside_hours'

    # 4. Mensagem SEM resposta pré-definida:
    # - Se for a 1ª mensagem do dia da pessoa OU após 15 min sem conversa (no WhatsApp real),
    #   ou se for uma saudação inicial no Simulador ("Oi, bom dia!"), envia o Menu Inicial (1, 2, 3, 4).
    # - Caso contrário (a pessoa já está conversando ou perguntou algo específico sem regra, como "IntelectualSys"),
    #   chama SEMPRE um Atendente Humano!
    if welcome_on:
        if is_simulation:
            if is_simple_greeting(norm_body, body_tokens):
                return format_bot_reply(cfg.get('welcome_message', ''), cfg), 'welcome'
        elif sender and should_send_welcome_menu(sender, cfg=cfg):
            return format_bot_reply(cfg.get('welcome_message', ''), cfg), 'welcome'

    # 5. Pergunta/resposta sem regra pré-definida (ex.: "IntelectualSys") -> Transfere para Atendente Humano!
    if not is_simulation and sender:
        pause_mins = int(cfg.get('human_pause_minutes', '15') or '15')
        short_msg = body.strip().replace('\n', ' ')[:40]
        reason_txt = f'Dúvida específica: "{short_msg}" ({push_name})' if push_name else f'Dúvida específica: "{short_msg}"'
        pause_contact(sender, minutes=pause_mins, reason=reason_txt, push_name=push_name)
    return format_bot_reply(cfg.get('human_handoff_reply', ''), cfg), 'human_handoff'


def decide(body):
    reply, _ = decide_for_message(body, sender='', is_simulation=True)
    return reply


def is_in_cooldown(sender, reply, decision_type='rule'):
    if not sender or not reply or decision_type == 'human_handoff':
        return False
    phone = clean_phone(sender)
    # Para o Menu de Boas-Vindas, evita apenas disparo duplo se o cliente mandar 2 linhas no mesmo instante (15s)
    if decision_type == 'welcome':
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
    else:
        cfg = get_settings()
        cooldown_minutes = float(cfg.get('cooldown_minutes', '1') or '0')
        if cooldown_minutes <= 0:
            return False
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)).isoformat()
    with conn() as db:
        row = db.execute(
            "SELECT 1 FROM events WHERE (sender=? OR sender LIKE ?) AND reply=? AND status IN ('sent', 'simulated', 'human_handoff') AND received_at >= ? LIMIT 1",
            (sender, f'{phone}%', reply, cutoff),
        ).fetchone()
    return bool(row)


def send_whatsapp(to, text):
    if SIMULATION_MODE:
        return 'simulated'

    mode = os.getenv('CONNECTION_MODE', 'qr').lower().strip()
    if mode == 'qr':
        bridge_url = os.getenv('QR_BRIDGE_URL', 'http://127.0.0.1:5001').rstrip('/')
        admin_token = os.getenv('ADMIN_TOKEN', '')
        response = requests.post(
            f'{bridge_url}/send',
            json={'to': to, 'text': text},
            headers={'X-Admin-Token': admin_token},
            timeout=15,
        )
        response.raise_for_status()
        return 'sent'

    token = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
    number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
    version = os.getenv('GRAPH_API_VERSION', 'v23.0')
    if not all([token, number_id]):
        raise RuntimeError('Token ou Phone Number ID ausente')
    url = f'https://graph.facebook.com/{version}/{number_id}/messages'
    response = requests.post(
        url,
        json={
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {'body': text},
        },
        headers={'Authorization': f'Bearer {token}'},
        timeout=15,
    )
    response.raise_for_status()
    return 'sent'


def handle_message(msg):
    mid = msg.get('id')
    sender = msg.get('from')
    if not mid or not sender or msg.get('type') != 'text':
        return
    incoming = msg.get('text', {}).get('body', '')
    push_name = str(msg.get('push_name', '') or '').strip()[:120]
    now_iso = datetime.now(timezone.utc).isoformat()

    with LOCK:
        with conn() as db:
            if db.execute('SELECT 1 FROM events WHERE message_id=?', (mid,)).fetchone():
                return

        # Se o contato estiver pausado (em atendimento humano), não envia resposta automática
        if is_contact_paused(sender):
            with conn() as db:
                db.execute(
                    'INSERT INTO events (message_id, sender, incoming, reply, status, received_at, push_name) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (mid, sender, incoming, None, 'paused_human', now_iso, push_name),
                )
            return

        reply, decision_type = decide_for_message(
            incoming, sender=sender, is_simulation=False, push_name=push_name
        )

        # Registra ou renova a sessão ativa de 15 minutos (exceto quando fora de horário comercial)
        if decision_type != 'outside_hours':
            stype = 'human' if decision_type == 'human_handoff' else 'bot'
            touch_active_session(sender, push_name=push_name, session_type=stype)

        with conn() as db:
            if reply and is_in_cooldown(sender, reply, decision_type=decision_type):
                db.execute(
                    'INSERT INTO events (message_id, sender, incoming, reply, status, received_at, push_name) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (mid, sender, incoming, reply, 'cooldown', now_iso, push_name),
                )
                return
            db.execute(
                'INSERT INTO events (message_id, sender, incoming, reply, status, received_at, push_name) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (mid, sender, incoming, reply, 'processing', now_iso, push_name),
            )

    status = 'no_rule'
    if reply:
        try:
            sent_status = send_whatsapp(sender, reply)
            status = 'human_handoff' if decision_type == 'human_handoff' else sent_status
        except Exception:
            app.logger.exception('Falha ao responder mensagem %s', mid)
            status = 'error'
    with conn() as db:
        db.execute('UPDATE events SET status=? WHERE message_id=?', (status, mid))


@app.get('/webhook')
def verify_webhook():
    if request.args.get('hub.mode') == 'subscribe' and secret_equal(
        request.args.get('hub.verify_token', ''), os.getenv('META_VERIFY_TOKEN', '')
    ):
        return request.args.get('hub.challenge', ''), 200, {'Content-Type': 'text/plain'}
    return 'Forbidden', 403


@app.post('/webhook')
def webhook():
    secret = os.getenv('META_APP_SECRET', '')
    signature = request.headers.get('X-Hub-Signature-256', '')
    raw = request.get_data()
    calculated = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(signature, calculated):
        return 'Forbidden', 403
    payload = request.get_json(silent=True) or {}
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') != 'messages':
                continue
            for msg in change.get('value', {}).get('messages', []):
                handle_message(msg)
    return jsonify({'ok': True})


@app.post('/api/qr-incoming')
def qr_incoming():
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    mid = str(data.get('id', '')).strip()
    sender = str(data.get('jid') or data.get('from') or '').strip()
    text = str(data.get('text', '')).strip()
    push_name = str(data.get('pushName') or '').strip()
    if not mid or not sender or not text:
        return jsonify({'error': 'Dados incompletos'}), 400
    handle_message({
        'id': mid,
        'from': sender,
        'push_name': push_name,
        'type': 'text',
        'text': {'body': text},
    })
    return jsonify({'ok': True})


@app.post('/api/human-takeover')
def human_takeover():
    """Acionado manualmente ou quando um humano assume o atendimento."""
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    sender = clean_phone(data.get('from') or data.get('jid') or '')
    if not sender:
        return jsonify({'error': 'Número ausente'}), 400
    cfg = get_settings()
    pause_mins = int(cfg.get('human_pause_minutes', '15') or '15')
    pause_contact(sender, minutes=pause_mins, reason='Atendente respondeu pelo celular/Web')
    return jsonify({'ok': True, 'sender': sender, 'paused_minutes': pause_mins})


@app.post('/api/human-activity')
def human_activity():
    """Renova o cronômetro de 15 minutos quando o atendente humano envia mensagem para um cliente em atendimento."""
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    raw_target = str(data.get('jid') or data.get('from') or '').strip()
    sender = clean_phone(raw_target)
    if not sender:
        return jsonify({'error': 'Número ausente'}), 400
    expire_due_sessions()
    now_dt = datetime.now(timezone.utc)
    cfg = get_settings()
    pause_mins = int(cfg.get('human_pause_minutes', '15') or '15')
    renewed = False
    new_until = (now_dt + timedelta(minutes=pause_mins)).isoformat()
    with conn() as db:
        row = db.execute(
            'SELECT sender FROM paused_contacts WHERE sender=? OR sender LIKE ?',
            (sender, f'{sender}%'),
        ).fetchone()
        if row and pause_mins > 0:
            db.execute(
                'UPDATE paused_contacts SET paused_until = ? WHERE sender = ?',
                (new_until, row['sender']),
            )
            renewed = True
        srow = db.execute(
            'SELECT sender FROM active_sessions WHERE sender=? OR sender LIKE ?',
            (sender, f'{sender}%'),
        ).fetchone()
        if srow and pause_mins > 0:
            db.execute(
                'UPDATE active_sessions SET expires_at = ? WHERE sender = ?',
                (new_until, srow['sender']),
            )
            renewed = True
    return jsonify({'ok': True, 'sender': sender, 'renewed': renewed, 'paused_minutes': pause_mins})


@app.get('/api/paused')
def list_paused():
    if not admin_ok():
        return auth_error()
    expire_due_sessions()
    with conn() as db:
        rows = db.execute('SELECT * FROM paused_contacts ORDER BY paused_until DESC').fetchall()
        return jsonify([dict(r) for r in rows])


@app.post('/api/paused')
def add_paused():
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    sender = re.sub(r'\D', '', str(data.get('sender', '')))
    if not sender:
        return jsonify({'error': 'Informe o número com DDD (ex.: 5511999999999)'}), 400
    cfg = get_settings()
    mins = int(data.get('minutes') or cfg.get('human_pause_minutes', '15') or '15')
    reason = str(data.get('reason') or 'Pausado manualmente pelo painel')
    pause_contact(sender, minutes=mins, reason=reason)
    return jsonify({'ok': True})


@app.delete('/api/paused/<path:sender>')
def remove_paused(sender):
    if not admin_ok():
        return auth_error()
    finish_attendance(sender, close_reason='Atendimento encerrado pelo atendente')
    return jsonify({'ok': True})


@app.get('/api/settings')
def read_settings():
    if not admin_ok():
        return auth_error()
    return jsonify(get_settings())


@app.post('/api/settings')
def save_settings():
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    with conn() as db:
        for k, v in data.items():
            if k in DEFAULT_SETTINGS:
                db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, str(v)))
    return jsonify({'ok': True, 'settings': get_settings()})


@app.get('/api/qr/status')
def qr_status():
    if not admin_ok():
        return auth_error()
    bridge_url = os.getenv('QR_BRIDGE_URL', 'http://127.0.0.1:5001').rstrip('/')
    admin_token = os.getenv('ADMIN_TOKEN', '')
    try:
        r = requests.get(
            f'{bridge_url}/status',
            headers={'X-Admin-Token': admin_token},
            timeout=4,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as exc:
        return jsonify({
            'state': 'bridge_offline',
            'qr': None,
            'phone': None,
            'name': None,
            'last_error': f'Ponte QR Code offline ({exc})',
        })


@app.post('/api/qr/reset')
def qr_reset():
    if not admin_ok():
        return auth_error()
    bridge_url = os.getenv('QR_BRIDGE_URL', 'http://127.0.0.1:5001').rstrip('/')
    admin_token = os.getenv('ADMIN_TOKEN', '')
    try:
        r = requests.post(
            f'{bridge_url}/reset',
            headers={'X-Admin-Token': admin_token},
            timeout=8,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as exc:
        return jsonify({'error': str(exc)}), 502


@app.get('/api/status')
def status():
    if not admin_ok():
        return auth_error()
    cfg = get_settings()
    return jsonify({
        'simulation_mode': SIMULATION_MODE,
        'connection_mode': os.getenv('CONNECTION_MODE', 'qr').lower().strip(),
        'outside_business_hours': is_outside_business_hours(cfg),
    })


@app.post('/api/mode/toggle')
def toggle_mode():
    global SIMULATION_MODE
    if not admin_ok():
        return auth_error()
    SIMULATION_MODE = not SIMULATION_MODE
    return jsonify({'simulation_mode': SIMULATION_MODE})


@app.post('/api/simulate')
def simulate():
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    body = str(data.get('message', ''))[:4096]
    reply, decision_type = decide_for_message(body, sender='', is_simulation=True)
    return jsonify({'reply': reply, 'decision_type': decision_type, 'sent': False})


@app.get('/api/rules')
def list_rules():
    if not admin_ok():
        return auth_error()
    with conn() as db:
        return jsonify([dict(r) for r in db.execute('SELECT * FROM rules ORDER BY id ASC')])


@app.post('/api/rules')
def add_rule():
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    keyword = str(data.get('keyword', '')).strip()[:300]
    reply = str(data.get('reply', '')).strip()[:4096]
    if not keyword or not reply:
        return jsonify({'error': 'Informe palavra-chave e resposta'}), 400
    try:
        with conn() as db:
            db.execute('INSERT INTO rules (keyword, reply) VALUES (?, ?)', (keyword, reply))
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Palavra-chave já cadastrada'}), 409
    return jsonify({'ok': True}), 201


@app.put('/api/rules/<int:rule_id>')
def update_rule(rule_id):
    if not admin_ok():
        return auth_error()
    data = request.get_json(silent=True) or {}
    keyword = str(data.get('keyword', '')).strip()[:300]
    reply = str(data.get('reply', '')).strip()[:4096]
    if not keyword or not reply:
        return jsonify({'error': 'Informe palavra-chave e resposta'}), 400
    try:
        with conn() as db:
            result = db.execute(
                'UPDATE rules SET keyword=?, reply=? WHERE id=?',
                (keyword, reply, rule_id),
            )
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Já existe outra regra com essa mesma palavra-chave'}), 409
    return jsonify({'ok': result.rowcount > 0})


@app.post('/api/rules/<int:rule_id>/toggle')
def toggle_rule(rule_id):
    if not admin_ok():
        return auth_error()
    with conn() as db:
        result = db.execute('UPDATE rules SET enabled = 1 - enabled WHERE id=?', (rule_id,))
    return jsonify({'ok': result.rowcount > 0})


@app.delete('/api/rules/<int:rule_id>')
def delete_rule(rule_id):
    if not admin_ok():
        return auth_error()
    with conn() as db:
        result = db.execute('DELETE FROM rules WHERE id=?', (rule_id,))
    return jsonify({'ok': result.rowcount > 0})


@app.get('/api/events')
def events():
    if not admin_ok():
        return auth_error()
    expire_due_sessions()
    with conn() as db:
        return jsonify([dict(r) for r in db.execute('SELECT * FROM events ORDER BY received_at DESC LIMIT 80')])


def _session_expiry_loop():
    while True:
        try:
            expire_due_sessions()
        except Exception:
            pass
        time.sleep(5)


setup()
if __name__ == '__main__':
    from waitress import serve
    threading.Thread(target=_session_expiry_loop, daemon=True).start()
    host = os.getenv('SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('SERVER_PORT', '5000'))
    serve(app, host=host, port=port)
