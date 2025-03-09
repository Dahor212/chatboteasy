from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import logging
import psycopg2
from datetime import datetime

app = FastAPI()

# Povolení CORS pro konkrétní domény
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

# Třída pro přijetí hodnocení
class RatingRequest(BaseModel):
    answer_id: int  # ID odpovědi, která byla hodnocena
    rating: str     # Hodnocení (up, down nebo none)

# Nastavení logování
logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("🚀 Spuštění aplikace")

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
    # Tento endpoint bude hledat odpověď na základě dotazu
    pass

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
        # Připojení k databázi
        conn = connect_db()
        if conn:
            cursor = conn.cursor()

            # Aktualizace ratingu pro daný záznam
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
