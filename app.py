from fastapi import FastAPI, HTTPException
import openai
import requests
import json
import os
from notion_client import Client
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pydantic import BaseModel

# 🔹 Clés API (via variables d'environnement)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "1b1d9062c346806b9753f5430bced77f"
SPREADSHEET_ID = "1NdKKbrvl10vZ1lwXYAUYlhhTTJq8wiedJzsE0-6F8I4"

# 🔹 Vérifier si les clés sont bien chargées
if not OPENAI_API_KEY:
    raise ValueError("❌ ERREUR : La clé OPENAI_API_KEY est manquante")
if not NOTION_API_KEY:
    raise ValueError("❌ ERREUR : La clé NOTION_API_KEY est manquante")

# 🔹 Définition des SCOPES Google API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# 🔹 Chargement des Credentials Google Sheets
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if credentials_json:
    creds_dict = json.loads(credentials_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    raise ValueError("❌ ERREUR : Les identifiants Google Sheets ne sont pas définis.")

# 🔹 Initialisation FastAPI
app = FastAPI()

# 🔹 Vérification si l'API fonctionne
@app.get("/")
def read_root():
    return {"message": "✅ API FastAPI en ligne 🚀"}

# 🔹 Connexion Notion
notion = Client(auth=NOTION_API_KEY)

# 🔹 Connexion Google API Services (Sheets + Drive)
sheets_service = build("sheets", "v4", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)

# 🔹 Configuration API OpenAI
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ===================== ✅ OPENAI GPT-4 ===================== #
class GPTRequest(BaseModel):
    prompt: str

@app.post("/gpt/generate")
def generate_content(request: GPTRequest):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        return {"generated_text": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI: {str(e)}")

# ===================== ✅ NOTION : Ajouter du contenu ===================== #
class UpdateNotionRequest(BaseModel):
    page_id: str
    prompt: str

@app.post("/gpt/generate_to_notion", operation_id="generate_notion_content")
def generate_and_update_notion(request: UpdateNotionRequest):
    """
    Génère du texte avec GPT-4 et l'ajoute à une page Notion.
    """
    try:
        # 🔹 Générer du texte avec GPT-4
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        generated_text = response.choices[0].message.content

        # 🔹 Construire la requête POST pour ajouter un bloc de texte
        url = f"https://api.notion.com/v1/blocks/{request.page_id}/children"
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        data = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": generated_text
                                }
                            }
                        ]
                    }
                }
            ]
        }

        # 🔹 DEBUG : Voir la requête envoyée à Notion
        print("🔍 Requête envoyée à Notion:", json.dumps(data, indent=4))

        # 🔹 Envoyer la requête POST à Notion
        notion_response = requests.post(url, headers=headers, json=data)

        # 🔹 DEBUG : Voir la réponse de Notion
        print("🔍 Réponse Notion:", notion_response.json())

        if notion_response.status_code == 200:
            return {"message": "✅ Texte ajouté à Notion", "content": generated_text}
        else:
            raise HTTPException(status_code=notion_response.status_code, detail=notion_response.json())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Erreur : {str(e)}")

# ===================== ✅ GOOGLE SHEETS ===================== #
@app.get("/sheets/{sheet_name}")
def get_google_sheet(sheet_name: str):
    try:
        result = sheets_service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=sheet_name).execute()
        values = result.get("values", [])
        return {"data": values if values else "Aucune donnée trouvée"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Google Sheets: {str(e)}")

@app.post("/sheets/update/{sheet_name}/{cell}")
def update_google_sheet(sheet_name: str, cell: str, new_value: str):
    body = {"values": [[new_value]]}
    try:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!{cell}",
            valueInputOption="RAW",
            body=body,
        ).execute()
        return {"message": f"✅ Cellule {cell} de {sheet_name} mise à jour avec {new_value}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Google Sheets: {str(e)}")
import logging

logging.basicConfig(level=logging.DEBUG)

@app.post("/gpt/generate_to_notion", operation_id="generate_notion_content")
def generate_and_update_notion(request: UpdateNotionRequest):
    """
    Génère du texte avec GPT-4 et l'ajoute à une page Notion.
    """
    try:
        # Générer du texte avec GPT-4
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        generated_text = response.choices[0].message.content

        # Construire la requête pour Notion
        url = f"https://api.notion.com/v1/blocks/{request.page_id}/children"
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        data = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": generated_text
                                }
                            }
                        ]
                    }
                }
            ]
        }

        # Debugging : Voir les logs
        logging.debug("📌 ENVOI À NOTION...")
        logging.debug(f"➡️ URL: {url}")
        logging.debug(f"➡️ Headers: {headers}")
        logging.debug(f"➡️ Payload: {json.dumps(data, indent=4)}")

        # Envoyer la requête POST à Notion
        notion_response = requests.post(url, headers=headers, json=data)

        # Debugging : Voir la réponse de Notion
        logging.debug("📌 RÉPONSE NOTION:")
        logging.debug(notion_response.json())

        if notion_response.status_code == 200:
            return {"message": "✅ Texte ajouté à Notion", "content": generated_text}
        else:
            logging.error(f"❌ Erreur Notion {notion_response.status_code}: {notion_response.json()}")
            raise HTTPException(status_code=notion_response.status_code, detail=notion_response.json())

    except Exception as e:
        logging.error(f"❌ ERREUR : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
