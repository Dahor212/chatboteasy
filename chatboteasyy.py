from fastapi import FastAPI
import json
import os
import logging
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import process, fuzz
from github import Github
from io import BytesIO, StringIO

app = FastAPI()

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
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GitHub API token a repo informace (token načítáme z environmentální proměnné)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # GitHub token načtený z prostředí
REPO_NAME = 'Dahor212/chatboteasy'  # GitHub repozitář
EXCEL_FILE_PATH = 'https://github.com/Dahor212/chatboteasy/blob/main/chat_data.xlsx'  # Cesta k souboru na GitHubu

# Nastavení připojení k GitHubu
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

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
        
        # Uložení dotazu a odpovědi do Excelu na GitHub
        save_to_excel(query, answer)
        
        return {"answer": answer}
    else:
        logging.info(f"⚠️ Dotaz '{query}' má skóre {best_match[1] if best_match else 'N/A'} a nevrací odpověď.")
        save_to_excel(query, "Omlouvám se, ale na tuto otázku nemám odpověď.")
        return {"answer": "Omlouvám se, ale na tuto otázku nemám odpověď."}

# Funkce pro uložení do Excelu na GitHub
def save_to_excel(question, answer):
    try:
        # Stáhnutí souboru z GitHubu
        file = repo.get_contents(EXCEL_FILE_PATH)
        content = file.decoded_content.decode("utf-8")

        # Přečtěte existující data do DataFrame
        df = pd.read_excel(StringIO(content))

        # Přidání nového záznamu
        new_row = pd.DataFrame({"Question": [question], "Answer": [answer]})
        df = pd.concat([df, new_row], ignore_index=True)

        # Uložení do nového souboru
        with BytesIO() as output:
            df.to_excel(output, index=False)
            output.seek(0)
            # Přejeďte soubor zpět na GitHub
            repo.update_file(EXCEL_FILE_PATH, "Add new question and answer", output.read(), file.sha)

        logging.info(f"✅ Úspěšně uloženo do Excelu na GitHub: {EXCEL_FILE_PATH}")
    except Exception as e:
        logging.error(f"❌ Chyba při ukládání do Excelu na GitHubu: {str(e)}")
