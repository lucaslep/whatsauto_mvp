"""Painel Desktop Empresarial para o WhatsAuto (Regras, Sinônimos, Edição, QR Code, Pausa Humana, Menu e Horário)."""
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    import winsound
except ImportError:
    winsound = None

import qrcode
import requests
from dotenv import load_dotenv

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR if (BASE_DIR / 'server.py').exists() else BASE_DIR.parent
ENV_FILE = BASE_DIR / '.env'

if not ENV_FILE.exists():
    try:
        default_url = 'http://127.0.0.1:5000' if (BASE_DIR / 'server.py').exists() else 'http://192.168.0.213:5000'
        ENV_FILE.write_text(
            f'# Gerado automaticamente pelo WhatsAutoPanel\n'
            f'BACKEND_URL={default_url}\n'
            f'ADMIN_TOKEN=whatsauto-token-admin-local\n',
            encoding='utf-8',
        )
    except Exception:
        pass

load_dotenv(ENV_FILE, override=True)
if not os.getenv('ADMIN_TOKEN') and (PROJECT_DIR / '.env').exists():
    load_dotenv(PROJECT_DIR / '.env', override=True)

URL = os.getenv('BACKEND_URL', 'http://192.168.0.213:5000').rstrip('/')
TOKEN = os.getenv('ADMIN_TOKEN', 'whatsauto-token-admin-local')
_LAST_START_ATTEMPT = 0.0


# ==================== PALETA DE CORES MODERNA (WHATSAPP BUSINESS SAAS) ====================
THEME = {
    'bg_app': '#F0F2F5',          # Fundo geral estilo WhatsApp Web moderno
    'bg_card': '#FFFFFF',         # Fundo dos cartões
    'bg_header': '#0B141A',       # Topo escuro executivo
    'bg_subheader': '#111B21',    # Faixa de KPIs/Status no topo
    'brand_green': '#00A884',     # Verde principal WhatsApp Business
    'brand_green_dark': '#008069',
    'brand_teal': '#075E54',
    'accent_blue': '#0284C7',
    'slate_dark': '#1E293B',
    'slate_med': '#475569',
    'slate_light': '#64748B',
    'border': '#E2E8F0',
    'input_bg': '#F8FAFC',
    'input_border': '#CBD5E1',
    'danger': '#EF4444',
    'danger_dark': '#DC2626',
    'warning': '#F59E0B',
    'success_bg': '#ECFDF5',
    'warning_bg': '#FFFBEB',
    'danger_bg': '#FEF2F2',
}


def _port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(('127.0.0.1', port)) == 0


def ensure_local_services():
    """Se os arquivos do servidor existirem nesta máquina e estiverem desligados, inicia automaticamente."""
    global _LAST_START_ATTEMPT
    if not (PROJECT_DIR / 'server.py').exists():
        return
    now = time.monotonic()
    if now - _LAST_START_ATTEMPT < 15.0:
        return
    _LAST_START_ATTEMPT = now

    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    py_exe = PROJECT_DIR / '.venv' / 'Scripts' / 'python.exe'
    if not py_exe.exists():
        py_exe = Path(sys.executable)
    server_script = PROJECT_DIR / 'server.py'
    bridge_script = PROJECT_DIR / 'whatsapp_qr_bridge.js'

    if not _port_open(5000) and server_script.exists():
        try:
            subprocess.Popen([str(py_exe), str(server_script)], cwd=str(PROJECT_DIR), creationflags=flags)
        except Exception:
            pass

    if not _port_open(5001) and bridge_script.exists():
        try:
            subprocess.Popen(['node', str(bridge_script)], cwd=str(PROJECT_DIR), creationflags=flags)
        except Exception:
            pass


ensure_local_services()


def api(method, path, **kwargs):
    global URL
    if not TOKEN:
        raise RuntimeError('Configure ADMIN_TOKEN no arquivo .env')
    try:
        r = requests.request(
            method,
            URL + path,
            headers={'X-Admin-Token': TOKEN},
            timeout=5,
            **kwargs,
        )
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        alt_url = 'http://127.0.0.1:5000' if '127.0.0.1' not in URL else 'http://192.168.0.213:5000'
        r = requests.request(
            method,
            alt_url + path,
            headers={'X-Admin-Token': TOKEN},
            timeout=5,
            **kwargs,
        )
        r.raise_for_status()
        URL = alt_url
        return r.json()


try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('whatsauto.empresarial.painel.v5')
except Exception:
    pass

root = tk.Tk()
root.title('WhatsAuto Empresarial — Central Inteligente de Atendimento WhatsApp')
root.geometry('1180x820')
root.minsize(1000, 700)
root.configure(bg=THEME['bg_app'])
try:
    root.state('zoomed')
except Exception:
    pass

try:
    bundle_dir = Path(getattr(sys, '_MEIPASS', BASE_DIR))
    for candidate in (bundle_dir / 'whatsauto.ico', BASE_DIR / 'whatsauto.ico', PROJECT_DIR / 'whatsauto.ico'):
        if candidate.exists():
            root.iconbitmap(default=str(candidate))
            root.wm_iconbitmap(str(candidate))
            break
except Exception:
    pass

root.lift()
root.attributes('-topmost', True)
root.after(800, lambda: root.attributes('-topmost', False))
root.focus_force()

# ==================== ESTILIZAÇÃO TTK AVANÇADA ====================
style = ttk.Style(root)
try:
    style.theme_use('clam')
except Exception:
    pass

style.configure('.', background=THEME['bg_app'], foreground=THEME['slate_dark'], font=('Segoe UI', 10))
style.configure('TFrame', background=THEME['bg_app'])
style.configure('Card.TFrame', background=THEME['bg_card'])
style.configure('TLabel', background=THEME['bg_app'], foreground=THEME['slate_dark'], font=('Segoe UI', 10))
style.configure('Card.TLabel', background=THEME['bg_card'], foreground=THEME['slate_dark'], font=('Segoe UI', 10))
style.configure('Muted.Card.TLabel', background=THEME['bg_card'], foreground=THEME['slate_light'], font=('Segoe UI', 9))
style.configure('SectionTitle.Card.TLabel', background=THEME['bg_card'], foreground=THEME['slate_dark'], font=('Segoe UI', 11, 'bold'))

# Notebook (Abas Modernas)
style.configure(
    'TNotebook',
    background=THEME['bg_app'],
    borderwidth=0,
    tabmargins=[0, 6, 0, 0],
)
style.configure(
    'TNotebook.Tab',
    background='#DCE3EC',
    foreground=THEME['slate_med'],
    padding=[18, 10],
    font=('Segoe UI', 10, 'bold'),
    borderwidth=0,
)
style.map(
    'TNotebook.Tab',
    background=[('selected', THEME['bg_card']), ('active', '#E8EEF5')],
    foreground=[('selected', THEME['brand_green_dark']), ('active', THEME['slate_dark'])],
    expand=[('selected', [0, 2, 0, 0])],
)

# LabelFrames como Cartões Limpos
style.configure(
    'TLabelframe',
    background=THEME['bg_card'],
    foreground=THEME['slate_dark'],
    bordercolor=THEME['border'],
    lightcolor=THEME['border'],
    darkcolor=THEME['border'],
    borderwidth=1,
    relief='solid',
)
style.configure(
    'TLabelframe.Label',
    background=THEME['bg_card'],
    foreground=THEME['brand_green_dark'],
    font=('Segoe UI', 10, 'bold'),
    padding=[6, 2],
)

# Botões Modernos
style.configure(
    'TButton',
    background='#E2E8F0',
    foreground=THEME['slate_dark'],
    font=('Segoe UI', 9, 'bold'),
    padding=[12, 7],
    borderwidth=0,
    focusthickness=0,
)
style.map(
    'TButton',
    background=[('active', '#CBD5E1'), ('pressed', '#94A3B8')],
    foreground=[('active', '#0F172A')],
)

style.configure(
    'Primary.TButton',
    background=THEME['brand_green'],
    foreground='#FFFFFF',
    font=('Segoe UI', 10, 'bold'),
    padding=[14, 7],
    borderwidth=0,
)
style.map(
    'Primary.TButton',
    background=[('active', THEME['brand_green_dark']), ('pressed', THEME['brand_teal'])],
    foreground=[('active', '#FFFFFF')],
)

style.configure(
    'Dark.TButton',
    background=THEME['slate_dark'],
    foreground='#FFFFFF',
    font=('Segoe UI', 9, 'bold'),
    padding=[12, 7],
    borderwidth=0,
)
style.map(
    'Dark.TButton',
    background=[('active', '#334155'), ('pressed', '#0F172A')],
    foreground=[('active', '#FFFFFF')],
)

style.configure(
    'Danger.TButton',
    background=THEME['danger'],
    foreground='#FFFFFF',
    font=('Segoe UI', 9, 'bold'),
    padding=[12, 7],
    borderwidth=0,
)
style.map(
    'Danger.TButton',
    background=[('active', THEME['danger_dark'])],
    foreground=[('active', '#FFFFFF')],
)

style.configure(
    'Warning.TButton',
    background=THEME['warning'],
    foreground='#FFFFFF',
    font=('Segoe UI', 9, 'bold'),
    padding=[12, 7],
    borderwidth=0,
)
style.map(
    'Warning.TButton',
    background=[('active', '#D97706')],
    foreground=[('active', '#FFFFFF')],
)

# Checkbuttons em fundo branco
style.configure(
    'TCheckbutton',
    background=THEME['bg_card'],
    foreground=THEME['slate_dark'],
    font=('Segoe UI', 10),
    focusthickness=0,
)
style.map(
    'TCheckbutton',
    background=[('active', THEME['bg_card'])],
    indicatorcolor=[('selected', THEME['brand_green']), ('!selected', '#FFFFFF')],
)

# Entradas de texto (Entry)
style.configure(
    'TEntry',
    fieldbackground=THEME['input_bg'],
    foreground=THEME['slate_dark'],
    bordercolor=THEME['input_border'],
    lightcolor=THEME['input_border'],
    darkcolor=THEME['input_border'],
    padding=6,
)
style.map(
    'TEntry',
    bordercolor=[('focus', THEME['brand_green'])],
    lightcolor=[('focus', THEME['brand_green'])],
    fieldbackground=[('focus', '#FFFFFF')],
)

# Tabelas (Treeview) Executivas
style.configure(
    'Treeview',
    background='#FFFFFF',
    fieldbackground='#FFFFFF',
    foreground=THEME['slate_dark'],
    rowheight=30,
    font=('Segoe UI', 9),
    borderwidth=1,
    relief='solid',
)
style.configure(
    'Treeview.Heading',
    background=THEME['slate_dark'],
    foreground='#FFFFFF',
    font=('Segoe UI', 9, 'bold'),
    padding=[8, 7],
    borderwidth=0,
)
style.map(
    'Treeview.Heading',
    background=[('active', '#334155')],
    foreground=[('active', '#FFFFFF')],
)
style.map(
    'Treeview',
    background=[('selected', '#D1FAE5')],
    foreground=[('selected', '#065F46')],
)


def style_text_widget(widget):
    """Aplica borda suave e visual moderno a campos tk.Text."""
    widget.configure(
        bg=THEME['input_bg'],
        fg=THEME['slate_dark'],
        insertbackground=THEME['brand_green_dark'],
        selectbackground='#A7F3D0',
        selectforeground='#064E3B',
        relief='flat',
        padx=8,
        pady=6,
        highlightthickness=1,
        highlightbackground=THEME['input_border'],
        highlightcolor=THEME['brand_green'],
    )


# ==================== TOPO EXECUTIVO (HEADER + KPIs) ====================
header_banner = tk.Frame(root, bg=THEME['bg_header'], padx=20, pady=8)
header_banner.pack(fill='x')

# Faixa decorativa verde no topo
accent_bar = tk.Frame(root, bg=THEME['brand_green'], height=3)
accent_bar.pack(fill='x')

title_row = tk.Frame(header_banner, bg=THEME['bg_header'])
title_row.pack(fill='x')

brand_left = tk.Frame(title_row, bg=THEME['bg_header'])
brand_left.pack(side='left')

logo_badge = tk.Label(
    brand_left,
    text=' 🤖 ',
    font=('Segoe UI Emoji', 15),
    bg=THEME['brand_green'],
    fg='white',
    padx=4,
    pady=1,
)
logo_badge.pack(side='left', padx=(0, 10))

title_texts = tk.Frame(brand_left, bg=THEME['bg_header'])
title_texts.pack(side='left')

tk.Label(
    title_texts,
    text='WhatsAuto Empresarial',
    font=('Segoe UI', 14, 'bold'),
    fg='#FFFFFF',
    bg=THEME['bg_header'],
).pack(anchor='w')

tk.Label(
    title_texts,
    text='Automação Receptiva Inteligente • Transbordo Humano • Anti-Bloqueio',
    font=('Segoe UI', 9),
    fg='#94A3B8',
    bg=THEME['bg_header'],
).pack(anchor='w')

toggle_mode_btn = ttk.Button(title_row, text='⚡ Alternar Modo Real / Simulação', style='Primary.TButton')
toggle_mode_btn.pack(side='right', padx=4)

# Sub-barra de Status e Indicadores Rápidos
status_bar = tk.Frame(root, bg=THEME['bg_subheader'], padx=20, pady=6)
status_bar.pack(fill='x')

status_label = tk.Label(
    status_bar,
    text='● Verificando servidor...',
    font=('Segoe UI', 9, 'bold'),
    fg='#34D399',
    bg=THEME['bg_subheader'],
)
status_label.pack(side='left')

wa_status_label = tk.Label(
    status_bar,
    text='  |   📱 WhatsApp: verificando...',
    font=('Segoe UI', 9, 'bold'),
    fg='#E2E8F0',
    bg=THEME['bg_subheader'],
)
wa_status_label.pack(side='left', padx=8)

kpi_summary_label = tk.Label(
    status_bar,
    text='Regras Ativas: -   •   Em Atendimento: 0   •   Expediente: 08:30–17:38',
    font=('Segoe UI', 9),
    fg='#94A3B8',
    bg=THEME['bg_subheader'],
)
kpi_summary_label.pack(side='right')

# ==================== ÁREA DE ABAS (NOTEBOOK) ====================
notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=14, pady=(6, 10))

# ==================== ABA 1: REGRAS E SIMULADOR ====================
tab_rules = ttk.Frame(notebook, padding=10)
notebook.add(tab_rules, text='  💬 1. Regras & Simulador  ')

# Linha superior dividida lado a lado (Formulário à esquerda | Simulador à direita) para deixar a tabela gigante!
top_split = ttk.Frame(tab_rules)
top_split.pack(fill='x', pady=(0, 6))
top_split.columnconfigure(0, weight=6)
top_split.columnconfigure(1, weight=4)

form_frame = ttk.LabelFrame(
    top_split,
    text=' ✏️ Criar ou Editar Regra (Separe sinônimos por vírgula) ',
    padding=8,
)
form_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 6))

editing_rule_id = {'id': None}
rules_cache = {}

ttk.Label(
    form_frame,
    text='Palavras-chave / Sinônimos (ex.: 1, preço, valor, quanto custa, orçamento):',
    style='Card.TLabel',
).pack(anchor='w')
keyword_entry = ttk.Entry(form_frame, font=('Segoe UI', 10))
keyword_entry.pack(fill='x', pady=(2, 6))

ttk.Label(
    form_frame,
    text='Resposta automática do robô (pode usar várias linhas com Enter e *negrito*):',
    style='Card.TLabel',
).pack(anchor='w')
reply_text_widget = tk.Text(form_frame, height=2, font=('Segoe UI', 10), wrap='word')
style_text_widget(reply_text_widget)
reply_text_widget.pack(fill='x', pady=(2, 2))

sim_frame = ttk.LabelFrame(
    top_split,
    text=' ⚡ Simulador Instantâneo (Teste 1/2/3/4 ou saudações) ',
    padding=8,
)
sim_frame.grid(row=0, column=1, sticky='nsew', padx=(6, 0))

ttk.Label(
    sim_frame,
    text='Mensagem de teste do cliente:',
    style='Card.TLabel',
).pack(anchor='w')

sim_input_row = ttk.Frame(sim_frame, style='Card.TFrame')
sim_input_row.pack(fill='x', pady=(2, 6))
message_entry = ttk.Entry(sim_input_row, font=('Segoe UI', 10))
message_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
message_entry.insert(0, 'Oi, bom dia!')

output_var = tk.StringVar(value='💡 Clique em "Testar" para ver a resposta do robô.')


def simulate():
    try:
        result = api('POST', '/api/simulate', json={'message': message_entry.get()})
        reply_text = result.get('reply')
        dtype = result.get('decision_type', '')
        type_labels = {
            'rule': '✅ Regra de Palavra-Chave',
            'welcome': '👋 Menu de Boas-Vindas (1º Contato)',
            'human_handoff': '🎧 Transferência p/ Atendente Humano (Pausa o robô)',
            'outside_hours': '🌙 Aviso de Fora do Horário Comercial',
        }
        if reply_text:
            t_label = type_labels.get(dtype, dtype)
            preview = reply_text.replace('\n', '  ↵  ')
            output_var.set(f'{t_label}  ➔  {preview}')
        else:
            output_var.set('🔇 Nenhuma regra correspondente ➔ Silêncio.')
    except Exception as exc:
        messagebox.showerror('Erro', str(exc))


ttk.Button(sim_input_row, text='🚀 Testar', command=simulate, style='Primary.TButton').pack(side='right')
sim_result_banner = tk.Label(
    sim_frame,
    textvariable=output_var,
    wraplength=420,
    justify='left',
    anchor='w',
    bg='#F0FDF4',
    fg='#065F46',
    font=('Segoe UI', 9, 'bold'),
    padx=8,
    pady=6,
)
sim_result_banner.pack(fill='both', expand=True, pady=(2, 0))

btn_bar = ttk.Frame(tab_rules)
btn_bar.pack(fill='x', pady=(2, 6))

save_rule_btn = ttk.Button(btn_bar, text='➕ Adicionar Nova Regra', style='Primary.TButton')
save_rule_btn.pack(side='left', padx=(0, 6))

cancel_edit_btn = ttk.Button(btn_bar, text='✖ Cancelar Edição')

rules_tree_frame = ttk.Frame(tab_rules)
rules_tree_frame.pack(fill='both', expand=True)

rules_tree = ttk.Treeview(
    rules_tree_frame,
    columns=('id', 'keyword', 'reply', 'enabled'),
    show='headings',
    height=15,
)
rules_scroll = ttk.Scrollbar(rules_tree_frame, orient='vertical', command=rules_tree.yview)
rules_tree.configure(yscrollcommand=rules_scroll.set)

for field, title, width in [
    ('id', 'ID', 50),
    ('keyword', 'Palavras-chave / Sinônimos', 260),
    ('reply', 'Resposta Automática (Dê duplo clique na linha para editar)', 560),
    ('enabled', 'Status', 90),
]:
    rules_tree.heading(field, text=title)
    rules_tree.column(field, width=width, stretch=(field == 'reply'), anchor=('center' if field in ('id', 'enabled') else 'w'))

rules_tree.tag_configure('even', background='#FFFFFF')
rules_tree.tag_configure('odd', background='#F8FAFC')
rules_tree.tag_configure('disabled', background='#FEF2F2', foreground='#991B1B')


def clear_rule_form():
    editing_rule_id['id'] = None
    keyword_entry.delete(0, 'end')
    reply_text_widget.delete('1.0', 'end')
    save_rule_btn.config(text='➕ Adicionar Nova Regra')
    cancel_edit_btn.pack_forget()


def save_or_add_rule():
    kw = keyword_entry.get().strip()
    rep = reply_text_widget.get('1.0', 'end').strip()
    if not kw or not rep:
        messagebox.showwarning('Atenção', 'Preencha as palavras-chave e o texto da resposta.')
        return
    try:
        if editing_rule_id['id'] is not None:
            rid = editing_rule_id['id']
            api('PUT', f'/api/rules/{rid}', json={'keyword': kw, 'reply': rep})
        else:
            api('POST', '/api/rules', json={'keyword': kw, 'reply': rep})
        clear_rule_form()
        refresh_all()
    except Exception as exc:
        messagebox.showerror('Erro ao salvar regra', str(exc))


def load_selected_rule_for_edit(*_):
    selected = rules_tree.selection()
    if not selected:
        messagebox.showinfo('Editar Regra', 'Selecione uma regra na tabela primeiro (ou dê duplo clique nela).')
        return
    rid = int(rules_tree.item(selected[0], 'values')[0])
    rule_data = rules_cache.get(rid)
    if not rule_data:
        return
    editing_rule_id['id'] = rid
    keyword_entry.delete(0, 'end')
    keyword_entry.insert(0, rule_data['keyword'])
    reply_text_widget.delete('1.0', 'end')
    reply_text_widget.insert('1.0', rule_data['reply'])
    save_rule_btn.config(text=f'💾 Salvar Alterações (Regra #{rid})')
    cancel_edit_btn.pack(side='left', padx=6, after=save_rule_btn)


def toggle_rule():
    selected = rules_tree.selection()
    if not selected:
        messagebox.showinfo('Atenção', 'Selecione uma regra na lista primeiro.')
        return
    rid = rules_tree.item(selected[0], 'values')[0]
    try:
        api('POST', f'/api/rules/{rid}/toggle')
        refresh_all()
    except Exception as exc:
        messagebox.showerror('Erro', str(exc))


def delete_rule():
    selected = rules_tree.selection()
    if not selected:
        messagebox.showinfo('Atenção', 'Selecione uma regra na lista para excluir.')
        return
    rid, kw = rules_tree.item(selected[0], 'values')[:2]
    if not messagebox.askyesno('Confirmar exclusão', f'Deseja realmente excluir a regra "{kw}"?'):
        return
    try:
        api('DELETE', f'/api/rules/{rid}')
        if editing_rule_id['id'] == int(rid):
            clear_rule_form()
        refresh_all()
    except Exception as exc:
        messagebox.showerror('Erro', str(exc))


save_rule_btn.config(command=save_or_add_rule)
cancel_edit_btn.config(command=clear_rule_form)
ttk.Button(btn_bar, text='✏️ Editar Selecionada', command=load_selected_rule_for_edit).pack(side='left', padx=5)
ttk.Button(btn_bar, text='🔄 Ativar / Desativar', command=toggle_rule).pack(side='left', padx=5)
ttk.Button(btn_bar, text='🗑️ Excluir Selecionada', command=delete_rule, style='Danger.TButton').pack(side='left', padx=5)
ttk.Button(btn_bar, text='🔄 Atualizar Dados', command=lambda: refresh_all(), style='Dark.TButton').pack(side='right')

rules_tree.bind('<Double-1>', load_selected_rule_for_edit)
rules_tree.pack(side='left', fill='both', expand=True)
rules_scroll.pack(side='right', fill='y')

# ==================== ABA 2: CONECTAR WHATSAPP (QR CODE) ====================
tab_qr = ttk.Frame(notebook, padding=20)
notebook.add(tab_qr, text='  📱 2. Conexão WhatsApp (QR Code)  ')

qr_card = tk.Frame(
    tab_qr,
    bg=THEME['bg_card'],
    padx=28,
    pady=22,
    highlightthickness=1,
    highlightbackground=THEME['border'],
)
qr_card.pack(fill='both', expand=True, padx=40, pady=6)

tk.Label(
    qr_card,
    text='Conecte o WhatsApp da sua Empresa em Segundos',
    font=('Segoe UI', 14, 'bold'),
    bg=THEME['bg_card'],
    fg=THEME['slate_dark'],
).pack(anchor='center', pady=(0, 6))

qr_info_label = tk.Label(
    qr_card,
    text=(
        '1️⃣  Abra o WhatsApp no celular da empresa     •     '
        '2️⃣  Vá em Aparelhos Conectados > Conectar Aparelho     •     '
        '3️⃣  Aponte a câmera para o quadro abaixo'
    ),
    font=('Segoe UI', 10),
    bg='#F8FAFC',
    fg=THEME['slate_med'],
    padx=16,
    pady=8,
)
qr_info_label.pack(fill='x', pady=(0, 14))

qr_state_banner = tk.Label(
    qr_card,
    text='Verificando status do WhatsApp...',
    font=('Segoe UI', 12, 'bold'),
    bg=THEME['bg_card'],
    fg=THEME['brand_green_dark'],
)
qr_state_banner.pack(anchor='center', pady=6)

qr_canvas_holder = tk.Frame(
    qr_card,
    bg='#FFFFFF',
    padx=14,
    pady=14,
    highlightthickness=2,
    highlightbackground=THEME['brand_green'],
)
qr_canvas_holder.pack(anchor='center', pady=10)

qr_canvas = tk.Canvas(
    qr_canvas_holder,
    width=260,
    height=260,
    bg='white',
    highlightthickness=0,
)
qr_canvas.pack(anchor='center')
qr_photo_ref = {'raw': None}


def reset_qr_session():
    if not messagebox.askyesno(
        'Gerar Novo QR Code',
        'Isso desconectará a sessão atual (se houver) e gerará um novo QR Code. Continuar?',
    ):
        return
    try:
        api('POST', '/api/qr/reset')
        qr_photo_ref['raw'] = None
        refresh_qr_status()
    except Exception as exc:
        messagebox.showerror('Erro ao reiniciar QR Code', str(exc))


qr_btn_row = tk.Frame(qr_card, bg=THEME['bg_card'])
qr_btn_row.pack(anchor='center', pady=(12, 0))
ttk.Button(qr_btn_row, text='🔄 Atualizar Status / QR Code', command=lambda: refresh_qr_status(), style='Primary.TButton').pack(
    side='left', padx=8
)
ttk.Button(qr_btn_row, text='🔌 Desconectar / Gerar Novo QR Code', command=reset_qr_session, style='Danger.TButton').pack(
    side='left', padx=8
)

# ==================== ABA 3: ATENDIMENTO HUMANO E HISTÓRICO ====================
tab_events = ttk.Frame(notebook, padding=12)
notebook.add(tab_events, text='  🎧 3. Fila Humana & Histórico  ')

paused_frame = ttk.LabelFrame(
    tab_events,
    text=' 👨‍💼 Clientes em Atendimento Humano Ativo (Encerra sozinho após 15 min sem conversa de ambos os lados) ',
    padding=10,
)
paused_frame.pack(fill='x', pady=(0, 10))

paused_top_row = ttk.Frame(paused_frame, style='Card.TFrame')
paused_top_row.pack(fill='x', pady=(0, 8))
ttk.Label(paused_top_row, text='Pausar cliente manualmente (DDI+DDD+Número):', style='Card.TLabel').pack(side='left')
manual_pause_entry = ttk.Entry(paused_top_row, width=22)
manual_pause_entry.pack(side='left', padx=8)


def pause_number_manual():
    num = manual_pause_entry.get().strip()
    if not num:
        return
    try:
        api('POST', '/api/paused', json={'sender': num})
        manual_pause_entry.delete(0, 'end')
        refresh_paused()
    except Exception as exc:
        messagebox.showerror('Erro', str(exc))


def unpause_selected():
    selected = paused_tree.selection()
    if not selected:
        messagebox.showinfo('Atenção', 'Selecione um cliente na lista de pausados para liberar o robô.')
        return
    sender = paused_tree.item(selected[0], 'values')[0]
    try:
        api('DELETE', f'/api/paused/{sender}')
        refresh_paused()
        refresh_events()
    except Exception as exc:
        messagebox.showerror('Erro', str(exc))


ttk.Button(paused_top_row, text='⏸️ Pausar Robô p/ este Número', command=pause_number_manual, style='Dark.TButton').pack(
    side='left', padx=4
)
ttk.Button(
    paused_top_row,
    text='✅ Encerrar Atendimento Selecionado (Voltar p/ Robô)',
    command=unpause_selected,
    style='Primary.TButton',
).pack(side='right', padx=4)

paused_tree = ttk.Treeview(
    paused_frame,
    columns=('sender', 'paused_until', 'reason'),
    show='headings',
    height=4,
)
for field, title, width in [
    ('sender', 'Cliente (Número / ID)', 190),
    ('paused_until', 'Expira se Inativo Até (UTC)', 190),
    ('reason', 'Motivo / Nome do Cliente', 500),
]:
    paused_tree.heading(field, text=title)
    paused_tree.column(field, width=width, stretch=(field == 'reason'))
paused_tree.pack(fill='x')

events_top = ttk.Frame(tab_events)
events_top.pack(fill='x', pady=(4, 6))
ttk.Label(
    events_top,
    text='📋 Histórico em Tempo Real (Últimas 80 interações):',
    font=('Segoe UI', 10, 'bold'),
).pack(side='left')
ttk.Button(events_top, text='🔄 Atualizar Histórico', command=lambda: (refresh_paused(), refresh_events()), style='Dark.TButton').pack(
    side='right'
)
ttk.Button(
    events_top,
    text='🔔 Testar Alerta de Atendente na Tela',
    style='Warning.TButton',
    command=lambda: show_attendant_alert({
        'sender': '5511999999999',
        'push_name': 'Cliente Exemplo (Teste)',
        'incoming': '4 - Quero falar com um atendente',
        'received_at': 'Agora mesmo',
    }),
).pack(side='right', padx=8)

events_tree_frame = ttk.Frame(tab_events)
events_tree_frame.pack(fill='both', expand=True)

events_tree = ttk.Treeview(
    events_tree_frame,
    columns=('received_at', 'sender', 'incoming', 'reply', 'status'),
    show='headings',
    height=11,
)
events_scroll = ttk.Scrollbar(events_tree_frame, orient='vertical', command=events_tree.yview)
events_tree.configure(yscrollcommand=events_scroll.set)

for field, title, width in [
    ('received_at', 'Data / Hora (UTC)', 140),
    ('sender', 'Cliente (Nome / Número)', 185),
    ('incoming', 'Mensagem Recebida', 220),
    ('reply', 'Resposta Automática Enviada', 310),
    ('status', 'Status do Atendimento', 165),
]:
    events_tree.heading(field, text=title)
    events_tree.column(field, width=width, stretch=(field in ('incoming', 'reply')))

events_tree.tag_configure('sent', background='#FFFFFF')
events_tree.tag_configure('odd', background='#F8FAFC')
events_tree.tag_configure('handoff', background='#FEF2F2', foreground='#991B1B')
events_tree.tag_configure('paused', background='#FFFBEB', foreground='#92400E')
events_tree.tag_configure('closed', background='#ECFDF5', foreground='#065F46')

events_tree.pack(side='left', fill='both', expand=True)
events_scroll.pack(side='right', fill='y')

# ==================== ABA 4: MENU INICIAL, HORÁRIO E CONFIGURAÇÕES ====================
tab_cfg = ttk.Frame(notebook, padding=12)
notebook.add(tab_cfg, text='  ⚙️ 4. Menu Inicial, Horário & Ajustes  ')

cfg_top = ttk.LabelFrame(tab_cfg, text=' 🤖 Identificação do Robô, Transbordo Humano e Inatividade (15 min) ', padding=10)
cfg_top.pack(fill='x', pady=(0, 8))

row_prefix = ttk.Frame(cfg_top, style='Card.TFrame')
row_prefix.pack(fill='x', pady=2)
ttk.Label(row_prefix, text='Assinatura no topo das mensagens do robô:', width=40, style='Card.TLabel').pack(side='left')
bot_prefix_entry = ttk.Entry(row_prefix)
bot_prefix_entry.pack(side='left', fill='x', expand=True, padx=4)

row_pause = ttk.Frame(cfg_top, style='Card.TFrame')
row_pause.pack(fill='x', pady=2)
ttk.Label(row_pause, text='Reiniciar conversa / encerrar atendente após inatividade de:', width=48, style='Card.TLabel').pack(side='left')
human_pause_entry = ttk.Entry(row_pause, width=8)
human_pause_entry.pack(side='left', padx=4)
ttk.Label(row_pause, text='min   |   Intervalo p/ não repetir mesma regra:', style='Card.TLabel').pack(side='left', padx=6)
cooldown_entry = ttk.Entry(row_pause, width=8)
cooldown_entry.pack(side='left', padx=4)
ttk.Label(row_pause, text='min', style='Card.TLabel').pack(side='left')

row_handoff = ttk.Frame(cfg_top, style='Card.TFrame')
row_handoff.pack(fill='x', pady=2)
ttk.Label(row_handoff, text='Palavras que transferem p/ humano (ex. 4, atendente):', width=48, style='Card.TLabel').pack(side='left')
handoff_kw_entry = ttk.Entry(row_handoff)
handoff_kw_entry.pack(side='left', fill='x', expand=True, padx=4)

row_handoff_msg = ttk.Frame(cfg_top, style='Card.TFrame')
row_handoff_msg.pack(fill='x', pady=2)
ttk.Label(row_handoff_msg, text='Resposta ao transferir p/ atendente humano:', width=40, style='Card.TLabel').pack(side='left')
handoff_reply_entry = ttk.Entry(row_handoff_msg)
handoff_reply_entry.pack(side='left', fill='x', expand=True, padx=4)

row_close_msg = ttk.Frame(cfg_top, style='Card.TFrame')
row_close_msg.pack(fill='x', pady=2)
ttk.Label(row_close_msg, text='Mensagem ao encerrar o atendimento:', width=40, style='Card.TLabel').pack(side='left')
human_close_reply_entry = ttk.Entry(row_close_msg)
human_close_reply_entry.pack(side='left', fill='x', expand=True, padx=4)

cfg_welcome = ttk.LabelFrame(
    tab_cfg,
    text=' 👋 Saudação Inicial / Menu de Boas-Vindas (Enviado no 1º contato, após 1h ou após encerramento) ',
    padding=10,
)
cfg_welcome.pack(fill='x', pady=(0, 8))

welcome_enabled_var = tk.IntVar(master=root, value=1)
w_row1 = ttk.Frame(cfg_welcome, style='Card.TFrame')
w_row1.pack(fill='x')
welcome_chk = ttk.Checkbutton(
    w_row1,
    text='Enviar Menu de Boas-Vindas automaticamente quando a mensagem não bater em nenhuma regra',
    variable=welcome_enabled_var,
    onvalue=1,
    offvalue=0,
)
welcome_chk.pack(side='left')
ttk.Label(w_row1, text='   |   Repetir Menu após:', style='Card.TLabel').pack(side='left')
welcome_hours_entry = ttk.Entry(w_row1, width=6)
welcome_hours_entry.pack(side='left', padx=4)
ttk.Label(w_row1, text='hora(s) por cliente', style='Card.TLabel').pack(side='left')

welcome_text_widget = tk.Text(cfg_welcome, height=5, font=('Segoe UI', 9), wrap='word')
style_text_widget(welcome_text_widget)
welcome_text_widget.pack(fill='x', pady=(6, 2))

cfg_bh = ttk.LabelFrame(
    tab_cfg,
    text=' 🕒 Horário Comercial (Mensagem Automática de Fora de Expediente) ',
    padding=10,
)
cfg_bh.pack(fill='x', pady=(0, 8))

bh_enabled_var = tk.IntVar(master=root, value=1)
bh_weekends_var = tk.IntVar(master=root, value=0)

bh_row1 = ttk.Frame(cfg_bh, style='Card.TFrame')
bh_row1.pack(fill='x')
bh_enabled_chk = ttk.Checkbutton(
    bh_row1,
    text='Ativar aviso de Fora do Horário Comercial',
    variable=bh_enabled_var,
    onvalue=1,
    offvalue=0,
)
bh_enabled_chk.pack(side='left')
ttk.Label(bh_row1, text='   |   Início (HH:MM):', style='Card.TLabel').pack(side='left')
bh_start_entry = ttk.Entry(bh_row1, width=8)
bh_start_entry.pack(side='left', padx=4)
ttk.Label(bh_row1, text='Fim (HH:MM):', style='Card.TLabel').pack(side='left')
bh_end_entry = ttk.Entry(bh_row1, width=8)
bh_end_entry.pack(side='left', padx=4)
bh_weekends_chk = ttk.Checkbutton(
    bh_row1,
    text='Atender também Sábado/Domingo',
    variable=bh_weekends_var,
    onvalue=1,
    offvalue=0,
)
bh_weekends_chk.pack(side='left', padx=12)

ttk.Label(cfg_bh, text='Mensagem enviada fora do horário de expediente:', style='Card.TLabel').pack(anchor='w', pady=(6, 2))
bh_text_widget = tk.Text(cfg_bh, height=2, font=('Segoe UI', 9), wrap='word')
style_text_widget(bh_text_widget)
bh_text_widget.pack(fill='x')


def get_startup_cmd_path():
    appdata = os.getenv('APPDATA', '')
    if not appdata:
        return None
    return Path(appdata) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup' / 'WhatsAuto_Empresarial.cmd'


def is_windows_startup_enabled():
    p = get_startup_cmd_path()
    return bool(p and p.exists())


def toggle_windows_startup():
    p = get_startup_cmd_path()
    if not p:
        messagebox.showerror('Erro', 'Não foi possível localizar a pasta Inicializar do Windows.')
        return
    try:
        if p.exists():
            p.unlink()
            messagebox.showinfo('Inicialização com o Windows', 'O WhatsAuto NÃO iniciará mais automaticamente com o Windows.')
        else:
            bat_path = PROJECT_DIR / 'iniciar_whatsauto.bat'
            exe_path = BASE_DIR / 'WhatsAuto.exe' if (BASE_DIR / 'WhatsAuto.exe').exists() else Path(sys.executable)
            target = bat_path if bat_path.exists() else exe_path
            p.write_text(
                f'@echo off\ncd /d "{target.parent}"\nstart "" "{target}"\n',
                encoding='utf-8',
            )
            messagebox.showinfo(
                'Inicialização com o Windows',
                'Pronto! Agora o WhatsAuto iniciará automaticamente sempre que você ligar o Windows.',
            )
        update_startup_btn_label()
    except Exception as exc:
        messagebox.showerror('Erro', str(exc))


def _collect_settings_payload():
    return {
        'bot_prefix': bot_prefix_entry.get().strip(),
        'human_pause_minutes': human_pause_entry.get().strip() or '15',
        'cooldown_minutes': cooldown_entry.get().strip() or '1',
        'human_handoff_keywords': handoff_kw_entry.get().strip(),
        'human_handoff_reply': handoff_reply_entry.get().strip(),
        'human_close_reply': human_close_reply_entry.get().strip(),
        'welcome_enabled': '1' if int(welcome_enabled_var.get()) == 1 else '0',
        'welcome_cooldown_hours': welcome_hours_entry.get().strip() or '1',
        'welcome_message': welcome_text_widget.get('1.0', 'end').strip(),
        'bh_enabled': '1' if int(bh_enabled_var.get()) == 1 else '0',
        'bh_start': bh_start_entry.get().strip() or '08:30',
        'bh_end': bh_end_entry.get().strip() or '17:38',
        'bh_weekends': '1' if int(bh_weekends_var.get()) == 1 else '0',
        'bh_message': bh_text_widget.get('1.0', 'end').strip(),
    }


def save_all_settings_silent():
    """Salva imediatamente quando o usuário clica nos checkboxes, sem abrir janela."""
    try:
        api('POST', '/api/settings', json={
            'welcome_enabled': '1' if int(welcome_enabled_var.get()) == 1 else '0',
            'bh_enabled': '1' if int(bh_enabled_var.get()) == 1 else '0',
            'bh_weekends': '1' if int(bh_weekends_var.get()) == 1 else '0',
            'bh_start': bh_start_entry.get().strip() or '08:30',
            'bh_end': bh_end_entry.get().strip() or '17:38',
        })
        refresh_status_only()
    except Exception:
        pass


welcome_chk.config(command=save_all_settings_silent)
bh_enabled_chk.config(command=save_all_settings_silent)
bh_weekends_chk.config(command=save_all_settings_silent)


def save_all_settings():
    payload = _collect_settings_payload()
    try:
        api('POST', '/api/settings', json=payload)
        messagebox.showinfo('Configurações Salvas', 'Todas as configurações foram salvas e já estão ativas!')
        refresh_all()
    except Exception as exc:
        messagebox.showerror('Erro ao salvar configurações', str(exc))


cfg_footer = ttk.Frame(tab_cfg)
cfg_footer.pack(fill='x', pady=(6, 0))
ttk.Button(
    cfg_footer,
    text='💾 Salvar Todas as Configurações',
    command=save_all_settings,
    style='Primary.TButton',
).pack(side='left')
startup_btn = ttk.Button(cfg_footer, text='Iniciar com o Windows', command=toggle_windows_startup, style='Dark.TButton')
startup_btn.pack(side='right')


def update_startup_btn_label():
    if is_windows_startup_enabled():
        startup_btn.config(text='✅ Inicia com o Windows (Clique p/ desativar)')
    else:
        startup_btn.config(text='🚀 Ativar Inicialização junto com o Windows')


update_startup_btn_label()
_settings_loaded = {'done': False}


def load_settings_into_ui():
    try:
        cfg = api('GET', '/api/settings')
        bot_prefix_entry.delete(0, 'end')
        bot_prefix_entry.insert(0, cfg.get('bot_prefix', ''))

        human_pause_entry.delete(0, 'end')
        human_pause_entry.insert(0, cfg.get('human_pause_minutes', '15'))

        cooldown_entry.delete(0, 'end')
        cooldown_entry.insert(0, cfg.get('cooldown_minutes', '1'))

        handoff_kw_entry.delete(0, 'end')
        handoff_kw_entry.insert(0, cfg.get('human_handoff_keywords', ''))

        handoff_reply_entry.delete(0, 'end')
        handoff_reply_entry.insert(0, cfg.get('human_handoff_reply', ''))

        human_close_reply_entry.delete(0, 'end')
        human_close_reply_entry.insert(0, cfg.get('human_close_reply', ''))

        welcome_enabled_var.set(1 if str(cfg.get('welcome_enabled', '1')) == '1' else 0)
        welcome_hours_entry.delete(0, 'end')
        welcome_hours_entry.insert(0, cfg.get('welcome_cooldown_hours', '1'))

        welcome_text_widget.delete('1.0', 'end')
        welcome_text_widget.insert('1.0', cfg.get('welcome_message', ''))

        bh_enabled_var.set(1 if str(cfg.get('bh_enabled', '1')) == '1' else 0)
        bh_weekends_var.set(1 if str(cfg.get('bh_weekends', '0')) == '1' else 0)

        bh_start_entry.delete(0, 'end')
        bh_start_entry.insert(0, cfg.get('bh_start', '08:30'))

        bh_end_entry.delete(0, 'end')
        bh_end_entry.insert(0, cfg.get('bh_end', '17:38'))

        bh_text_widget.delete('1.0', 'end')
        bh_text_widget.insert('1.0', cfg.get('bh_message', ''))
        _settings_loaded['done'] = True
    except Exception:
        pass


def toggle_simulation_mode():
    try:
        api('POST', '/api/mode/toggle')
        refresh_all()
    except Exception as exc:
        messagebox.showerror('Erro ao alternar modo', str(exc))


toggle_mode_btn.config(command=toggle_simulation_mode)


def render_qr_code(raw_qr):
    if not raw_qr:
        qr_canvas.delete('all')
        qr_canvas.config(width=320, height=90, bg='#F8FAFC')
        qr_canvas.create_text(
            160,
            45,
            text='✔ Nenhum QR Code pendente no momento',
            fill=THEME['brand_green_dark'],
            font=('Segoe UI', 10, 'bold'),
        )
        qr_photo_ref['raw'] = None
        return
    if qr_photo_ref['raw'] == raw_qr:
        return
    qr_obj = qrcode.QRCode(box_size=6, border=2)
    qr_obj.add_data(raw_qr)
    qr_obj.make(fit=True)
    matrix = qr_obj.get_matrix()
    rows = len(matrix)
    box = 6
    size = rows * box
    qr_canvas.config(width=size, height=size, bg='white')
    qr_canvas.delete('all')
    for r, row in enumerate(matrix):
        y0 = r * box
        y1 = y0 + box
        for c, val in enumerate(row):
            if val:
                x0 = c * box
                qr_canvas.create_rectangle(x0, y0, x0 + box, y1, fill='#0B141A', outline='#0B141A')
    qr_photo_ref['raw'] = raw_qr


def refresh_qr_status():
    try:
        q = api('GET', '/api/qr/status')
        st = q.get('state', 'unknown')
        if st == 'connected':
            phone = q.get('phone') or ''
            name = q.get('name') or ''
            wa_status_label.config(
                text=f'  |   📱 WhatsApp CONECTADO: {phone} {f"({name})" if name else ""}',
                fg='#34D399',
            )
            qr_state_banner.config(
                text=f'✅ WhatsApp Conectado com Sucesso! Número: {phone} {f"({name})" if name else ""}',
                fg=THEME['brand_green_dark'],
            )
            render_qr_code(None)
        elif st == 'connecting':
            phone = q.get('phone') or ''
            wa_status_label.config(
                text=f'  |   🔄 WhatsApp: Sincronizando {phone}...',
                fg='#FBBF24',
            )
            qr_state_banner.config(
                text='🔄 QR Code lido! Finalizando sincronização com o celular, aguarde alguns segundos...',
                fg=THEME['brand_green_dark'],
            )
            render_qr_code(None)
        elif st == 'qr_ready' and q.get('qr'):
            wa_status_label.config(
                text='  |   📱 WhatsApp: Aguardando leitura do QR Code (Aba 2)',
                fg='#FBBF24',
            )
            qr_state_banner.config(
                text='📱 Aponte a câmera do WhatsApp da empresa para o QR Code abaixo:',
                fg='#D97706',
            )
            render_qr_code(q.get('qr'))
        elif st == 'bridge_offline':
            wa_status_label.config(
                text='  |   ⚠️ Ponte QR Code desligada (inicie pelo atalho iniciar_whatsauto.bat)',
                fg='#F87171',
            )
            qr_state_banner.config(
                text='⚠️ A ponte do QR Code não está rodando. Execute iniciar_whatsauto.bat.',
                fg=THEME['danger'],
            )
            render_qr_code(None)
        else:
            wa_status_label.config(
                text=f'  |   ⏳ WhatsApp: Iniciando conexão ({st})...',
                fg='#94A3B8',
            )
            qr_state_banner.config(
                text='⏳ Gerando QR Code, aguarde alguns segundos...',
                fg=THEME['slate_med'],
            )
            render_qr_code(None)
    except Exception:
        wa_status_label.config(text='  |   ⚠️ WhatsApp: sem comunicação', fg='#F87171')


def update_kpi_summary():
    try:
        active_rules = sum(1 for r in rules_cache.values() if r.get('enabled'))
        paused_cnt = len(paused_tree.get_children())
        b_start = bh_start_entry.get().strip() or '08:30'
        b_end = bh_end_entry.get().strip() or '17:38'
        kpi_summary_label.config(
            text=f'🟢 Regras Ativas: {active_rules}   •   👨‍💼 Em Atendimento: {paused_cnt}   •   🕒 Expediente: {b_start}–{b_end}'
        )
    except Exception:
        pass


def refresh_paused():
    try:
        for item_id in paused_tree.get_children():
            paused_tree.delete(item_id)
        for p in api('GET', '/api/paused'):
            until_str = (p.get('paused_until') or '')[:19].replace('T', ' ')
            paused_tree.insert(
                '',
                'end',
                values=(p.get('sender') or '', until_str, p.get('reason') or ''),
            )
        update_kpi_summary()
    except Exception:
        pass


_seen_handoff_ids = set()
_initial_events_loaded = {'done': False}


def play_attendant_sound():
    """Toca um alerta sonoro claro no computador do atendente."""
    if not winsound:
        return
    try:
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        for freq, dur in [(880, 180), (1175, 180), (1397, 280), (880, 180), (1397, 350)]:
            winsound.Beep(freq, dur)
    except Exception:
        pass


def show_attendant_alert(ev):
    """Abre um pop-up moderno sempre visível no topo da tela e toca som avisando o atendente."""
    threading.Thread(target=play_attendant_sound, daemon=True).start()

    raw_sender = (ev.get('sender') or '').replace('@s.whatsapp.net', '').replace('@lid', '')
    push_name = (ev.get('push_name') or '').strip()
    display_client = f'{push_name} ({raw_sender})' if push_name else raw_sender
    incoming_txt = ev.get('incoming') or 'Solicitou falar com atendente'
    raw_time = (ev.get('received_at') or '')[:19].replace('T', ' ')

    try:
        root.deiconify()
        root.lift()
    except Exception:
        pass

    alert_win = tk.Toplevel(root)
    alert_win.title('🔔 CHAMADO DE ATENDIMENTO HUMANO — WhatsAuto Empresarial')
    alert_win.geometry('540x330')
    alert_win.configure(bg='#FFFFFF')
    alert_win.attributes('-topmost', True)
    alert_win.lift()
    alert_win.focus_force()

    banner = tk.Frame(alert_win, bg='#DC2626', padx=18, pady=12)
    banner.pack(fill='x')
    tk.Label(
        banner,
        text='🔔 CLIENTE AGUARDANDO ATENDENTE HUMANO!',
        font=('Segoe UI', 13, 'bold'),
        fg='white',
        bg='#DC2626',
    ).pack(anchor='w')
    tk.Label(
        banner,
        text='O robô foi pausado automaticamente por 15 min para este contato.',
        font=('Segoe UI', 9),
        fg='#FEE2E2',
        bg='#DC2626',
    ).pack(anchor='w')

    body = tk.Frame(alert_win, bg='#FFFFFF', padx=20, pady=14)
    body.pack(fill='both', expand=True)

    tk.Label(
        body,
        text=f'👤 Cliente: {display_client}',
        font=('Segoe UI', 12, 'bold'),
        fg=THEME['slate_dark'],
        bg='#FFFFFF',
    ).pack(anchor='w', pady=(2, 8))

    msg_box = tk.Frame(body, bg='#F8FAFC', padx=12, pady=8, highlightthickness=1, highlightbackground='#E2E8F0')
    msg_box.pack(fill='x', pady=(0, 8))
    tk.Label(
        msg_box,
        text=f'💬 "{incoming_txt}"',
        font=('Segoe UI', 10, 'italic'),
        fg=THEME['slate_dark'],
        bg='#F8FAFC',
        wraplength=470,
        justify='left',
    ).pack(anchor='w')

    tk.Label(
        body,
        text=f'🕒 Horário do chamado: {raw_time}',
        font=('Segoe UI', 9),
        fg=THEME['slate_light'],
        bg='#FFFFFF',
    ).pack(anchor='w')

    btn_row = tk.Frame(alert_win, bg='#F8FAFC', padx=20, pady=12)
    btn_row.pack(fill='x', side='bottom')

    def assume_attendance():
        try:
            notebook.select(tab_events)
            root.deiconify()
            root.lift()
        except Exception:
            pass
        alert_win.destroy()

    def release_bot_now():
        try:
            if raw_sender and raw_sender != '5511999999999':
                api('DELETE', f'/api/paused/{raw_sender}')
                refresh_paused()
                refresh_events()
        except Exception:
            pass
        alert_win.destroy()

    tk.Button(
        btn_row,
        text='✅ Estou Ciente / Assumir Atendimento',
        command=assume_attendance,
        bg=THEME['brand_green'],
        activebackground=THEME['brand_green_dark'],
        fg='white',
        activeforeground='white',
        font=('Segoe UI', 10, 'bold'),
        padx=14,
        pady=7,
        relief='flat',
        cursor='hand2',
    ).pack(side='left')

    tk.Button(
        btn_row,
        text='🔓 Encerrar & Liberar Robô',
        command=release_bot_now,
        bg='#E2E8F0',
        activebackground='#CBD5E1',
        fg=THEME['slate_dark'],
        font=('Segoe UI', 9, 'bold'),
        padx=12,
        pady=7,
        relief='flat',
        cursor='hand2',
    ).pack(side='right')


def refresh_events():
    try:
        events_list = api('GET', '/api/events')
        for item_id in events_tree.get_children():
            events_tree.delete(item_id)
        status_map = {
            'sent': '✅ Enviada (Robô)',
            'human_handoff': '🔔 Transferido p/ Humano',
            'paused_human': '👨‍💼 Em Atendimento Humano',
            'closed_session': '🏁 Atendimento Encerrado',
            'simulated': '🧪 Simulada',
            'no_rule': '🔇 Sem regra (Silêncio)',
            'cooldown': '⏳ Ignorada (Repetida)',
            'error': '❌ Erro no envio',
            'processing': '🔄 Processando...',
        }
        new_handoffs = []
        for idx, ev in enumerate(events_list):
            mid = ev.get('message_id')
            st = ev.get('status')
            if st == 'human_handoff' and mid:
                if not _initial_events_loaded['done']:
                    _seen_handoff_ids.add(mid)
                elif mid not in _seen_handoff_ids:
                    _seen_handoff_ids.add(mid)
                    new_handoffs.append(ev)

            raw_time = (ev.get('received_at') or '')[:19].replace('T', ' ')
            raw_sender = (ev.get('sender') or '').replace('@s.whatsapp.net', '').replace('@lid', '')
            pname = (ev.get('push_name') or '').strip()
            sender_col = f'{pname} ({raw_sender})' if pname else raw_sender
            st_label = status_map.get(st, st)
            rep_preview = (ev.get('reply') or '-').replace('\n', ' ↵ ')

            if st == 'human_handoff':
                row_tag = 'handoff'
            elif st == 'paused_human':
                row_tag = 'paused'
            elif st == 'closed_session':
                row_tag = 'closed'
            else:
                row_tag = 'odd' if idx % 2 == 1 else 'sent'

            events_tree.insert(
                '',
                'end',
                tags=(row_tag,),
                values=(
                    raw_time,
                    sender_col,
                    ev.get('incoming') or '',
                    rep_preview,
                    st_label,
                ),
            )
        _initial_events_loaded['done'] = True
        for handoff_ev in new_handoffs:
            show_attendant_alert(handoff_ev)
    except Exception:
        pass


def populate_rules_tree(rules_list):
    rules_cache.clear()
    for rid in rules_tree.get_children():
        rules_tree.delete(rid)
    for idx, item in enumerate(rules_list):
        rules_cache[item['id']] = item
        preview_reply = str(item['reply']).replace('\n', ' ↵ ')
        tag = 'disabled' if not item['enabled'] else ('odd' if idx % 2 == 1 else 'even')
        rules_tree.insert(
            '',
            'end',
            tags=(tag,),
            values=(
                item['id'],
                item['keyword'],
                preview_reply,
                '🟢 Ativa' if item['enabled'] else '🔴 Inativa',
            ),
        )
    update_kpi_summary()


def refresh_status_only():
    try:
        s = api('GET', '/api/status')
        bh_tag = '  •  🌙 FORA DO EXPEDIENTE' if s.get('outside_business_hours') else '  •  ☀️ DENTRO DO EXPEDIENTE'
        if s.get('simulation_mode'):
            status_label.config(
                text=f'🟡 MODO SIMULAÇÃO (Pausado){bh_tag}',
                fg='#FBBF24',
            )
        else:
            status_label.config(
                text=f'🟢 ROBÔ ATIVO (Modo Real){bh_tag}',
                fg='#34D399',
            )
        if not rules_tree.get_children():
            populate_rules_tree(api('GET', '/api/rules'))
        if not _settings_loaded['done']:
            load_settings_into_ui()
        update_kpi_summary()
    except Exception:
        ensure_local_services()
        status_label.config(text='⏳ Iniciando servidor local... aguarde alguns segundos', fg='#FBBF24')


def refresh_all():
    try:
        s = api('GET', '/api/status')
        bh_tag = '  •  🌙 FORA DO EXPEDIENTE' if s.get('outside_business_hours') else '  •  ☀️ DENTRO DO EXPEDIENTE'
        if s.get('simulation_mode'):
            status_label.config(
                text=f'🟡 MODO SIMULAÇÃO (Pausado){bh_tag}',
                fg='#FBBF24',
            )
        else:
            status_label.config(
                text=f'🟢 ROBÔ ATIVO (Modo Real){bh_tag}',
                fg='#34D399',
            )
        populate_rules_tree(api('GET', '/api/rules'))
        load_settings_into_ui()
        refresh_qr_status()
        refresh_paused()
        refresh_events()
        update_kpi_summary()
    except Exception:
        ensure_local_services()
        status_label.config(text='⏳ Iniciando servidor local... aguarde alguns segundos', fg='#FBBF24')


def auto_poll():
    refresh_status_only()
    refresh_qr_status()
    refresh_paused()
    refresh_events()
    root.after(3000, auto_poll)


root.after(500, refresh_all)
root.after(3000, auto_poll)
root.mainloop()
