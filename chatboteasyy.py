from fastapi import FastAPI, HTTPException
from pydantic import BaseModel  # Importujeme BaseModel z Pydantic pro definici požadavků
import json
import os
import logging
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import process, fuzz
from github import Github
from io import BytesIO, StringIO
import psycopg2
from datetime import datetime

app = FastAPI()

# Třída pro přijetí hodnocení
class RatingRequest(BaseModel):
    answer_id: int  # ID odpovědi, která byla hodnocena
    rating: str     # Hodnocení (up, down nebo none)

# Nastavení logování
logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("🚀 Spuštění aplikace")

# Povolení CORS
origins = [
    "http://dotazy.wz.cz",
    "https://dotazy.wz.cz",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Povolení specifikovaných domén
    allow_credentials=True,
    allow_methods=["*"],  # Povolit všechny HTTP metody
    allow_headers=["*"],  # Povolit všechny hlavičky
)

# GitHub API token a repo informace (token načítáme z environmentální proměnné)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # GitHub token načtený z prostředí
REPO_NAME = 'Dahor212/chatboteasy'  # GitHub repozitář
CSV_FILE_PATH = 'chat_data.csv'  # Cesta k souboru na GitHubu (bez URL, pouze cesta k souboru v repozitáři)

# Nastavení připojení k GitHubu
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# Logujeme připojení k repozitáři
logging.info(f"📦 Připojeno k repozitáři: {REPO_NAME}")

# Cesta k JSON souboru (pro Render)
json_path = "Chatbot_zdroj.json"
faq_data = []
if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            faq_data = json.load(f)
        logging.info(f"✅ Načteno {len(faq_data)} záznamů z JSON souboru.")
    except Exception as e:
        logging.error(f"❌ Chyba při načítání JSON souboru: {str(e)}")
else:
    logging.error(f"⚠️ Chyba: Soubor {json_path} nebyl nalezen!")

questions = [item["question"] for item in faq_data] if faq_data else []

# Připojení k PostgreSQL databázi
def connect_db():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except Exception as e:
        logging.error(f"❌ Chyba při připojení k databázi: {e}")
        return None

# Vytvoření tabulky v PostgreSQL, pokud neexistuje
def create_table():
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chatbot_logs (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rating VARCHAR(10) DEFAULT 'none'  -- nový sloupec pro hodnocení
                );
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("✅ Tabulka byla úspěšně vytvořena nebo upravena.")
        except Exception as e:
            logging.error(f"❌ Chyba při vytváření tabulky: {e}")
            conn.close()

@app.on_event("startup")
def startup_event():
    logging.info("🌐 Server běží...")
    create_table()

@app.get("/")
def root():
    return {"message": "Chatbot API běží! Použij endpoint /chatbot/?query=VAŠE_OTÁZKA"}

@app.get("/chatbot/")
def chatbot(query: str):
    if not faq_data:
        logging.error("🚨 Databáze není načtena!")
        return {"answer": "Chyba: Databáze není načtena."}

    # Logování dotazu
    logging.info(f"📥 Dotaz od uživatele: {query}")

    # Vyhledání nejlepší shody
    best_match = process.extractOne(query, questions, scorer=fuzz.ratio)

    if best_match:
        logging.info(f"✅ Nejlepší shoda: {best_match[0]} (skóre: {best_match[1]})")
    else:
        logging.info("❌ Nenalezena žádná shoda.")

    if best_match and best_match[1] > 76:  # Snížený práh pro shodu
        index = questions.index(best_match[0])
        answer = faq_data[index]["answer"]
        logging.info(f"📤 Vrácená odpověď: {answer}")
        
        # Uložení dotazu a odpovědi do databáze
        save_to_db(query, answer)
        
        return {"answer": answer}
    else:
        logging.info(f"⚠️ Dotaz '{query}' má skóre {best_match[1] if best_match else 'N/A'} a nevrací odpověď.")
        save_to_db(query, "Omlouvám se, ale na tuto otázku nemám odpověď.")
        return {"answer": "Omlouvám se, ale na tuto otázku nemám odpověď."}

# Funkce pro uložení dotazu a odpovědi do PostgreSQL
def save_to_db(question, answer, rating='none'):
    try:
        conn = connect_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chatbot_logs (question, answer, rating)
                VALUES (%s, %s, %s)
            ''', (question, answer, rating))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info(f"✅ Úspěšně uloženo do databáze: {question} -> {answer}")
    except Exception as e:
        logging.error(f"❌ Chyba při ukládání do databáze: {e}")

# Funkce pro aktualizaci hodnocení odpovědi
@app.post("/rate_answer")
async def rate_answer(request: RatingRequest):
    try:
        logging.info(f"📥 Přijatý požadavek na hodnocení: {request}")
        # Připojení k databázi
        conn = connect_db()
        if conn:
            cursor = conn.cursor()

            # Pokud hodnocení neexistuje, nastavíme jej
            cursor.execute('''
                UPDATE chatbot_logs
                SET rating = %s
                WHERE id = %s
            ''', (request.rating, request.answer_id))

            conn.commit()
            cursor.close()
            conn.close()

            return {"success": True}
        else:
            raise HTTPException(status_code=500, detail="Chyba při připojení k databázi.")
    except Exception as e:
        logging.error(f"❌ Chyba při ukládání hodnocení: {e}")
        raise HTTPException(status_code=500, detail="Chyba při ukládání hodnocení.")
