# Point d'avancement — 15-16 octobre 2026

## État actuel

| Accès | Serveur | Base de données | État |
|-------|---------|-----------------|------|
| Adresse web Emergent `https://ehpad-recall.preview.emergentagent.com` (donnée à l'EHPAD) | serveur Emergent | base Emergent | fonctionnait le 16/10 au matin ; non modifiée |
| APK Android 1.0.3 (build Expo `2f0909a2`, disponible 13 jours) | Railway | base Railway | connexion vérifiée sur téléphone |

Les deux accès utilisent des bases **séparées** : un compte créé sur l'un n'existe pas sur l'autre.
Pour les testeurs, rester sur **un seul** accès : l'adresse web Emergent, déjà transmise.

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
- **Compte `laracontelle@gmail.com`** absent de la base Railway au 15/10 au soir : l'essai de connexion
  passait par Emergent. À recréer sur Railway si besoin.
- **Emergent écrit directement dans `main`** : ne pas faire « Save to GitHub » depuis Emergent
  après la fusion des PR #2/#3 sans resynchroniser, sinon conflit ou écrasement.
- Mot de passe affiché en clair dans une capture et jeton Expo visible dans le terminal :
  changer le mot de passe, supprimer le jeton sur expo.dev.

## Ne pas faire avant la fin des tests EHPAD

- Arrêter ou modifier le projet Emergent : l'adresse donnée à l'EHPAD en dépend.
- Changer `PASSWORD_RESET_URL` tant que l'EHPAD utilise l'adresse Emergent.
