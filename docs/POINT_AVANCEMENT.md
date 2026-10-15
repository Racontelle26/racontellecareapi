# Point d'avancement — 15-16 octobre 2026

## Chronologie (historique Git)

| Période | Web (adresse Emergent) | APK | Serveur et base | Stockage audio |
|---------|------------------------|-----|-----------------|----------------|
| 1er → 7/10 08:48 | serveur Emergent | serveur Emergent (`eas.json`) | Emergent, comptes et souvenirs créés à cette période | Emergent, fonctionnel |
| depuis 7/10 08:48 (commit `db77980` « Backend Railway configuré ») | **Railway** | Emergent (ancien `eas.json`) | Railway : base **neuve**, vide au départ | **non configuré** sur Railway |
| depuis 15/10 (PR #1) | Railway | Railway | Railway | non configuré |

Conséquence : les comptes créés jusqu'au 7/10 (dont `laracontelle@gmail.com`) sont dans la base
Emergent, absente de Railway. D'où « Identifiants incorrects » sur l'adresse web, et l'avertissement
`stockage objet indisponible` dans les logs Railway.

## Deux façons de retrouver l'état du 7/10

1. **Revenir au serveur Emergent** (le plus rapide, retrouve comptes et souvenirs) : remettre
   `EXPO_PUBLIC_BACKEND_URL=https://ehpad-recall.preview.emergentagent.com` dans l'environnement
   frontend d'Emergent, et dans `frontend/eas.json` pour un nouvel APK. Dépend d'Emergent.
2. **Rester sur Railway** (durable) : renseigner le stockage audio (PR #3 ou variables
   `INTEGRATION_PROXY_URL` + `EMERGENT_LLM_KEY`) et transférer la base Emergent vers Railway.

## Fait

- `frontend/eas.json` : l'APK appelle l'API Railway (fusionné dans `main`, PR #1).
- Resend : domaine `racontellecare.com` vérifié (DNS Gandi : DKIM, `send`, `rsend`), clé posée dans Railway.
- Mode d'emploi pour l'EHPAD rédigé (document Claude) ; à compléter : lien d'installation, contact.

## Prêt, en attente de fusion

| PR | Contenu | À faire après fusion |
|----|---------|----------------------|
| #3 `claude/s3-audio-storage` | audios dans un bucket S3 (Scaleway Paris) au lieu du stockage Emergent, absent de Railway | bucket + 5 variables `S3_*` (`docs/STOCKAGE_AUDIO.md`) |
| #2 `claude/web-app-domain` | site `https://app.racontellecare.com` servi par Railway | service web Railway, CNAME `app` chez Gandi, `CORS_ORIGINS` et `PASSWORD_RESET_URL` (`docs/MISE_EN_LIGNE_WEB.md`) |

Ordre : #3, puis #2. Une fois les deux en ligne, web et APK partagent le serveur Railway.

## Problèmes connus

- **Railway sans stockage audio** (log `stockage objet indisponible au démarrage`) : sur l'APK, les
  audios restent seulement sur le téléphone ; transcription et export côté serveur échouent. Corrigé par la PR #3.
- **Compte `laracontelle@gmail.com`** absent de la base Railway : créé avant le 7/10, il est dans la base Emergent.
- **Emergent écrit directement dans `main`** : ne pas faire « Save to GitHub » depuis Emergent
  après la fusion des PR #2/#3 sans resynchroniser, sinon conflit ou écrasement.
- Mot de passe affiché en clair dans une capture et jeton Expo visible dans le terminal :
  changer le mot de passe, supprimer le jeton sur expo.dev.

## Ne pas faire avant la fin des tests EHPAD

- Arrêter ou modifier le projet Emergent : l'adresse donnée à l'EHPAD en dépend.
- Changer `PASSWORD_RESET_URL` tant que l'EHPAD utilise l'adresse Emergent.
