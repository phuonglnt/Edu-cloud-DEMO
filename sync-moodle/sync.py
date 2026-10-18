"""
sync-moodle — envoie les fichiers de cours de Moodle vers Open WebUI.

Pour chaque cours Moodle, le service cree une base de connaissances du meme nom
dans Open WebUI, puis y depose les fichiers PDF du cours. L'enseignant n'a donc
rien a faire de plus : il depose ses supports dans Moodle comme d'habitude.
"""

import os
import time

import httpx
import psycopg

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("DB_NAME", "moodle")
DB_USER = os.getenv("DB_USER", "moodle")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

ASSISTANT_URL = os.getenv("ASSISTANT_URL", "http://open-webui:8080")
ASSISTANT_API_KEY = os.getenv("ASSISTANT_API_KEY", "")

MOODLE_DATA = os.getenv("MOODLE_DATA", "/moodledata")
INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))

HEADERS = {"Authorization": f"Bearer {ASSISTANT_API_KEY}"}

# Les fichiers deposes dans un cours sont rattaches a un module (contextlevel 70),
# pas directement au cours. Il faut donc passer par mdl_course_modules.
REQUETE = """
SELECT DISTINCT c.fullname, f.filename, f.contenthash
FROM mdl_files f
JOIN mdl_context ctx ON f.contextid = ctx.id
JOIN mdl_course_modules cm ON ctx.instanceid = cm.id
JOIN mdl_course c ON cm.course = c.id
WHERE f.filename <> '.'
  AND f.mimetype = 'application/pdf'
  AND ctx.contextlevel = 70
"""


def log(message):
    print(f"[sync-moodle] {message}", flush=True)


def fichiers_moodle():
    """Liste les PDF deposes dans les cours, avec le nom du cours."""
    with psycopg.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    ) as conn:
        return conn.execute(REQUETE).fetchall()


def chemin_fichier(contenthash):
    """Moodle range ses fichiers par hash : filedir/xx/yy/hash complet."""
    return os.path.join(MOODLE_DATA, "filedir", contenthash[:2], contenthash[2:4], contenthash)


def bases_existantes(client):
    reponse = client.get(f"{ASSISTANT_URL}/api/v1/knowledge/", headers=HEADERS)
    reponse.raise_for_status()
    donnees = reponse.json()
    if isinstance(donnees, dict):
        return donnees.get("items", [])
    return donnees


def creer_base(client, nom):
    reponse = client.post(
        f"{ASSISTANT_URL}/api/v1/knowledge/create",
        headers=HEADERS,
        json={"name": nom, "description": f"Supports du cours {nom}"},
    )
    reponse.raise_for_status()
    log(f"base de connaissances creee : {nom}")
    return reponse.json()


def televerser(client, chemin, nom_fichier):
    with open(chemin, "rb") as f:
        reponse = client.post(
            f"{ASSISTANT_URL}/api/v1/files/",
            headers=HEADERS,
            files={"file": (nom_fichier, f, "application/pdf")},
        )
    reponse.raise_for_status()
    return reponse.json()["id"]


def attendre_traitement(client, file_id, essais=30):
    """Open WebUI extrait le texte du fichier en arriere-plan.
    Tant que le statut est 'pending', le rattachement echoue."""
    for _ in range(essais):
        reponse = client.get(f"{ASSISTANT_URL}/api/v1/files/{file_id}", headers=HEADERS)
        reponse.raise_for_status()
        statut = (reponse.json().get("data") or {}).get("status")
        if statut != "pending":
            return statut
        time.sleep(2)
    return "pending"


def rattacher(client, base_id, file_id):
    reponse = client.post(
        f"{ASSISTANT_URL}/api/v1/knowledge/{base_id}/file/add",
        headers=HEADERS,
        json={"file_id": file_id},
    )
    reponse.raise_for_status()


def synchroniser():
    with httpx.Client(timeout=180) as client:
        bases = {b["name"]: b for b in bases_existantes(client)}

        for cours, nom_fichier, contenthash in fichiers_moodle():
            base = bases.get(cours)
            if base is None:
                base = creer_base(client, cours)
                bases[cours] = base

            deja_presents = {f["meta"]["name"] for f in (base.get("files") or [])}
            if nom_fichier in deja_presents:
                continue

            chemin = chemin_fichier(contenthash)
            if not os.path.exists(chemin):
                log(f"fichier introuvable sur le disque : {nom_fichier}")
                continue

            try:
                file_id = televerser(client, chemin, nom_fichier)
                statut = attendre_traitement(client, file_id)
                if statut == "pending":
                    log(f"traitement trop long pour {nom_fichier}, nouvel essai au prochain cycle")
                    continue
                rattacher(client, base["id"], file_id)
                log(f"{cours} <- {nom_fichier}")
            except httpx.HTTPStatusError as e:
                log(f"echec pour {nom_fichier} : {e.response.status_code} {e.response.text[:200]}")
                continue

            # La base vient de changer : on la relit pour la prochaine boucle.
            bases = {b["name"]: b for b in bases_existantes(client)}


def main():
    if not ASSISTANT_API_KEY:
        log("ASSISTANT_API_KEY n'est pas configuree, arret.")
        return

    log(f"demarrage, synchronisation toutes les {INTERVAL} secondes")
    while True:
        try:
            synchroniser()
        except Exception as e:
            log(f"erreur : {type(e).__name__} {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
