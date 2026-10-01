# Audit du code — septembre 2026

Relecture de `backend/server.py` et des écrans concernés du frontend.
**Rien n'a pu être exécuté ici** : Python et Node ne sont pas installés sur le poste. Relancez les tests (voir `LANCER-EN-LOCAL.md`) avant tout déploiement.

## Corrigé

| Gravité | Problème | Correction |
|---|---|---|
| Critique | Si la variable `JWT_SECRET` manquait, le serveur signait les sessions avec une valeur écrite dans le code (`racontelle-dev-secret-change-me`). Quiconque lit le code pouvait se connecter à n'importe quel compte. | Le serveur refuse de démarrer sans secret d'au moins 32 caractères. |
| Élevée | Aucune limite de tentatives : mot de passe, code de réinitialisation et code d'invitation pouvaient être essayés en boucle. | Limites par IP et par compte (ex. 10 connexions / 15 min). Réponse `429` au-delà. |
| Élevée | Après une réinitialisation du mot de passe, les anciennes sessions (valables 30 jours) restaient actives, y compris celle d'un éventuel intrus. | Toute session ouverte avant le changement de mot de passe est refusée. |
| Moyenne | N'importe quel membre du cercle pouvait supprimer les photos des souvenirs des autres. | Réservé à l'auteur du souvenir ou au créateur du cercle, comme pour la suppression du souvenir. Boutons masqués dans l'app pour les autres. |
| Moyenne | Les codes d'invitation en attente étaient visibles par tous les membres (il suffit du code pour entrer dans le cercle). | Seul le créateur du cercle les voit. |
| Moyenne | Le lien photo acceptait une session d'un compte désactivé (le lien audio, non). | Même contrôle pour l'audio et les photos. |
| Moyenne | Changement de jour des questions décalé d'une heure en hiver (fuseau fixé à +2 h). | Fuseau `Europe/Paris` réel. |
| Moyenne | Lecture audio : le serveur annonçait les requêtes partielles sans les gérer. Les lecteurs iPhone en ont besoin et peuvent refuser de lire. | Réponses `206` partielles gérées. À vérifier sur un iPhone réel. |
| Faible | Champs sans longueur maximale (profil, retours bêta, titre, code), couleur d'avatar libre. | Limites et format ajoutés. |
| Faible | Un souvenir pouvait être rattaché à une question du jour d'une autre famille, ou à un profil supprimé. | Vérifié côté serveur. |
| Faible | CORS ouvert à tous avec `allow_credentials`. | Credentials désactivés (l'app n'utilise pas de cookies), origines configurables via `ALLOWED_ORIGINS`. |
| Blocage | Le script `preinstall` Emergent empêchait `yarn install` sous Windows. | Retiré de `package.json`. |

## À traiter plus tard (non corrigé)

1. **Session dans l'URL des médias** : l'audio et les photos sont chargés avec `?token=<session de 30 jours>`. Ces URL peuvent finir dans les journaux des serveurs intermédiaires. Amélioration : un jeton court (5 min) dédié aux médias. Cela touche aussi le frontend (album, détail, PDF).
2. **Suppression de compte et de données** : absente. Obligatoire au titre du RGPD avant une ouverture large. Aujourd'hui, les suppressions sont « douces » : les fichiers audio et photo restent dans le stockage.
3. **Consentement CGU** : l'inscription enregistre `accepted: True` sans case à cocher dans l'app.
4. **Mot de passe de 6 caractères minimum** : passer à 8 ou plus (côté serveur et écran d'inscription).
5. **Génération de chapitres sans limite** : chaque clic appelle Claude. Un plafond par cercle et par jour protégerait la facture.
6. **Questions du jour** : deux ouvertures simultanées de l'accueil peuvent créer 6 questions au lieu de 3 (rare). Un index unique réglerait le cas.
7. **Chapitres** : n'importe quel membre peut en supprimer un. À décider : réserver au créateur ?
8. Les limites de tentatives sont gardées en mémoire : elles valent pour **une** instance du serveur, ce qui suffit sur Render Starter.

## Vérifié sans problème
- Isolation entre familles : chaque lecture et écriture filtre sur le cercle de l'utilisateur.
- Mots de passe hachés avec bcrypt, jamais renvoyés par l'API.
- Contrôle du vrai format des fichiers envoyés (signature binaire), tailles limitées.
- E-mails : contenus échappés, contrôle anti-hameçonnage des liens.
- Livre PDF : titres et textes échappés avant l'impression, pas d'injection HTML possible.
- Jeton de session stocké dans le trousseau sécurisé du téléphone (SecureStore).
