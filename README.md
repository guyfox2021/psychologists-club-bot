# Psychologists Closed Community Bot

Telegram-only subscription platform that automates onboarding, document verification, admin
review, payment-method authorization, a free trial and recurring paid access management for a
closed Telegram community of psychologists, students and supervisors.

Interface language: Ukrainian. Code/comments: English.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [1. Create the Telegram bot](#1-create-the-telegram-bot)
- [2. Create the closed community channel](#2-create-the-closed-community-channel)
- [3. Monobank Acquiring merchant token](#3-monobank-acquiring-merchant-token)
- [4. Configure environment variables](#4-configure-environment-variables)
- [5. Run with Docker (recommended)](#5-run-with-docker-recommended)
- [6. Run locally without Docker](#6-run-locally-without-docker)
- [Database migrations](#database-migrations)
- [Admin commands](#admin-commands)
- [Important notes on the Monobank integration](#important-notes-on-the-monobank-integration)

## Features

- Admin-only onboarding: role selection, questionnaire, multi-file document upload
  (PDF/JPG/PNG), application review (approve / reject / request more documents)
- Supervisors get permanent, immediate access; students/psychologists get a free trial followed
  by a recurring paid subscription
- Monobank Acquiring integration: card tokenization via a hosted zero-charge verification
  invoice, server-to-server recurring charges by token, ECDSA-signed webhook callbacks
- Automatic daily scheduler: charges due trials/subscriptions, kicks users on failed payment,
  restores access (new invite link) on a successful retry, sends expiration reminders
- Admin panel: `/applications`, `/users`, `/search`, `/subscriptions`, `/payments`, `/stats`,
  `/settings`, `/broadcast`
- Full structured logging (console + rotating file), Docker Compose deployment

## Architecture

Clean Architecture, async end to end (aiogram 3 + SQLAlchemy 2 async + asyncpg):

```
app/
  main.py            # wiring: bot, dispatcher, aiohttp app, scheduler
  config/            # pydantic-settings (.env)
  database/
    models/          # SQLAlchemy ORM models (10 tables)
    repositories/     # one repository per model
  services/           # domain services (users, applications, documents, notifications,
                       # access/invite-links, admin logs, settings, broadcast, subscriptions)
  payments/           # Monobank client, schemas, payment orchestration, webhook handler
  admin/              # admin-only keyboards + handlers (mounted behind AdminOnlyMiddleware)
  handlers/            # public onboarding + payment-confirmation handlers
  middlewares/         # DB session injection, request logging, admin gate
  scheduler/            # APScheduler daily maintenance job
  states/               # aiogram FSM state groups
  keyboards/            # public inline keyboards + callback data
  utils/                # logging, datetime helpers, upload validators
migrations/             # Alembic (async), versions/0001_initial_schema.py
```

Database tables: `roles`, `users`, `applications`, `documents`, `payment_tokens`, `payments`,
`trials`, `subscriptions`, `notifications`, `admin_logs`, `settings`.

## Requirements

- Python 3.12 (only if running locally without Docker)
- Docker + Docker Compose (recommended path)
- A public HTTPS domain (or a tunnel like ngrok for testing) — required for the Monobank
  webhook, and for Telegram webhook mode if you keep `USE_TELEGRAM_WEBHOOK=true`

## 1. Create the Telegram bot

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` and follow the prompts to choose a name and username.
3. BotFather replies with an HTTP API **token** — copy it into `BOT_TOKEN` in your `.env`.
4. Optionally set a bot description/avatar with `/setdescription` and `/setuserpic`.

## 2. Create the closed community channel

1. Create a private Telegram channel (or supergroup) for the community.
2. Add your bot to it and **promote it to administrator** with the right to invite users via
   links (and ban/unban users, since the bot manages access automatically).
3. Get the channel's numeric ID (e.g. by forwarding a message from it to
   [@userinfobot](https://t.me/userinfobot), or via `getUpdates`/any chat-id-lookup bot) and put
   it in `COMMUNITY_CHAT_ID` in `.env`. You can also set/change it later from Telegram with the
   admin `/settings` command → "📢 Канал спільноти" (send the channel's `@username`, numeric ID,
   or an invite link — the bot verifies it is already an admin there before accepting it).

## 3. Monobank Acquiring merchant token

1. The merchant needs a Monobank business account ("Мій ФОП" or corporate) with Acquiring
   enabled.
2. Get the API token from [web.monobank.ua](https://web.monobank.ua/) → Acquiring / API section
   → copy it into `MONOBANK_TOKEN`.
3. Set `MONOBANK_MERCHANT_DOMAIN` to the bot's public domain (used only for reference/logging,
   not sent to Monobank).
4. Leave `MONOBANK_API_URL` as the default unless Monobank support tells you otherwise.
5. Sanity-check the token before deploying:

   ```bash
   curl -s -H "X-Token: $MONOBANK_TOKEN" https://api.monobank.ua/api/merchant/details
   ```

   A valid token returns `{"merchantId": "...", "merchantName": "...", "edrpou": "..."}`.

> **Read this before processing a single real payment.** The Monobank field names, endpoints and
> statuses implemented in `app/payments/monobank_client.py` reflect the publicly documented
> Acquiring API contract (`https://monobank.ua/api-docs/acquiring`) at the time this integration
> was written. Payment gateway APIs change; every request/response field in that file should be
> re-verified against the current docs before going live. The whole integration is deliberately
> isolated behind `MonobankClient` so that if a field needs correcting, it only needs fixing in
> that one file — nothing else in the codebase depends on Monobank's raw field names.
>
> The implemented flow: the "confirm payment method" step creates a hosted invoice with
> `paymentType: "verification"` and `amount: 0` — a genuine zero-charge card verification (no
> refund workaround needed, unlike gateways that require charging a small hold first) — which
> returns a `cardToken` via `walletData` once completed. All later trial-end/renewal charges are
> triggered directly by our own daily scheduler (not any autonomous billing engine on Monobank's
> side), using that stored `cardToken` against `POST /api/merchant/wallet/payment`.
>
> Webhook callbacks are signed with ECDSA/SHA-256 in the `X-Sign` header; the public key is
> fetched from `GET /api/merchant/pubkey` and cached in-process for an hour. Monobank expects a
> plain `200 OK` back from the webhook (no signed acknowledgement body, unlike some other
> gateways) — retrying up to 3 times otherwise.

## 4. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Key variables:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Token from BotFather |
| `SUPER_ADMIN_IDS` | Comma-separated Telegram user IDs with permanent admin access |
| `COMMUNITY_CHAT_ID` | Bootstrap value for the tracked channel (can be changed via `/settings`) |
| `USE_TELEGRAM_WEBHOOK` | `true` to receive Telegram updates via webhook, `false` for long polling |
| `WEBHOOK_BASE_URL` | Public HTTPS base URL (required for the Monobank webhook either way) |
| `WEBHOOK_SECRET_TOKEN` | Random secret Telegram echoes back on every webhook call — generate one, e.g. `openssl rand -hex 32` |
| `POSTGRES_*` | PostgreSQL connection parameters |
| `REDIS_*` | Redis connection parameters (FSM storage) |
| `MONOBANK_*` | Merchant credentials from step 3 |

## 5. Run with Docker (recommended)

```bash
docker compose up --build -d
docker compose logs -f bot
```

This starts PostgreSQL, Redis and the bot. The bot's entrypoint (`docker-entrypoint.sh`) runs
`alembic upgrade head` automatically before starting, so the schema (and seed data — the three
roles and a default `settings` row) is always up to date.

To stop everything:

```bash
docker compose down
```

## 6. Run locally without Docker

1. Install Python 3.12 and PostgreSQL + Redis locally (or point `.env` at remote instances).
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create the database:

   ```sql
   CREATE DATABASE psychologists_club;
   CREATE USER psychologists_club WITH PASSWORD 'change_me_strong_password';
   GRANT ALL PRIVILEGES ON DATABASE psychologists_club TO psychologists_club;
   ```
4. Apply migrations (see below), then run the bot:

   ```bash
   python -m app.main
   ```

## Database migrations

```bash
# apply all migrations
alembic upgrade head

# generate a new migration after changing models
alembic revision --autogenerate -m "describe the change"

# roll back the last migration
alembic downgrade -1
```

## Admin commands

| Command | Description |
|---|---|
| `/applications` | List pending verification applications with approve/reject/request-docs actions |
| `/users` | List the most recently registered users |
| `/search <telegram_id>` | Look up a user and ban/unban, promote/demote admin, change role |
| `/subscriptions` | Overview of subscription counts by status |
| `/payments` | List recent payments |
| `/stats` | Aggregate platform statistics (users, applications, subscriptions, revenue) |
| `/settings` | View/edit trial length, subscription price/duration, reminder schedule, community channel |
| `/broadcast` | Send a message to all users or to a specific role |

## Important notes on the Monobank integration

See the callout in [section 3](#3-monobank-acquiring-merchant-token) above — it is repeated here
because it matters: **verify every Monobank request/response field against the live API docs
before processing real payments.**
