# Quickstart OmniAgent

## Prerequis
- Python 3.11+
- Node.js 20+
- Docker Desktop (pour PostgreSQL + Redis)

## Installation
```cmd
cd C:\Users\KOURO\omniagent
scripts\bootstrap.bat
```

## Demarrage en dev

### 1. API (backend)
```cmd
cd apps\api
.venv\Scripts\activate
uvicorn omniagent.main:app --reload
```
API dispo sur http://localhost:8000/docs

### 2. WEB (frontend)
```cmd
cd apps\web
npm run dev
```
App dispo sur http://localhost:3000

## Tester le module Recouvrement
1. Ouvre http://localhost:3000/recouvrement
2. Ajoute quelques factures (bouton "+ Ajouter une facture")
3. Clique "Lancer le scoring"
4. Les messages generes apparaissent a droite

## Tester l''API directement
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/recouvrement/plan
curl -X POST http://localhost:8000/api/recouvrement/run `
  -H "Content-Type: application/json" `
  -d "{\"invoices\":[{\"id\":\"1\",\"number\":\"F001\",\"debtor_id\":\"c1\",\"debtor_name\":\"ACME\",\"amount_due\":1500,\"due_date\":\"2025-04-01\"}]}"
```

## Configurer les integrations
Edite `apps\api\.env` et remplis tes cles :
- `OPENAI_API_KEY` (obligatoire pour LLM)
- `PENNYLANE_API_KEY` ou `STRIPE_SECRET_KEY` (factures)
- `WHATSAPP_PHONE_ID` + `WHATSAPP_TOKEN` (relances)
- `SENDGRID_API_KEY` (emails)
- `TWILIO_*` (SMS)