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

# 🔹 Définition des SCOPES Google API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# 🔹 Chargement des Credentials Google Sheets depuis Render
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if credentials_json:
    creds_dict = json.loads(credentials_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    raise ValueError("Les identifiants Google Sheets ne sont pas définis.")

# 🔹 Initialisation FastAPI
app = FastAPI()

# 🔹 Vérification si l'API fonctionne
@app.get("/")
def read_root():
    return {"message": "API FastAPI est bien en ligne 🚀"}

# 🔹 Connexion Notion
notion = Client(auth=NOTION_API_KEY)

# 🔹 Connexion Google API Services (Sheets + Drive)
sheets_service = build("sheets", "v4", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)

# 🔹 Configuration API OpenAI
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ===================== NOTION ===================== #
@app.get("/notion/page/{page_id}")
def get_notion_page(page_id: str):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())

class UpdateTitleRequest(BaseModel):
    new_title: str

@app.post("/notion/update_page/{page_id}")
def update_notion_page_content(page_id: str, request: UpdateTitleRequest):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    data = {
        "properties": {
            "title": {
                "title": [{"text": {"content": request.new_title}}]
            }
        }
    }

    response = requests.patch(url, headers=headers, json=data)

    if response.status_code == 200:
        return {"message": "Page Notion mise à jour avec succès"}
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())

# ===================== GOOGLE SHEETS ===================== #
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
        return {"message": f"Cellule {cell} de {sheet_name} mise à jour avec {new_value}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Google Sheets: {str(e)}")

# ===================== OPENAI GPT-4 ===================== #
@app.get("/test_openai")
def test_openai():
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Dis-moi un fait intéressant sur l'espace."}]
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI: {str(e)}")

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

class UpdateNotionRequest(BaseModel):
    page_id: str
    prompt: str

@app.post("/gpt/generate_to_notion")
def generate_and_update_notion(request: UpdateNotionRequest):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        generated_text = response.choices[0].message.content

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
        notion_response = requests.patch(url, headers=headers, json=data)

        if notion_response.status_code == 200:
            return {"message": "Texte généré et ajouté à Notion", "content": generated_text}
        else:
            raise HTTPException(status_code=notion_response.status_code, detail=notion_response.json())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
