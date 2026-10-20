# 🤖 WhatsAuto Empresarial — Central Inteligente de Atendimento WhatsApp

Sistema desktop completo para automação receptiva de atendimento no **WhatsApp** combinando **Python (Flask + Tkinter + SQLite)** e **Node.js (Baileys WebSocket QR Bridge)**.

Projetado para empresas que desejam responder clientes instantaneamente com menu interativo e regras inteligentes, sem perder o toque humano quando o cliente solicita falar com um atendente.

---

## ✨ Principais Funcionalidades

- 🖥️ **Painel Executivo Desktop Windows (`.exe`)**: Interface moderna inspirada no *WhatsApp Business SaaS* com indicadores em tempo real (Regras Ativas, Clientes em Atendimento, Status da Conexão e Expediente).
- 📱 **Conexão Direta via QR Code**: Conecte o WhatsApp da empresa em segundos diretamente pela Aba 2 do painel, sem depender de configuração complexa de webhook na nuvem.
- 👋 **Menu Inicial de Boas-Vindas Inteligente**:
  - Enviado automaticamente no primeiro contato, quando uma mensagem não corresponde a nenhuma regra específica, após 1 hora de intervalo ou sempre que um atendimento anterior é encerrado.
- 🧠 **Motor de Regras e Sinônimos**:
  - Reconhece opções numéricas (`1`, `2`, `3`, `4`) e sinônimos separados por vírgula (`preço, valor, quanto custa, orçamento`), ignorando acentos e diferenças de maiúsculas/minúsculas.
- 🔔 **Transbordo para Atendente Humano com Alerta Sonoro & Pop-up**:
  - Quando o cliente solicita atendimento humano (opção `4` ou palavras como `atendente`), o robô pausa automaticamente para aquele contato e exibe um **Pop-up Always-on-Top com alerta sonoro** na tela do computador do atendente.
- ⏱️ **Reset por Inatividade Bidirecional (15 min) + Mensagem de Encerramento**:
  - Enquanto cliente e atendente conversam (inclusive pelo celular ou WhatsApp Web), o cronômetro de 15 minutos é renovado automaticamente.
  - Após **15 minutos de silêncio de ambas as partes** (ou ao encerrar manualmente pelo painel), o sistema envia uma mensagem de encerramento ao cliente e reinicia o ciclo para que a próxima mensagem receba o Menu Inicial novamente.
- 🕒 **Gestão de Horário Comercial**:
  - Configurável por horário de início/fim e finais de semana, respondendo automaticamente com aviso de fora de expediente.
- 🛡️ **Comportamento Humanizado Anti-Bloqueio**:
  - Simula tempo de leitura e exibe o status **"Digitando..." (`composing`)** por `1,5s a 3,0s` antes de cada resposta automática.
  - Ignora automaticamente grupos, listas de transmissão, canais (newsletters) e atualizações de Status.

---

## 🛠️ Arquitetura e Tecnologias

| Camada | Tecnologia | Arquivo Principal |
| :--- | :--- | :--- |
| **Painel Desktop (GUI)** | Python, Tkinter / TTK Custom Theme, PyInstaller | `panel.py` |
| **Servidor & Motor de Regras** | Python, Flask, Waitress, SQLite3 | `server.py` |
| **Ponte WhatsApp QR Code** | Node.js, `@whiskeysockets/baileys`, Pino | `whatsapp_qr_bridge.js` |

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- **Python 3.10+**
- **Node.js 18+**

### 2. Instalação rápida
No PowerShell, dentro da pasta do projeto:

```powershell
# 1. Criar ambiente virtual Python e instalar dependências
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 2. Instalar dependências da ponte Node.js (QR Code)
npm install

# 3. Criar arquivo de configuração local
Copy-Item .env.example .env
```

### 3. Iniciar o Sistema Completo
Basta dar dois cliques em **`iniciar_whatsauto.bat`** (que inicia o servidor Python, a ponte QR Code em Node.js e abre o painel desktop), ou executar:

```powershell
# Terminal 1 - Servidor Backend
.\.venv\Scripts\python.exe server.py

# Terminal 2 - Ponte WhatsApp QR Code
node whatsapp_qr_bridge.js

# Terminal 3 - Painel Desktop
.\.venv\Scripts\python.exe panel.py
```

---

## 📦 Como Gerar o Executável (`.exe`) no Windows

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --icon "whatsauto.ico" --add-data "whatsauto.ico;." --name WhatsAutoPanel panel.py
```
O executável será gerado em `dist/WhatsAutoPanel.exe`.
