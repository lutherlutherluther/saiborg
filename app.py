import os
import sys
import logging
import re
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# -------------------------------------------------------------------
# ENV + LOGGING
# -------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
load_dotenv()

# Try to import Monday client
try:
    from monday_client import _call_monday, search_items_by_text, get_all_items
    MONDAY_AVAILABLE = True
except ImportError:
    logger.warning("Could not find 'monday_client.py'. Monday functions will not work.")
    MONDAY_AVAILABLE = False
    def _call_monday(*args: Any) -> None: return None
    def search_items_by_text(*args: Any) -> List[Any]: return []
    def get_all_items(*args: Any) -> List[Any]: return []

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
CUSTOMER_BOARD_ID = int(os.getenv("MONDAY_CUSTOMER_BOARD_ID", "5085798849"))

# Validate required environment variables
required_vars = {
    "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
    "SLACK_APP_TOKEN": SLACK_APP_TOKEN,
    "GOOGLE_API_KEY": GOOGLE_API_KEY,
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    logger.error("Missing required environment variables: %s", ", ".join(missing_vars))
    for name, value in required_vars.items():
        status = "✅" if value else "❌"
        logger.error("  %s present? %s", name, status)
    sys.exit(1)

if not MONDAY_API_KEY:
    logger.warning("MONDAY_API_KEY missing – Monday functions will not work.")

# -------------------------------------------------------------------
# Slack app
# -------------------------------------------------------------------

logger.info("Initializing Slack App...")
app = App(token=SLACK_BOT_TOKEN)

# Get bot user ID to strip mentions correctly
try:
    auth_info = app.client.auth_test()
    BOT_USER_ID = auth_info["user_id"]
    logger.info("Bot user ID: %s", BOT_USER_ID)
except Exception as e:
    logger.error("Could not connect to Slack: %s", e)
    sys.exit(1)

# -------------------------------------------------------------------
# LLM + RAG (Chroma)
# -------------------------------------------------------------------

logger.info("Initializing Gemini + Chroma...")

# Use 'gemini-2.0-flash' as the standard model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.2,
)

embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

DB_PATH = os.getenv("CHROMA_DB_PATH", "chroma_db")
retriever: Optional[Any] = None

try:
    if os.path.exists(DB_PATH):
        logger.info("Found Chroma DB, loading...")
        vector_db = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
        retriever = vector_db.as_retriever(search_kwargs={"k": 5})
        logger.info("Chroma retriever ready.")
    else:
        logger.warning("No 'chroma_db' folder found, RAG disabled.")
except Exception as e:
    logger.error("Error loading ChromaDB (RAG disabled): %s", e)
    retriever = None

# -------------------------------------------------------------------
# Helper-funktioner
# -------------------------------------------------------------------

def strip_bot_mention(text: str) -> str:
    """Remove bot mention (e.g., '<@U123ABC>') from Slack text."""
    # Use regex to handle mentions more robustly
    pattern = rf"<@{BOT_USER_ID}>"
    return re.sub(pattern, "", text).strip()


def extract_customer_name(text: str) -> str:
    """Extract a customer name from a sentence."""
    t = text.strip()
    t = t.lstrip("-–— ").strip()
    lower = t.lower()

    # 1) Pattern: 'kunde' or 'kunden X' - stop at connectors
    # First try with explicit stop at connectors
    match = re.search(
        r"kunde[n]?\s+([A-Za-z0-9ÆØÅæøå][A-Za-z0-9ÆØÅæøå_-]*(?:\s+[A-Za-z0-9ÆØÅæøå][A-Za-z0-9ÆØÅæøå_-]*)*?)(?:\s+(?:i\s+monday|og|hvor|som|der))",
        t,
        re.IGNORECASE,
    )
    if match:
        name = match.group(1)
        return name.strip(" ?!.:,;")
    
    # Fallback: match without connector check, then manually stop
    match = re.search(
        r"kunde[n]?\s+([A-Za-z0-9ÆØÅæøå][A-Za-z0-9ÆØÅæøå ._-]+)",
        t,
        re.IGNORECASE,
    )
    if match:
        name = match.group(1)
        # Stop at common connectors
        for stop_word in [" i monday", " i ", " og ", " hvor ", " som ", " der "]:
            stop_idx = name.lower().find(stop_word)
            if stop_idx != -1:
                name = name[:stop_idx].strip()
                break
        return name.strip(" ?!.:,;")

    # 2) Look for "find X" or "X i monday" pattern
    # Try to find capitalized words (likely company names) before "i monday"
    match = re.search(r"find\s+([A-Z][A-Za-z0-9ÆØÅæøå]+)", t, re.IGNORECASE)
    if match:
        name = match.group(1)
        # Stop at common connectors
        for stop_word in [" i ", " og ", " hvor ", " som ", " der "]:
            if stop_word in name.lower():
                name = name.split(stop_word)[0]
        return name.strip(" ?!.:,;")

    # 3) Extract text before " i monday" or "og" or other connectors
    # Find the position of " i monday" or "og" or "hvor"
    connectors = [" i monday", " og ", " hvor ", " som ", " der "]
    earliest_idx = len(t)
    for connector in connectors:
        idx = lower.find(connector)
        if idx != -1 and idx < earliest_idx:
            earliest_idx = idx

    if earliest_idx < len(t):
        before = t[:earliest_idx].strip()
        # Remove "find" if present
        before = re.sub(r"^find\s+", "", before, flags=re.IGNORECASE)
        # Take the last word or capitalized word sequence
        parts = before.split()
        if parts:
            # If we have capitalized words, take them
            capitalized_parts = [p for p in parts if p and p[0].isupper()]
            if capitalized_parts:
                name = " ".join(capitalized_parts)
            else:
                name = parts[-1]
        else:
            name = before
        return name.strip(" ?!.:,;")

    # 4) Fallback: look for capitalized words (likely company names)
    capitalized_match = re.search(r"\b([A-Z][A-Za-z0-9ÆØÅæøå]+)\b", t)
    if capitalized_match:
        return capitalized_match.group(1).strip(" ?!.:,;")

    # 5) Last resort: use first meaningful word
    parts = t.split()
    for part in parts:
        if len(part) > 2 and part[0].isalnum():
            return part.strip(" ?!.:,;")

    return t.strip(" ?!.:,;")


def build_rag_answer(user_text: str) -> str:
    """Build an answer using PDF/RAG + LLM for a normal question."""
    context_parts: List[str] = []

    if retriever is not None:
        try:
            # Use .invoke() instead of .get_relevant_documents()
            docs = retriever.invoke(user_text)
            if docs:
                logger.info("Found %d relevant document snippets.", len(docs))
                for doc in docs[:5]:
                    src = doc.metadata.get('source', 'Unknown source')
                    page = doc.metadata.get('page', '?')
                    logger.debug("  - %s (page %s)", src, page)
                context_parts = [doc.page_content for doc in docs[:5]]
            else:
                logger.info("No documents matched the query.")
        except Exception as e:
            logger.error("Error during document search: %s", e)
            context_parts = []
    else:
        logger.info("RAG is not active (no Chroma DB).")

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""
Du er SAIBORG – en professionel, præcis og hjælpsom dansk AI-assistent.

DIT MÅL:
- Giv det bedst mulige svar på brugerens spørgsmål.
- Brug dokument-konteksten som PRIMÆR KILDE.
- Hvis konteksten ikke er relevant, så forklar, hvad du kan svare ud fra generel viden.
- Svar altid på klart, flydende og professionelt dansk.

BRUGERENS SPØRGSMÅL:
\"\"\"{user_text}\"\"\"

DOKUMENT-KONTEKST:
\"\"\"{context}\"\"\"

REGLER:
1) Du må aldrig opfinde tal, priser eller specifikke fakta, der ikke står i konteksten.
2) Hvis noget er uklart eller mangler i materialet, skal du sige det tydeligt.
3) Vær kortfattet, præcis og venlig i tonen.

OUTPUTFORMAT:
- Start med en 1–2 linjers opsummering.
- Giv derefter et struktureret svar (punktopstilling eller korte afsnit).
"""
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        logger.error("Error invoking LLM: %s", e)
        return "Beklager, jeg kunne ikke generere et svar lige nu. Prøv igen senere."


def build_monday_answer(user_text: str, items: List[Dict[str, Any]], mode: str = "summary") -> str:
    """Use LLM to format Monday results nicely.

    mode:
        - "summary": short CRM overview (default)
        - "email_followup": draft a follow-up email
        - "meeting_prep": prepare for a call/meeting
        - "next_steps": suggest concrete next actions
    """
    structured = []
    safe_items = items if items else []
    
    for item in safe_items:
        entry = {
            "name": item.get("name"),
            "id": item.get("id"),
            "columns": {
                cv.get("id"): cv.get("text")
                for cv in (item.get("column_values") or [])
            },
        }
        structured.append(entry)

    if mode == "email_followup":
        crm_prompt = f"""
Du er SAIBORG – en professionel dansk CRM-assistent.

OPGAVEN:
- Skriv et færdigt, venligt og salgsorienteret opfølgningsmail-udkast på dansk.
- Brug data fra Monday til at sætte scenen (navn, firma, kontekst, status).
- Foreslå tydeligt næste skridt (fx book et møde, sende materiale, bede om svar).

FORMAT:
- Emnelinje øverst.
- Derefter en kort, personlig mailtekst i 2–5 afsnit.
- Ingen tekniske detaljer som IDs, JSON, kolonnenavne osv.

DATA FRA MONDAY:
{structured}

BRUGERENS INSTRUKTION:
\"\"\"{user_text}\"\"\"
"""
    elif mode == "meeting_prep":
        crm_prompt = f"""
Du er SAIBORG – en dansk mødeforberedelses-assistent.

OPGAVEN:
- Hjælp brugeren med at forberede et salgsmøde/et kundemøde.
- Brug Monday-data til at opsummere: hvem kunden er, hvor sagen står, og hvad der er sket.
- Foreslå 3–7 konkrete punkter til dagsorden og 3–7 spørgsmål, der bør stilles.

FORMAT:
- Kort overblik (2–3 linjer).
- Punktopstilling med: "Status i dag", "Målsætning for mødet", "Forslag til dagsorden", "Vigtige spørgsmål".

DATA FRA MONDAY:
{structured}

BRUGERENS INSTRUKTION:
\"\"\"{user_text}\"\"\"
"""
    elif mode == "next_steps":
        crm_prompt = f"""
Du er SAIBORG – en dansk salgsstrategi-assistent.

OPGAVEN:
- Kig på CRM-data og foreslå helt konkrete næste skridt for sagen.
- Tænk i pipeline-næste trin, ansvarlig person, og realistisk tidslinje.

FORMAT:
- Kort statusopsummering (1–3 linjer).
- Punktopstilling med anbefalede næste skridt, med: hvad der skal gøres, af hvem, og hvornår.

DATA FRA MONDAY:
{structured}

BRUGERENS INSTRUKTION:
\"\"\"{user_text}\"\"\"
"""
    else:  # "summary"
        crm_prompt = f"""
Du er SAIBORG – en professionel dansk CRM-assistent.
Dit svar skal være kort, klart og salgsorienteret.

OPGAVEN:
- Opsummer lead/kunde på en naturlig og menneskelig måde.
- Brug almindeligt dansk, ikke rå kolonnenavne.
- Giv kun de vigtigste fakta: navn, rolle/titel, virksomhed, status og email.
- Giv gerne en kort anbefaling (fx "bør følges op", "venter på svar", "kan være varmt lead").
- Hvis der er flere matches: brug punktform med én linje per lead.

FORMAT:
- Overskrift: "**[Firma] – Kontakt: [Navn]**"
- Kort tekst på 1–3 linjer, der forklarer status.
- Kontaktinfo nederst i en punktopstilling.
- Ingen tekniske detaljer som IDs, JSON, kolonne-id'er osv.

DATA FRA MONDAY:
{structured}

BRUGERENS SPØRGSMÅL:
\"\"\"{user_text}\"\"\"
"""
    try:
        resp = llm.invoke(crm_prompt)
        return resp.content
    except Exception as e:
        logger.error("Error invoking LLM for Monday answer: %s", e)
        return "Beklager, jeg kunne ikke formatere Monday-resultaterne lige nu."


# -------------------------------------------------------------------
# Slack handler
# -------------------------------------------------------------------

@app.event("app_mention")
def handle_mention(event: Dict[str, Any], say: Any) -> None:
    """Main entry point when someone mentions @Saiborg in Slack."""
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event.get("ts"))

    raw_text = event.get("text", "")
    user_text = strip_bot_mention(raw_text)
    lower = user_text.lower()

    logger.info("Received message: %s", user_text)

    # Send "thinking..." message first
    say(text="🤔 Saiborg er i gang med at tænke...", thread_ts=thread_ts)

    try:
        reply = ""
        
        # 1) Monday health-check
        if "monday test" in lower:
            if not MONDAY_API_KEY:
                reply = "Jeg har ikke nogen Monday API-nøgle konfigureret."
            else:
                query = "query { me { name email } }"
                data = _call_monday(query)
                me = (data or {}).get("me")
                if me:
                    reply = f"✅ Monday-forbindelse virker! Du er logget ind som: {me.get('name')} ({me.get('email')})"
                else:
                    reply = "❌ Jeg kunne ikke læse brugerinfo fra Monday – tjek API-nøglen."

        # 2) Monday CRM-mode
        elif "monday" in lower or "crm" in lower:
            if not MONDAY_API_KEY:
                reply = "Jeg har ikke nogen Monday API-nøgle konfigureret, så jeg kan ikke læse CRM-data endnu."
            else:
                items: Optional[List[Dict[str, Any]]] = None
                mode = "summary"

                overview_phrases = [
                    "alle kunder", "alle leads", "hvilke leads har vi",
                    "hvilke kunder har vi", "overblik over vores leads", "overblik over kunder",
                ]

                email_phrases = [
                    "skriv en mail", "skriv en e-mail", "skriv email", "skriv en email",
                    "formuler en mail", "lav en mail", "follow up mail", "opfølgningsmail",
                ]

                meeting_phrases = [
                    "forbered møde", "forberedelse til møde", "mødeforberedelse",
                    "prepare meeting", "prepare for meeting", "salgsmøde", "kundemøde",
                ]

                next_step_phrases = [
                    "næste skridt", "next steps", "hvad gør vi nu", "hvad er næste skridt",
                    "hvad bør jeg gøre nu",
                ]

                if any(phrase in lower for phrase in overview_phrases):
                    logger.info("Monday lookup: fetching all items from board")
                    items = get_all_items(CUSTOMER_BOARD_ID)
                else:
                    search_term = extract_customer_name(user_text)
                    logger.info("Monday lookup for: '%s'", search_term)
                    items = search_items_by_text(CUSTOMER_BOARD_ID, search_term)

                # Decide which Monday mode to use, based on phrasing
                if any(phrase in lower for phrase in email_phrases):
                    mode = "email_followup"
                elif any(phrase in lower for phrase in meeting_phrases):
                    mode = "meeting_prep"
                elif any(phrase in lower for phrase in next_step_phrases):
                    mode = "next_steps"

                if not items:
                    reply = "Jeg kunne ikke finde nogen kunder/leads i Monday, der matcher din forespørgsel."
                else:
                    logger.info("Monday-lookup succeeded with %d items", len(items))
                    reply = build_monday_answer(user_text, items, mode=mode)

        # 3) Standard RAG-/AI-mode
        else:
            reply = build_rag_answer(user_text)

        app.client.chat_postMessage(
            channel=channel,
            text=reply,
            thread_ts=thread_ts,
        )

    except Exception as e:
        logger.exception("Error in handle_mention")
        app.client.chat_postMessage(
            channel=channel,
            text=f"❌ Der skete en fejl: {e}",
            thread_ts=thread_ts,
        )


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Connecting to Slack via Socket Mode...")
    logger.info("🤖 === SAIBORG IS ONLINE! === 🤖")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()