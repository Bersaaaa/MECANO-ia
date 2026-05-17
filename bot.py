import os
import json
import base64
import logging
import asyncio
import anthropic
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN manquant dans les variables d'environnement")
if not ANTHROPIC_API_KEY:
    raise ValueError("❌ ANTHROPIC_API_KEY manquant dans les variables d'environnement")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Teste la connexion à l'API au démarrage
try:
    test = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": "ok"}],
    )
    logger.info("✅ Connexion Anthropic OK")
except Exception as e:
    logger.error(f"❌ Erreur connexion Anthropic: {e}")
    raise

SYSTEM_PROMPT = """Tu es AutoDoc, un expert en diagnostic automobile. Tu analyses des photos de voitures, codes défaut OBD, et descriptions de problèmes mécaniques.

Pour chaque problème, réponds UNIQUEMENT en JSON valide avec cette structure exacte (sans markdown, sans backticks, sans texte avant ou après):
{
  "diagnostic": "Nom du problème identifié",
  "explication": "Explication claire du problème en 2-3 phrases",
  "causes": ["cause 1", "cause 2", "cause 3"],
  "urgence": "critique|élevée|modérée|faible",
  "peutRouler": true,
  "reparations": [
    {"piece": "nom de la pièce", "coutPiece": "XX - XXX €", "mainOeuvre": "XX - XXX €", "total": "XXX - XXX €"}
  ],
  "conseilsMecanicien": "Conseil pratique pour le mécanicien ou le propriétaire",
  "tempsReparation": "X - X heures"
}

Sois précis sur les fourchettes de prix (marché français). Si c'est une photo, décris ce que tu vois avant de diagnostiquer."""

URGENCE_EMOJI = {
    "critique": "🚨",
    "élevée": "⚠️",
    "modérée": "🔶",
    "faible": "✅",
}


def format_response(data: dict) -> str:
    urgence = data.get("urgence", "modérée")
    emoji = URGENCE_EMOJI.get(urgence, "🔶")
    peut_rouler = data.get("peutRouler", True)
    rouler_text = "✅ Vous pouvez rouler prudemment" if peut_rouler else "🚫 Ne roulez pas — remorquage conseillé"

    lines = [
        f"{emoji} *Urgence : {urgence.upper()}*",
        rouler_text,
        "",
        f"🔍 *Diagnostic : {data.get('diagnostic', 'Inconnu')}*",
        f"_{data.get('explication', '')}_",
        "",
        "🧩 *Causes probables :*",
    ]

    for cause in data.get("causes", []):
        lines.append(f"  • {cause}")

    reparations = data.get("reparations", [])
    if reparations:
        lines.append("")
        lines.append("💰 *Coût de réparation estimé :*")
        for r in reparations:
            lines.append(f"  🔧 *{r.get('piece', '')}*")
            lines.append(f"     Pièce : {r.get('coutPiece', 'N/A')}")
            lines.append(f"     Main d'œuvre : {r.get('mainOeuvre', 'N/A')}")
            lines.append(f"     💵 Total : *{r.get('total', 'N/A')}*")

    lines.append("")
    lines.append(f"⏱ *Temps de réparation :* {data.get('tempsReparation', 'N/A')}")
    lines.append("")
    lines.append(f"💡 *Conseil :*")
    lines.append(f"_{data.get('conseilsMecanicien', '')}_")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ _Estimation indicative — consultez toujours un professionnel qualifié_")

    return "\n".join(lines)


def _call_claude(content) -> str:
    """Appel synchrone à Claude (exécuté dans un thread séparé)."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text.strip()


async def analyze_with_claude(text: str = None, image_bytes: bytes = None) -> str:
    try:
        if image_bytes:
            image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": text if text else "Analyse cette image de voiture et identifie tout problème visible.",
                },
            ]
        else:
            content = text

        # Exécute l'appel bloquant dans un thread pour ne pas bloquer asyncio
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _call_claude, content)

        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return format_response(data)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} | raw={raw[:200] if 'raw' in dir() else 'N/A'}")
        return "❌ Réponse inattendue du modèle. Réessaie en donnant plus de détails."
    except anthropic.AuthenticationError:
        logger.error("Clé API Anthropic invalide !")
        return "❌ Erreur d'authentification API. Vérifie la clé ANTHROPIC_API_KEY dans Railway."
    except anthropic.RateLimitError:
        return "⏳ Trop de requêtes. Attends quelques secondes et réessaie."
    except Exception as e:
        logger.error(f"Erreur Claude: {type(e).__name__}: {e}")
        return f"❌ Erreur : {type(e).__name__}. Consulte les logs Railway pour plus de détails."


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🔧 Comment ça marche ?"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Bonjour ! Je suis *AutoDoc*, votre assistant de diagnostic automobile.\n\n"
        "Envoyez-moi :\n"
        "📸 Une *photo* (voyant, pièce, dommage)\n"
        "🔢 Un *code défaut* (ex: P0420, P0301)\n"
        "💬 Une *description* du problème\n\n"
        "Je vous donnerai un diagnostic complet avec les coûts de réparation estimés ! 🚗",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Comment utiliser AutoDoc :*\n\n"
        "1️⃣ *Photo* → Envoyez directement une photo\n"
        "2️⃣ *Code OBD* → Tapez le code (P0xxx, C0xxx, B0xxx)\n"
        "3️⃣ *Description* → Décrivez votre problème en texte\n\n"
        "*Exemples :*\n"
        "• `P0420 – voyant moteur allumé`\n"
        "• `Fumée blanche au démarrage, odeur sucrée`\n"
        "• `Bruit de claquement en virage à droite`\n"
        "• `Vibrations au freinage à haute vitesse`\n\n"
        "💡 Plus vous donnez de détails, plus le diagnostic est précis !",
        parse_mode="Markdown",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔧 Comment ça marche ?":
        await help_command(update, context)
        return

    thinking_msg = await update.message.reply_text("🔍 Analyse en cours, veuillez patienter...")

    result = await analyze_with_claude(text=text)

    await thinking_msg.delete()
    await update.message.reply_text(result, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]  # Plus haute résolution
    caption = update.message.caption or ""

    thinking_msg = await update.message.reply_text("📸 Photo reçue ! Analyse visuelle en cours...")

    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    result = await analyze_with_claude(text=caption if caption else None, image_bytes=bytes(image_bytes))

    await thinking_msg.delete()
    await update.message.reply_text(result, parse_mode="Markdown")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        thinking_msg = await update.message.reply_text("📎 Image reçue ! Analyse en cours...")
        file = await context.bot.get_file(doc.file_id)
        image_bytes = await file.download_as_bytearray()
        caption = update.message.caption or ""
        result = await analyze_with_claude(text=caption if caption else None, image_bytes=bytes(image_bytes))
        await thinking_msg.delete()
        await update.message.reply_text(result, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "❌ Format non supporté. Envoyez une photo ou un texte décrivant le problème."
        )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("🚗 AutoDoc Bot démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
