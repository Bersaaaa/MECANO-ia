# 🚗 AutoDoc Bot — Telegram

Bot Telegram de diagnostic automobile alimenté par Claude AI.

---

## 📦 Fichiers

```
autodoc-bot/
├── bot.py            # Code principal du bot
├── requirements.txt  # Dépendances Python
├── Procfile          # Commande de démarrage
├── railway.toml      # Config Railway
└── README.md
```

---

## 🚀 Déploiement sur Railway

### 1. Créer le bot Telegram

1. Ouvre [@BotFather](https://t.me/BotFather) sur Telegram
2. Tape `/newbot` et suis les instructions
3. Copie le **token** (ex: `7123456789:AAF...`)

### 2. Récupérer la clé Anthropic

1. Va sur [console.anthropic.com](https://console.anthropic.com)
2. Crée une clé API → copie-la

### 3. Déployer sur Railway

```bash
# Option A : via GitHub (recommandé)
# 1. Push ces fichiers sur un repo GitHub
# 2. Va sur railway.app → New Project → Deploy from GitHub

# Option B : via CLI Railway
npm install -g @railway/cli
railway login
railway init
railway up
```

### 4. Ajouter les variables d'environnement

Dans Railway → ton projet → Variables :

| Variable | Valeur |
|---|---|
| `TELEGRAM_TOKEN` | `7123456789:AAF...` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` |

### 5. C'est bon ! 🎉

Le bot redémarre automatiquement. Teste avec `/start` sur Telegram.

---

## 💬 Fonctionnalités

- 📸 **Photo** → analyse visuelle de pièces/dommages/voyants
- 🔢 **Code OBD** → diagnostic P0xxx, C0xxx, B0xxx
- 💬 **Texte libre** → décris le problème en langage naturel

**Réponse inclut :**
- Diagnostic + explication
- Causes probables
- Niveau d'urgence
- Peut rouler ou pas ?
- Coût pièce + main d'œuvre + total
- Temps de réparation
- Conseil pratique

---

## 💰 Coût estimé

- Railway : **~5$/mois** (plan Hobby)
- Claude API : **~0.001$/message** (très faible)
- Pour 1000 diagnostics/mois → ~1$ d'API
