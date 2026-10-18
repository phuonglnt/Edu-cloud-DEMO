#!/bin/sh
set -e

# Installe la base de Moodle et cree le compte administrateur.
# A lancer une seule fois, apres "docker compose up -d".

if [ ! -f .env ]; then
  echo "Fichier .env introuvable. Copiez .env.example vers .env et remplissez-le."
  exit 1
fi

. ./.env

echo "Attente du demarrage de PostgreSQL..."
sleep 10

docker compose exec -u root moodle php /var/www/html/admin/cli/install_database.php \
  --agree-license \
  --adminuser="${MOODLE_ADMIN_USER}" \
  --adminpass="${MOODLE_ADMIN_PASSWORD}" \
  --adminemail="${MOODLE_ADMIN_EMAIL}" \
  --fullname="EduCloud" \
  --shortname="educloud"

echo ""
echo "Installation terminee."
echo "Moodle : http://localhost:8080"
echo "Compte : ${MOODLE_ADMIN_USER}"
