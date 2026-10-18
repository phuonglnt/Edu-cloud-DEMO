import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fastapi.responses import FileResponse



ASSISTANT_URL = os.getenv("ASSISTANT_URL", "http://open-webui:8080")
ASSISTANT_API_KEY = os.getenv("ASSISTANT_API_KEY", "")
MODEL = os.getenv("QUIZ_MODEL", "models/gemini-3.5-flash")

HEADERS = {"Authorization": f"Bearer {ASSISTANT_API_KEY}"}

app = FastAPI(title="Quiz API")

@app.get("/", include_in_schema=False)
def page():
    return FileResponse("index.html")


class QuizRequest(BaseModel):
    cours: str
    sujet: str = "le cours"
    nombre: int = 5


def bases_disponibles(client):
    reponse = client.get(f"{ASSISTANT_URL}/api/v1/knowledge/", headers=HEADERS)
    reponse.raise_for_status()
    donnees = reponse.json()
    if isinstance(donnees, dict):
        return donnees.get("items", [])
    return donnees


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cours")
async def lister_cours():
    """Liste les cours qui ont une base de connaissances."""
    async with httpx.AsyncClient(timeout=30) as client:
        reponse = await client.get(f"{ASSISTANT_URL}/api/v1/knowledge/", headers=HEADERS)
        reponse.raise_for_status()
        donnees = reponse.json()
        bases = donnees.get("items", []) if isinstance(donnees, dict) else donnees
    return [b["name"] for b in bases]


@app.post("/quiz")
async def generer_quiz(req: QuizRequest):
    prompt = (
        f"A partir des documents fournis, cree {req.nombre} questions "
        f"a choix multiples en francais sur : {req.sujet}. "
        "Chaque question a 4 options et une seule bonne reponse. "
        "Donne aussi la bonne reponse et une explication courte."
    )

    async with httpx.AsyncClient(timeout=180) as client:
        # On cherche la base de connaissances qui porte le nom du cours.
        reponse = await client.get(f"{ASSISTANT_URL}/api/v1/knowledge/", headers=HEADERS)
        reponse.raise_for_status()
        donnees = reponse.json()
        bases = donnees.get("items", []) if isinstance(donnees, dict) else donnees

        base = next((b for b in bases if b["name"] == req.cours), None)
        if base is None:
            noms = [b["name"] for b in bases]
            raise HTTPException(404, f"Aucune base pour le cours '{req.cours}'. Cours disponibles : {noms}")

        charge = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "files": [{"type": "collection", "id": base["id"]}],
        }

        reponse = await client.post(
            f"{ASSISTANT_URL}/api/chat/completions",
            headers=HEADERS,
            json=charge,
        )

    if reponse.status_code != 200:
        raise HTTPException(reponse.status_code, reponse.text[:300])

    contenu = reponse.json()["choices"][0]["message"]["content"]
    return {"cours": req.cours, "sujet": req.sujet, "quiz": contenu.split("\n")}