# Racontelle Care — Version de test Android

La version de test est un fichier **APK** installé directement sur les téléphones des
testeurs (sans passer par le Play Store). Il est fabriqué par **EAS Build**, le service de
compilation d'Expo : aucun outil Android n'est nécessaire sur l'ordinateur.

| Élément | Valeur |
|---------|--------|
| Identifiant Android | `fr.racontelle.care` (définitif) |
| Version | 1.0.0 (versionCode 1) |
| Profil de compilation | `preview` → APK, distribution interne |
| Autorisations | micro, internet, lecture audio ; caméra et écriture du stockage retirées |
| Configuration | `frontend/app.json`, `frontend/eas.json` |

## 1. Redéployer le serveur (Emergent)

L'application de test a besoin du **nouveau serveur** (questions par thème, quiz, réglages,
retours, mot de passe oublié). L'ancien serveur ne suffit pas.

1. Remplacer le code du projet Emergent par le contenu de `Racontelle-care-v2-beta.zip`
   (dossier `backend/` au minimum). Aucune nouvelle dépendance Python n'est nécessaire.
2. Redémarrer le serveur. Au démarrage, il charge les 400 questions automatiquement.
3. Facultatif : renseigner `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
   pour l'envoi des codes « Mot de passe oublié ».
4. Noter l'adresse publique du serveur (`https://…`), sans `/api` à la fin.

## 2. Renseigner l'adresse du serveur

Dans `frontend/eas.json`, remplacer `ADRESSE_DU_SERVEUR_A_RENSEIGNER` par cette adresse
(profils `preview` et `production`).

## 3. Se connecter à Expo (une seule fois)

Créer un compte gratuit sur https://expo.dev, puis dans un terminal, dossier `frontend` :

```bash
npx eas-cli login
```

## 4. Lancer la compilation

Toujours dans le dossier `frontend` (sous Windows PowerShell) :

```bash
$env:EAS_NO_VCS="1"; npx eas-cli build --platform android --profile preview
```

- La première fois, EAS propose de créer le projet Expo et une **clé de signature** Android :
  répondre **Oui** (la clé est conservée par Expo ; elle devra rester la même pour les mises à jour).
- La compilation dure en général 10 à 20 minutes. À la fin, EAS affiche un **lien** et un
  **QR code** vers l'APK.

## 5. Installer sur les téléphones

1. Sur le téléphone Android, ouvrir le lien (ou scanner le QR code) et télécharger l'APK.
2. Autoriser l'installation depuis le navigateur quand Android le demande
   (« Sources inconnues » / « Installer des applications inconnues »).
3. Ouvrir Racontelle Care, se connecter, autoriser le micro à la première demande.

## 6. À vérifier en priorité sur le téléphone

- [ ] Enregistrer un souvenir guidé de plus de 5 minutes, avec pause et reprise
- [ ] Réécouter, recommencer, sauvegarder
- [ ] Passer en mode avion, enregistrer, voir « En attente d'envoi », rétablir le réseau, voir « Sauvegardé »
- [ ] Refuser le micro une fois, vérifier le message, puis l'autoriser dans les réglages
- [ ] Ajouter une photo de profil

## Nouvelle version de test

Augmenter `versionCode` (2, 3…) et `version` dans `frontend/app.json`, puis relancer l'étape 4.
Les téléphones installent la nouvelle version par-dessus l'ancienne (même clé de signature).
