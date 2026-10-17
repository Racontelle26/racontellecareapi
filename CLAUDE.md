# Racontelle Care — mémoire du projet

Application d'atelier mémoire en EHPAD : enregistrement des souvenirs racontés par les
résidents. Propriétaire : Racontelle (GitHub `Racontelle26`). Répondre en français, simplement,
sans condescendance : l'utilisatrice n'est pas développeuse et veut des étapes courtes et sûres.
État détaillé et historique : `docs/POINT_AVANCEMENT.md`. Produit : `memory/PRD.md`.

## À faire le 17/10/2026 (dans cet ordre)

1. **APK 1.0.4** — le téléphone a encore la 1.0.3 (3 souvenirs « en attente d'envoi » le 16/10 à 21 h 26).
   - expo.dev → Builds : chercher un build **1.0.4 (5)** terminé. Sinon :
     `cd $HOME\racontellecareapi\frontend` → `git pull` → `npx eas-cli build --platform android --profile preview`.
   - Installer **par-dessus** la 1.0.3, sans désinstaller ni effacer les données.
   - Vérifier : bandeau « Tout est sauvegardé », 3 lignes `POST /api/capsules/…/audio 200` dans Railway
     (déploiement Active → Network Logs), fichiers dans `racontelle-care-media/racontelle-care/`.
   - Si l'envoi échoue encore en 1.0.4 : relever le code HTTP de `/audio` dans Railway avant toute autre action.
2. **Mot de passe oublié** : tester une vraie réception d'email (Resend) depuis l'adresse web testeurs.
3. **Mode d'emploi EHPAD** (document Claude) : y mettre le lien d'installation du build 1.0.4 et le contact, puis l'envoyer.
4. Si un testeur a un iPhone : vérifier que la session web tient au rechargement (Safari).
5. Plus tard, sans urgence : PR #2 (`app.racontellecare.com`) + domaine `api.racontellecare.com` ;
   supprimer le bucket vide `racontelle-care-audio` ; décider du sort des comptes d'avant le 7/10 (base Emergent).

Rappel permanent : avant tout « Save to GitHub » depuis Emergent, lui faire récupérer `main` (PR #1 à #7 fusionnées).

## Architecture en production (au 16/10/2026)

| Élément | Où | Détail |
|---------|----|--------|
| API FastAPI | Railway, projet `vivacious-unity`, service `racontellecareapi`, EU West | `https://racontellecareapi-production.up.railway.app`, `Dockerfile` racine, redéploie à chaque fusion dans `main` |
| Base MongoDB | Railway | base neuve depuis le 7/10 ; les comptes d'avant le 7/10 sont dans l'ancienne base Emergent |
| Audios | Scaleway Object Storage, organisation « Racontelle », bucket **`racontelle-care-media`**, `fr-par` | variables `S3_*` ; clé API `railway-racontelle` (expire ~16/10/2027) ; `racontelle-care-audio` vide, inutilisé |
| Site web testeurs | aperçu Emergent `https://ehpad-recall.preview.emergentagent.com` | servi par Emergent depuis sa propre copie du frontend ; `frontend/.env` Emergent : `EXPO_PUBLIC_BACKEND_URL` = API Railway |
| APK Android | EAS (compte Expo `laracontelle`, projet `racontelle-care`), profil `preview` | `frontend/eas.json` → API Railway ; 1.0.4 (versionCode 5) = envoi audio corrigé |
| Emails | Resend, `no-reply@racontellecare.com` | domaine vérifié via DNS Gandi (DKIM `resend._domainkey`, CNAME `send`, `rsend`) |
| Domaine | Gandi, `racontellecare.com` | ne pas toucher aux enregistrements messagerie Gandi existants |

Variables Railway attendues (noms seulement) : `MONGO_URL`, `DB_NAME`, `JWT_*`, `CORS_ORIGINS`,
`CORS_PROXY_ORIGIN`, `CORS_PUBLIC_ORIGIN`, `S3_BUCKET`, `S3_ENDPOINT`, `S3_REGION`,
`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`,
`PASSWORD_RESET_URL`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`. Ne jamais écrire de valeur secrète
dans le dépôt.

## Pièges déjà rencontrés (ne pas les refaire)

- **Emergent écrit directement dans `main`** et garde sa propre copie. Avant tout « Save to GitHub »
  depuis Emergent, lui faire récupérer `main`. Ne jamais « forcer le push » depuis Emergent sans avoir
  comparé sa branche à `main` : cela effacerait les PR fusionnées sur GitHub.
- **Expo SDK 57** remplace `fetch` par `expo/fetch`, qui refuse les parties FormData `{ uri, name, type }`.
  Envoi de fichiers sur mobile : `FileSystem.uploadAsync` (`frontend/src/api.ts`, `uploadNativeFile`).
- **Site et API sur deux sites différents** : le cookie de session web doit être
  `SameSite=None; Secure; HttpOnly; Partitioned` (`backend/security.py`, `_set_refresh_cookie`),
  sinon déconnexion à chaque rechargement. Non testé sur Safari/iPhone. Solution durable :
  `app.racontellecare.com` (PR #2) + domaine `api.racontellecare.com` sur Railway.
- **Web, écran verrouillé** : le navigateur coupe le micro (fichier de 26 s pour un compteur à 4 min le 17/10).
  Depuis la PR #9, l'enregistrement web s'arrête proprement quand la page est cachée et garde ce qui
  a été capté. Consigne atelier : désactiver la mise en veille automatique de l'écran.
  Le site testeurs est servi par Emergent : un changement du frontend n'y arrive qu'après
  « git pull » de `main` + redémarrage du frontend côté Emergent.
- Les journaux d'un déploiement Railway s'arrêtent quand il est remplacé : toujours ouvrir le
  déploiement **Active** le plus récent (Deployments → View logs → Network Logs).
- Sur mobile, un souvenir reste « en attente d'envoi » tant que `POST /api/capsules/{id}/audio`
  n'a pas répondu 200 ; l'envoi est retenté à l'ouverture, au retour au premier plan et après chaque
  sauvegarde. Ne jamais faire désinstaller l'APK : les audios en attente sont sur le téléphone.

## Commandes

- Tests backend (sans service externe) : `cd backend && python -m pytest tests_local -q -n 0`
- Frontend : `cd frontend && yarn install --frozen-lockfile && npx tsc --noEmit && npx expo lint`
- APK : `cd frontend && git pull && npx eas-cli build --platform android --profile preview`
  (incrémenter `version` et `android.versionCode` dans `app.json` pour installer par-dessus).

## Rappels programmés (scheduled tasks Claude)

- 4/01/2027 : fin de l'essai gratuit Scaleway le 14/01/2027 (moyen de paiement).
- 1/10/2027 : remplacer la clé Scaleway `railway-racontelle` (expire ~16/10/2027).
