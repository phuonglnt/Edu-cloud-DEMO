import os
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from openai import OpenAI, OpenAIError

app = FastAPI(title="API Statistiques Moodle", version="2.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"
llm_client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "your_api_key_here"),
    base_url=os.getenv("LLM_BASE_URL") or None,
)
llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")


class TutorHTMLSanitizer(HTMLParser):
        allowed_tags = {"b", "ul", "li", "p"}

        def __init__(self):
                super().__init__(convert_charrefs=True)
                self.parts = []
                self.open_tags = []

        def handle_starttag(self, tag, attrs):
                if tag in self.allowed_tags:
                        self.parts.append(f"<{tag}>")
                        self.open_tags.append(tag)

        def handle_endtag(self, tag):
                if tag in self.open_tags:
                        while self.open_tags:
                                open_tag = self.open_tags.pop()
                                self.parts.append(f"</{open_tag}>")
                                if open_tag == tag:
                                        break

        def handle_data(self, data):
                self.parts.append(escape(data))


def render_tutor_page(content, is_error=False, status_code=200):
        content_class = "alert alert-danger" if is_error else "tutor-content"
        page = f"""<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Tuteur IA - Écosystème Éducatif</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f8f9fa; color: #343a40; }}
        .navbar-moodle {{ background-color: #0f6cb6; }}
        .tutor-card {{ max-width: 820px; border: 1px solid #dee2e6; border-radius: .35rem; }}
        .tutor-content p:last-child {{ margin-bottom: 0; }}
        .breadcrumb-item a {{ color: #0f6cb6; text-decoration: none; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-dark navbar-moodle">
        <div class="container">
            <a class="navbar-brand fw-semibold" href="http://localhost:8080">Écosystème Éducatif - Tuteur IA</a>
        </div>
    </nav>
    <main class="container py-4 py-md-5">
        <nav aria-label="Fil d’Ariane">
            <ol class="breadcrumb small">
                <li class="breadcrumb-item"><a href="http://localhost:8080">Accueil</a></li>
                <li class="breadcrumb-item"><a href="http://localhost:8080">Cours</a></li>
                <li class="breadcrumb-item"><a href="http://localhost:8080">Master SIGLIS</a></li>
                <li class="breadcrumb-item active" aria-current="page">Tuteur Virtuel</li>
            </ol>
        </nav>
        <div class="card tutor-card shadow-sm mx-auto mt-4">
            <div class="card-header bg-white py-3">
                <h1 class="h4 mb-0">Votre tuteur en Cloud Computing</h1>
            </div>
            <div class="card-body p-4">
                <div class="{content_class}">{content}</div>
                <a class="btn btn-primary mt-3" href="javascript:history.back()">Retour au cours</a>
            </div>
        </div>
    </main>
</body>
</html>"""
        return HTMLResponse(content=page, status_code=status_code)


@app.get("/api/tuteur-interactif", response_class=HTMLResponse)
def tuteur_interactif():
        prompt_systeme = (
                "Tu es un tuteur universitaire spécialisé en Cloud Computing. En français, propose un conseil "
                "concret et concis de révision, puis un mini-quiz contenant exactement une question. "
                "Réponds uniquement en HTML basique en utilisant seulement les balises <b>, <ul>, <li> et <p>. "
                "N’ajoute aucun script, attribut HTML, lien ou bloc de code."
        )
        try:
                response = llm_client.chat.completions.create(
                        model=llm_model,
                    messages=[
                        {"role": "system", "content": prompt_systeme},
                        {
                            "role": "user",
                            "content": (
                                "Aide-moi à réviser les concepts fondamentaux du Cloud Computing. "
                                "Donne un conseil de révision puis une seule question de quiz, en HTML."
                            ),
                        },
                    ],
                        max_tokens=1200,
                        temperature=0.7,
                )
                contenu = response.choices[0].message.content
                if not contenu:
                        raise OpenAIError("Le modèle n'a retourné aucun contenu.")

                sanitizer = TutorHTMLSanitizer()
                sanitizer.feed(contenu)
                sanitizer.close()
                return render_tutor_page("".join(sanitizer.parts))
        except OpenAIError:
                message_erreur = (
                        "Le tuteur est momentanément indisponible. Réessayez dans quelques instants."
                )
                return render_tutor_page(escape(message_erreur), is_error=True, status_code=502)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")

def get_db_connection():
    try:
        return psycopg.connect(
            host=os.getenv("DB_HOST", "postgres"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("DB_USER", "moodleuser"),
            password=os.getenv("DB_PASSWORD", "moodlepassword"),
            dbname=os.getenv("DB_NAME", "moodledb"),
            row_factory=dict_row,
        )
    except psycopg.Error as e:
        raise HTTPException(status_code=503, detail=f"Base de données indisponible: {e}")

@app.get("/health")
def health_check():
    """Vérifie si l'API et la base de données sont en ligne."""
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "en ligne", "base_de_donnees": "connectée"}
    except HTTPException:
        return JSONResponse(status_code=503, content={"status": "dégradé", "base_de_donnees": "déconnectée"})


##############################################
import httpx

ASSISTANT_URL = os.getenv("ASSISTANT_URL", "http://open-webui:8080")
ASSISTANT_API_KEY = os.getenv("ASSISTANT_API_KEY", "")


async def compter_questions():
    headers = {"Authorization": f"Bearer {ASSISTANT_API_KEY}"}
    async with httpx.AsyncClient(timeout=30) as client:
        reponse = await client.get(f"{ASSISTANT_URL}/api/v1/chats/all/db", headers=headers)
        print(f"[compter_questions] status={reponse.status_code} body={reponse.text[:200]}")
        reponse.raise_for_status()
        return len(reponse.json())


@app.get("/api/stats")
async def get_stats():
    """Retourne les statistiques détaillées de Moodle."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Statistiques globales
            cursor.execute("SELECT COUNT(*) as count FROM mdl_user")
            total_utilisateurs = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM mdl_course")
            total_cours = cursor.fetchone()['count']

            # Nouvelles statistiques : Utilisateurs actifs (non supprimés, non suspendus)
            cursor.execute("SELECT COUNT(*) as count FROM mdl_user WHERE deleted = 0 AND suspended = 0")
            utilisateurs_actifs = cursor.fetchone()['count']

            # Nouvelles statistiques : Catégories de cours
            cursor.execute("SELECT COUNT(*) as count FROM mdl_course_categories")
            total_categories = cursor.fetchone()['count']

     ##########
        try:
            questions_total = await compter_questions()
        except httpx.HTTPError as e:
            print(f"[compter_questions] ERREUR: {type(e).__name__}: {e}")
            questions_total = None
    ###########
    
        return {
            "utilisateurs": {
                "total": total_utilisateurs,
                "actifs": utilisateurs_actifs
            },
            "catalogue": {
                "cours_total": total_cours,
                "categories_total": total_categories
            },
            "assistant": {
                "questions_total": questions_total
            }
        }
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Erreur lors de la lecture des tables Moodle. Sont-elles créées ?")
    finally:
        conn.close()

 ###############################       

# "405 Method Not Allowed" nghĩa là: 
# trang web gửi request kiểu POST (gửi dữ liệu lên server để xử lý) tới /api/analyse, 
# nhưng code backend (main.py) chỉ cho phép request kiểu GET (chỉ lấy dữ liệu, không gửi gì)
#  ở endpoint đó → server từ chối, trả lỗi 405.
# @app.get("/api/analyse")
# def analyse_par_ia(): 

@app.api_route("/api/analyse", methods=["GET", "POST"]) # cho phép cả GET và POST để tránh lỗi 405
async def analyse_par_ia():
    stats = await get_stats()
    prompt = (
        "Agis comme un expert pédagogique. Voici les statistiques brutes extraites de notre "
        f"base de données Moodle : {stats}. Rédige un court bilan professionnel de 2 phrases "
        "en français pour le directeur de l'université."
    )

    try:
        response = llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        texte_ia = response.choices[0].message.content
        if not texte_ia:
            raise HTTPException(status_code=502, detail="Le modèle n'a retourné aucune analyse.")

        return {
            "donnees_brutes": stats,
            "rapport_ia": texte_ia.strip()
        }
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"Erreur de génération : {e}")