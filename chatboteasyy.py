from fastapi import FastAPI
import json
import os
import logging
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import process, fuzz

app = FastAPI()

# Nastavení logování
logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("🚀 Spuštění aplikace")

# Povolení CORS
origins = [
    "http://dotazy.wz.cz",  # Povolte doménu, odkud budou přicházet požadavky
    "https://dotazy.wz.cz",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cesta k souboru s otázkami/odpověďmi a k Excel souboru
json_path = "Chatbot_zdroj.json"
excel_path = "chat_data.xlsx"

# Načtení existujících otázek z JSON souboru
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

# Seznam otázek pro vyhledávání
questions = [item["question"] for item in faq_data] if faq_data else []

# Funkce pro uložení otázek a odpovědí do Excel souboru
def save_to_excel(question, answer):
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
    else:
        df = pd.DataFrame(columns=['Question', 'Answer'])

    # Přidání nové řádky
    df = df.append({'Question': question, 'Answer': answer}, ignore_index=True)

    # Uložení zpět do Excelu
    df.to_excel(excel_path, index=False)

@app.on_event("startup")
def startup_event():
    logging.info("🌐 Server běží...")

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
        
        # Uložení otázky a odpovědi do Excelu
        save_to_excel(query, answer)
        
        return {"answer": answer}
    else:
        logging.info(f"⚠️ Dotaz '{query}' má skóre {best_match[1] if best_match else 'N/A'} a nevrací odpověď.")
        return {"answer": "Omlouvám se, ale na tuto otázku nemám odpověď."}
