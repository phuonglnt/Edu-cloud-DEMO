"""
title: Quota EduCloud
description: Bloque le chat quand le quota de questions de l'abonnement est atteint.
"""

import asyncio

import requests
from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        stats_api_url: str = "http://stats-api:8000"
        moodle_url: str = "http://localhost:8080"

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, __user__: dict = None) -> dict:
        """Appelé avant chaque message envoyé au modèle."""
        # Les administrateurs ne sont pas limités : quiz-api et stats-api
        # appellent l'assistant avec la clé API d'un administrateur.
        if not __user__ or __user__.get("role") == "admin":
            return body

        try:
            # Dans un thread : stats-api rappelle Open WebUI pour compter les
            # questions, il ne faut donc pas bloquer Open WebUI pendant l'appel.
            reponse = await asyncio.to_thread(
                requests.get,
                f"{self.valves.stats_api_url}/api/subscription/{__user__['email']}",
                timeout=10,
            )
            reponse.raise_for_status()
            abonnement = reponse.json()
        except requests.RequestException:
            return body  # stats-api indisponible : on ne bloque pas le chat

        if abonnement["quota_depasse"]:
            raise Exception(
                f"Quota {abonnement['tier']} atteint "
                f"({abonnement['questions_utilisees']}/{abonnement['limite']} questions). "
                f"Pour continuer, passez au niveau supérieur dans Moodle : "
                f"{self.valves.moodle_url}/local/abonnement/index.php"
            )
        return body
