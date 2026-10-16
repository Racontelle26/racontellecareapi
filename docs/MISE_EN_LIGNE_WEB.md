# Racontelle Care — Version web sur app.racontellecare.com

La version web est un **second service Railway**, distinct de l'API. Il compile
l'application Expo en site statique (`frontend/Dockerfile`) et le sert avec Caddy
(`frontend/Caddyfile`). L'API reste sur `racontellecareapi-production.up.railway.app`.

| Élément | Valeur |
|---------|--------|
| Adresse publique | `https://app.racontellecare.com` |
| Dossier du service | `/frontend` |
| Fichier de configuration Railway | `/frontend/railway.json` |
| API appelée | `https://racontellecareapi-production.up.railway.app` (fixée à la compilation) |

## 1. Créer le service web sur Railway

1. Ouvrir le projet Railway qui contient déjà l'API.
2. **+ Create** → **GitHub Repo** → `Racontelle26/racontellecareapi`.
3. Ouvrir le nouveau service → **Settings** :
   - **Source → Root Directory** : `/frontend`
   - **Config-as-code → Railway Config File** : `/frontend/railway.json`
   - Renommer le service, par exemple `racontelle-web`.
4. Lancer le déploiement (**Deploy**). La compilation dure 5 à 10 minutes.
5. **Settings → Networking → Generate Domain** pour obtenir une adresse de test
   `….up.railway.app` et vérifier que l'écran de connexion s'affiche.

Aucune variable n'est nécessaire sur ce service : Railway fournit `PORT`.

## 2. Brancher le domaine app.racontellecare.com

1. Service web → **Settings → Networking → Custom Domain** → `app.racontellecare.com`.
2. Railway affiche un enregistrement **CNAME** (cible `….up.railway.app`) et parfois
   un enregistrement **TXT** de vérification.
3. Sur Gandi → **Nom de domaine → racontellecare.com → Enregistrements DNS → Ajouter** :
   - Type **CNAME**, Nom `app`, Nom d'hôte = la cible Railway **suivie d'un point**.
   - Si Railway le demande : Type **TXT**, nom et valeur exactement comme affichés.
4. Ne modifier aucun autre enregistrement (messagerie Gandi, Resend, `www`).
5. Railway passe le domaine en vert et émet le certificat HTTPS (quelques minutes).

## 3. Autoriser la nouvelle adresse côté API

Service **API** Railway → **Variables** :

| Variable | Valeur |
|----------|--------|
| `CORS_ORIGINS` | ajouter `https://app.racontellecare.com` aux valeurs existantes, séparées par des virgules, sans espace ni `/` final |
| `PASSWORD_RESET_URL` | `https://app.racontellecare.com` |

Sans `CORS_ORIGINS`, le navigateur bloque les appels à l'API (connexion impossible
depuis le site). L'application Android n'est pas concernée par CORS.

## 4. Vérifications

1. `https://app.racontellecare.com` affiche l'écran de connexion (cadenas HTTPS).
2. Connexion avec un compte existant, ouverture d'une fiche résident.
3. Enregistrement audio : le navigateur demande l'accès au micro.
4. « Mot de passe oublié » : le lien de l'email ouvre `app.racontellecare.com` avec
   l'email et le code déjà remplis.

## Mises à jour

Chaque modification fusionnée dans `main` sous `frontend/` redéploie le site
automatiquement. L'ancienne adresse d'aperçu Emergent peut rester active en parallèle.
