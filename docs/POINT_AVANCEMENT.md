# Point d'avancement — 16 octobre 2026, 21 h 30

## Prochaine séance : 17/10/2026 (dans cet ordre)

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


## En place et vérifié

| Élément | État | Preuve |
|---------|------|--------|
| Adresse web testeurs `https://ehpad-recall.preview.emergentagent.com` → API Railway | ✅ | `frontend/.env` Emergent corrigé ; connexion `POST /api/auth/login` 200 dans Railway |
| APK 1.0.3 → API Railway | ✅ | connexion 200 à 14:02 et 14:11 |
| Stockage audio Scaleway (bucket `racontelle-care-media`, Paris ; `racontelle-care-audio` créé le 16/10 et inutilisé) | ✅ | PR #3 fusionnée, 5 variables `S3_*` dans Railway, plus de log « stockage objet indisponible » |
| Envoi audio depuis le web | ✅ | fichier présent dans `racontelle-care-media/racontelle-care/` le 16/10 |
| Resend (`no-reply@racontellecare.com`) | ✅ | domaine vérifié |
| Session web conservée au rechargement | ✅ | PR #5 + #6 (cookie `SameSite=None; Partitioned`), testé sur Android le 16/10 après le déploiement `8d500032` |

## En cours au moment du départ

1. Déconnexion au rechargement : **résolu** (voir tableau). Non testé sur iPhone/Safari.
2. **APK 1.0.4** (PR #4 fusionnée : envoi audio Android via `uploadAsync`) — **non installé** au 16/10 21 h 26 (téléphone en 1.0.3, 3 souvenirs en attente).
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
