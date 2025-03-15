from fastapi import FastAPI, HTTPException
import openai
import requests
import json
from notion_client import Client
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 🔹 Clés API
import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_API_KEY = "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"
DATABASE_ID = "1b1d9062c346806b9753f5430bced77f"
SPREADSHEET_ID = "1NdKKbrvl10vZ1lwXYAUYlhhTTJq8wiedJzsE0-6F8I4"
SERVICE_ACCOUNT_FILE = "credentials.json"

# 🔹 Initialisation FastAPI
app = FastAPI()

# 🔹 Connexion Notion
notion = Client(auth=NOTION_API_KEY)

# 🔹 Connexion Google Services (Sheets + Drive)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# 🔹 Google API Services
sheets_service = build("sheets", "v4", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)

# 🔹 Configuration API OpenAI
openai.api_key = OPENAI_API_KEY

# ===================== NOTION ===================== #
@app.get("/notion/page/{page_id}")
def get_notion_page(page_id: str):
    """
    Récupère les détails d'une page Notion.
    """
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

from pydantic import BaseModel

class UpdateTitleRequest(BaseModel):
    new_title: str

@app.post("/notion/update_page/{page_id}")
def update_notion_page_content(page_id: str, request: UpdateTitleRequest):
    """
    Met à jour le titre d'une page Notion.
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    data = {
        "properties": {
            "title": [
                {
                    "text": {
                        "content": request.new_title
                    }
                }
            ]
        }
    }

    response = requests.patch(url, headers=headers, json=data)

    if response.status_code == 200:
        return {"message": "Page Notion mise à jour avec succès"}
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    
@app.get("/notion/children/1b1d9062c346806b9753f5430bced77f")
def get_notion_children(page_id: str):  # `page_id` doit être inclus dans l'URL

    """
    Récupère les sous-pages d'une page Notion.
    """
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
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
    
@app.post("/notion/update_block/{block_id}")
def update_notion_block(block_id: str, new_text: str):
    """
    Met à jour le texte d'un bloc Notion.
    """
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    data = {
        "paragraph": {
            "rich_text": [
                {
                    "text": {
                        "content": new_text
                    }
                }
            ]
        }
    }

    response = requests.patch(url, headers=headers, json=data)

    if response.status_code == 200:
        return {"message": "Bloc Notion mis à jour avec succès"}
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

# ===================== GOOGLE DRIVE ===================== #
@app.get("/drive/list")
def list_drive_files():
    try:
        results = drive_service.files().list(pageSize=10).execute()
        files = results.get("files", [])
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Drive: {str(e)}")

@app.get("/drive/download/{file_id}")
def download_drive_file(file_id: str):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_data = request.execute()
        return {"file_content": file_data.decode("utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de téléchargement: {str(e)}")

# ===================== OPENAI GPT-4 ===================== #
@app.get("/test_openai")
def test_openai():
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)  # Nouvelle façon d'utiliser OpenAI
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Dis-moi un fait intéressant sur l'espace."}]
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI: {str(e)}")

from pydantic import BaseModel

class GPTRequest(BaseModel):
    prompt: str

@app.post("/gpt/generate")
def generate_content(request: GPTRequest):
    """
    Génère un texte avec GPT-4 en fonction du prompt.
    """
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        return {"generated_text": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur OpenAI: {str(e)}")
    
    from pydantic import BaseModel

class UpdateNotionRequest(BaseModel):
    page_id: str
    prompt: str

@app.post("/gpt/generate_to_notion")
def generate_and_update_notion(request: UpdateNotionRequest):
    """
    Génère du texte avec GPT-4 et l'ajoute à une page Notion.
    """
    try:
        # Générer du texte avec GPT-4
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        generated_text = response.choices[0].message.content

        # Ajouter le texte à Notion
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

class UpdateSheetRequest(BaseModel):
    sheet_name: str
    cell: str
    prompt: str

@app.post("/gpt/generate_to_sheets")
def generate_and_update_sheets(request: UpdateSheetRequest):
    """
    Génère du texte avec GPT-4 et l'ajoute dans une cellule Google Sheets.
    """
    try:
        # Générer du texte avec GPT-4
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request.prompt}]
        )
        generated_text = response.choices[0].message.content

        # Ajouter le texte dans Google Sheets
        body = {"values": [[generated_text]]}
        sheets_service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{request.sheet_name}!{request.cell}",
            valueInputOption="RAW",
            body=body
        ).execute()

        return {"message": "Texte généré et ajouté à Google Sheets", "content": generated_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")


# ===================== DÉMARRER L'API ===================== #
# Lance cette commande pour démarrer l'API :
# uvicorn app:app --reload
