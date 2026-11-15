import os
import time
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

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


#######################
# Gestion des quotas d'utilisation de l'assistant IA

LIMITES_QUOTA = {"FREE": 5, "GOLD": 50, "PLATINUM": None} 
ORDRE_TIERS = ["FREE", "GOLD", "PLATINUM"]

# Les tiers sont stockés dans PostgreSQL : l'état est ainsi partagé entre
# tous les réplicas Swarm de stats-api.
@app.on_event("startup")
def creer_tables():
    for tentative in range(30):  # PostgreSQL peut démarrer après l'API
        try:
            conn = get_db_connection()
            break
        except HTTPException:
            if tentative == 29:
                raise
            time.sleep(2)
    try:
        with conn.transaction(), conn.cursor() as cursor:
            # Verrou : évite que deux réplicas créent les tables en même temps
            cursor.execute("SELECT pg_advisory_xact_lock(20261115)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS abonnement (
                    user_id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paiement (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    statut TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")
    finally:
        conn.close()

def get_tier(user_id: str) -> str:
    """Tier de l'utilisateur ; "FREE" s'il n'a pas d'abonnement."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT tier FROM abonnement WHERE user_id = %s", (user_id.lower(),))
            ligne = cursor.fetchone()
            return ligne["tier"] if ligne else "FREE"
    except psycopg.Error as e:
        raise HTTPException(status_code=503, detail=f"Base de données indisponible: {e}")
    finally:
        conn.close()

def quota_depasse(user_id: str, nb_questions: int) -> bool:
    tier = get_tier(user_id)
    limite = LIMITES_QUOTA[tier]
    if limite is None:
        return False
    return nb_questions >= limite

#######################
async def compter_questions():
    headers = {"Authorization": f"Bearer {ASSISTANT_API_KEY}"}
    async with httpx.AsyncClient(timeout=30) as client:
        reponse = await client.get(f"{ASSISTANT_URL}/api/v1/chats/all/db", headers=headers)
        reponse.raise_for_status()
        chats = reponse.json()

         # Noms des utilisateurs (si la route échoue, on garde les identifiants)
        noms = {}
        emails = {}
        try:
            r = await client.get(f"{ASSISTANT_URL}/api/v1/users/all", headers=headers)
            r.raise_for_status()
            d = r.json()
            users = d.get("users", d) if isinstance(d, dict) else d
            noms = {u["id"]: u.get("name") or u.get("email") or u["id"] for u in users}
            emails = {u["id"]: u["email"].lower() for u in users if u.get("email")}
        except (httpx.HTTPError, KeyError, TypeError):
            pass

        par_utilisateur = {}
        par_email = {}
        email_par_nom = {}
        total = 0
        for chat in chats:
            uid = chat.get("user_id", "inconnu")
            messages = chat.get("chat", {}).get("history", {}).get("messages", {})
            nb_questions = sum(1 for m in messages.values() if m.get("role") == "user")
            nom = noms.get(uid, uid)
            par_utilisateur[nom] = par_utilisateur.get(nom, 0) + nb_questions
            if uid in emails:
                par_email[emails[uid]] = par_email.get(emails[uid], 0) + nb_questions
                email_par_nom[nom] = emails[uid]
            total += nb_questions

        return {"total": total, "par_utilisateur": par_utilisateur, "par_email": par_email,
                "email_par_nom": email_par_nom}

async def questions_utilisees(user_id: str) -> int:
    """Questions posées à l'assistant par cet utilisateur.

    user_id est l'e-mail du compte Moodle : il est rapproché de l'e-mail du
    compte Open WebUI (à défaut, du nom affiché dans Open WebUI).
    """
    try:
        questions = await compter_questions()
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Assistant IA indisponible : quota impossible à vérifier.")
    par_email = questions["par_email"]
    if user_id.lower() in par_email:
        return par_email[user_id.lower()]
    return questions["par_utilisateur"].get(user_id, 0)
########################

@app.get("/api/stats")
async def get_stats():
    """Retourne les statistiques détaillées de Moodle."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Statistiques globales
            cursor.execute("SELECT COUNT(*) as count FROM mdl_user")
            total_utilisateurs = cursor.fetchone()['count']
            # Nouvelles statistiques : Cours visibles (id > 1 pour exclure le cours "Site principal")
            cursor.execute("SELECT COUNT(*) as count FROM mdl_course WHERE id > 1 AND visible = 1")
            total_cours = cursor.fetchone()['count']

            # Nouvelles statistiques : Utilisateurs actifs (non supprimés, non suspendus)
            cursor.execute("SELECT COUNT(*) as count FROM mdl_user WHERE deleted = 0 AND suspended = 0")
            utilisateurs_actifs = cursor.fetchone()['count']

            # Nouvelles statistiques : Catégories de cours
            cursor.execute("SELECT COUNT(*) as count FROM mdl_course_categories")
            total_categories = cursor.fetchone()['count']

     ##########
        try:
            questions = await compter_questions()
            questions_total = questions["total"]
            questions_par_utilisateur = questions["par_utilisateur"]
            # Tier et quota de chaque utilisateur (abonnement rattaché par e-mail)
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id, tier FROM abonnement")
                tiers = {ligne["user_id"]: ligne["tier"] for ligne in cursor.fetchall()}
            abonnement_par_utilisateur = {}
            for nom in questions_par_utilisateur:
                tier = tiers.get(questions["email_par_nom"].get(nom, nom.lower()), "FREE")
                abonnement_par_utilisateur[nom] = {"tier": tier, "limite": LIMITES_QUOTA[tier]}
        except httpx.HTTPError as e:
            print(f"[compter_questions] ERREUR: {type(e).__name__}: {e}")
            questions_total = None
            questions_par_utilisateur = None
            abonnement_par_utilisateur = None
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
                "questions_total": questions_total,
                "questions_par_utilisateur": questions_par_utilisateur,
                "abonnement_par_utilisateur": abonnement_par_utilisateur
            }
        }
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Erreur lors de la lecture des tables Moodle. Sont-elles créées ?")
    finally:
        conn.close()

@app.get("/api/subscription/{user_id}")
async def get_subscription(user_id: str):
    nb_questions = await questions_utilisees(user_id)
    tier = get_tier(user_id)
    limite = LIMITES_QUOTA[tier]
    return {
        "user_id": user_id,
        "tier": tier,
        "questions_utilisees": nb_questions,
        "limite": limite,
        "quota_depasse": quota_depasse(user_id, nb_questions)
    }


#######################
# Paiement simulé : seul moyen de changer de tier

CARTE_ACCEPTEE = "4242424242424242"  # toute autre carte est refusée (ex. 4000000000000002)

class DemandeUpgrade(BaseModel):
    user_id: str
    tier: str
    carte: str

@app.post("/api/upgrade")
def upgrade(demande: DemandeUpgrade):
    user_id = demande.user_id.strip().lower()
    tier = demande.tier.strip().upper()
    if not user_id:
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant.")
    if tier not in ("GOLD", "PLATINUM"):
        raise HTTPException(status_code=400, detail="Tier invalide : choisissez GOLD ou PLATINUM.")

    accepte = demande.carte.replace(" ", "") == CARTE_ACCEPTEE
    conn = get_db_connection()
    try:
        with conn.transaction(), conn.cursor() as cursor:
            # Sérialise les paiements d'un même utilisateur entre réplicas
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (user_id,))
            cursor.execute("SELECT tier FROM abonnement WHERE user_id = %s", (user_id,))
            ligne = cursor.fetchone()
            tier_actuel = ligne["tier"] if ligne else "FREE"
            if ORDRE_TIERS.index(tier) <= ORDRE_TIERS.index(tier_actuel):
                raise HTTPException(
                    status_code=400,
                    detail=f"Vous êtes déjà au niveau {tier_actuel} : choisissez un niveau supérieur.",
                )
            # Le numéro de carte n'est jamais enregistré
            cursor.execute(
                "INSERT INTO paiement (user_id, tier, statut) VALUES (%s, %s, %s)",
                (user_id, tier, "ACCEPTE" if accepte else "REFUSE"),
            )
            if accepte:
                cursor.execute(
                    """INSERT INTO abonnement (user_id, tier) VALUES (%s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET tier = EXCLUDED.tier, updated_at = now()""",
                    (user_id, tier),
                )
    except psycopg.Error as e:
        raise HTTPException(status_code=503, detail=f"Base de données indisponible: {e}")
    finally:
        conn.close()

    if not accepte:
        raise HTTPException(status_code=402, detail=f"Paiement refusé. Votre abonnement reste {tier_actuel}.")
    return {"user_id": user_id, "tier": tier, "statut": "ACCEPTE"}

 ###############################       

# "405 Method Not Allowed" nghĩa là: 
# trang web gửi request kiểu POST (gửi dữ liệu lên server để xử lý) tới /api/analyse, 
# nhưng code backend (main.py) chỉ cho phép request kiểu GET (chỉ lấy dữ liệu, không gửi gì)
#  ở endpoint đó → server từ chối, trả lỗi 405.
# @app.get("/api/analyse")
# def analyse_par_ia(): 

@app.api_route("/api/analyse", methods=["GET", "POST"])
async def analyse_par_ia(user_id: str = "demo-admin"):
    stats = await get_stats()
    nb_questions = await questions_utilisees(user_id)
    if quota_depasse(user_id, nb_questions):
        raise HTTPException(
            status_code=403,
            detail=f"Quota {get_tier(user_id)} atteint ({nb_questions}/{LIMITES_QUOTA[get_tier(user_id)]} questions). Veuillez passer au niveau supérieur."
        )
    
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

        import re
        texte_ia = re.sub(r"<thought>.*?</thought>", "", texte_ia, flags=re.DOTALL).strip()
        return {
            "donnees_brutes": stats,
            "rapport_ia": texte_ia.strip()
        }
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"Erreur de génération : {e}")