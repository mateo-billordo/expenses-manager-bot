# Expense Manager Bot

Bot de Telegram para gestión de gastos compartidos. Registra gastos desde un grupo, clasifica automáticamente por categoría usando keywords, permite adjuntar comprobantes y exportar reportes en CSV/ZIP.

## Features

- Registro de gastos via texto libre en grupo (`5200 efectivo Carrefour`)
- Clasificación automática por keywords configurables
- Adjuntar comprobantes (foto/PDF) con almacenamiento organizado
- Exportar a CSV o ZIP (con comprobantes)
- Resumen mensual por categoría
- Configuración de categorías, métodos de pago y keywords via DM admin
- Backup de la base de datos via Telegram
- Multi-usuario con autorización por ID
- Timeout automático de gastos pendientes (10 min)
- Todo en español 🇦🇷

## Setup

### 1. Crear el bot en Telegram

1. Hablar con @BotFather
1. Crear bot con `/newbot`
1. Copiar el token

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus valores.

### 3. Deploy con Docker

```bash
chmod +x deploy.sh
./deploy.sh
```

## Variables de entorno

| Variable       | Descripción                                   | Ejemplo                |
|----------------|-----------------------------------------------|------------------------|
| BOT_TOKEN      | Token del bot de Telegram (@BotFather)        | `123456:ABC-DEF...`   |
| ADMIN_ID       | Telegram user ID del administrador            | `123456789`            |
| ALLOWED_USERS  | IDs de usuarios autorizados (comma-separated) | `123456789,987654321`  |
| GROUP_CHAT_ID  | ID del grupo autorizado                       | `-1001234567890`       |

## Comandos

### Grupo (usuarios autorizados)

| Comando                                      | Descripción                          |
|----------------------------------------------|--------------------------------------|
| `<monto> [método] [comercio]`                | Registrar gasto                      |
| `/exportar <mes> <año> [--zip]`              | Exportar gastos del mes              |
| `/exportar <dd/mm/yyyy> <dd/mm/yyyy> [--zip]`| Exportar rango de fechas            |
| `/resumen [mes] [año]`                       | Resumen mensual por categoría        |
| `/ultimos [N]`                               | Últimos N gastos (default: 5)        |

### DM Admin

| Comando   | Descripción                                         |
|-----------|-----------------------------------------------------|
| `/config` | Menú de configuración (categorías, métodos, keywords) |
| `/backup` | Descargar backup de la base de datos                |

## Arquitectura

```text
bot/
├── main.py          # Entry point, bot initialization
├── config.py        # Environment config + messages
├── db.py            # SQLite database layer
├── models.py        # Data classes and enums
├── parser.py        # Text parser (amount, method, vendor)
├── classifier.py    # Keyword-based category classifier
├── keyboards.py     # Inline keyboard builders
├── file_manager.py  # Receipt file storage
├── state.py         # In-memory pending expense state
└── handlers/
    ├── expense.py   # Expense registration flow
    ├── export.py    # Export and reporting commands
    └── admin.py     # Admin configuration (DM only)
```

### Flujo de registro

1. Usuario envía texto → parser extrae monto, método, comercio
1. Classifier intenta asignar categoría por keywords
1. Bot pregunta datos faltantes con inline buttons
1. Usuario confirma → gasto registrado en SQLite
1. Opcionalmente adjunta comprobante antes de confirmar

### Almacenamiento

- Base de datos: `data/expenses.db` (SQLite WAL mode)
- Comprobantes: `data/receipts/YYYY/MM/<fecha>_<cat>_<comercio>_<monto>.<ext>`

## Formato de montos aceptados

| Input        | Interpretación |
|:------------:|:--------------:|
| `5200`       | $5200          |
| `$5.200`     | $5200          |
| `5.200,50`   | $5200.50       |
| `$5200.50`   | $5200.50       |
| `5200,50`    | $5200.50       |

## Desarrollo local

```bash
pip install -r requirements.txt
cp .env.example .env
# Editar .env
python -m bot.main
```
