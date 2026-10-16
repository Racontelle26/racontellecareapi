# Point d'avancement — 16 octobre 2026, 14 h 40

## En place et vérifié

| Élément | État | Preuve |
|---------|------|--------|
| Adresse web testeurs `https://ehpad-recall.preview.emergentagent.com` → API Railway | ✅ | `frontend/.env` Emergent corrigé ; connexion `POST /api/auth/login` 200 dans Railway |
| APK 1.0.3 → API Railway | ✅ | connexion 200 à 14:02 et 14:11 |
| Stockage audio Scaleway (bucket `racontelle-care-media`, Paris ; `racontelle-care-audio` créé le 16/10 et inutilisé) | ✅ | PR #3 fusionnée, 5 variables `S3_*` dans Railway, plus de log « stockage objet indisponible » |
| Envoi audio depuis le web | ✅ (à confirmer dans le bucket) | « le souvenir semble partir sur le serveur » |
| Resend (`no-reply@racontellecare.com`) | ✅ | domaine vérifié |
| Session web conservée au rechargement | ✅ | PR #5 + #6 (cookie `SameSite=None; Partitioned`), testé sur Android le 16/10 après le déploiement `8d500032` |

## En cours au moment du départ

1. Déconnexion au rechargement : **résolu** (voir tableau). Non testé sur iPhone/Safari.
2. **APK 1.0.4** (PR #4 fusionnée : envoi audio Android via `uploadAsync`) — build EAS en cours.
   - Vérifier sur expo.dev que le build indique **1.0.4 (5)** ; sinon `git pull` puis relancer.
   - Installer **par-dessus** l'APK 1.0.3, sans désinstaller : le souvenir « en attente d'envoi »
     part au premier lancement. Attendu dans Railway : `POST /api/capsules/…/audio` 200.

## Rappels programmés

- 4 janvier 2027 : fin de l'essai gratuit Scaleway le 14/01/2027 (moyen de paiement).
- 1er octobre 2027 : clé API Scaleway `railway-racontelle` expire le 16/10/2027.

## Points d'attention

- Comptes créés avant le 7/10 : dans l'ancienne base Emergent, absents de Railway.
- Emergent : ne pas faire « Save to GitHub » sans resynchroniser, `main` a reçu les PR #3 à #6.
- PR #2 (`app.racontellecare.com`) : ouverte, non urgente.
