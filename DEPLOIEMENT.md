# Déployer Racontelle hors Emergent

## L'hébergement recommandé

| Brique | Service | Pourquoi | Coût indicatif (bêta) |
|---|---|---|---|
| API (FastAPI) | **Render**, région Francfort | Déploiement depuis GitHub, HTTPS automatique, pas de serveur à maintenir. Fichier `render.yaml` prêt | 7 $/mois (Starter, toujours allumé) |
| Base de données | **MongoDB Atlas**, région Paris ou Francfort | Aucune modification du code (déjà MongoDB), sauvegardes gérées | 0 € (M0) pour la bêta, puis Flex ~8–30 $/mois |
| Voix et photos | **Cloudflare R2**, juridiction UE | Compatible S3, **aucun frais de sortie** (l'écoute des souvenirs ne coûte rien) | 0 € jusqu'à 10 Go |
| E-mails | **Resend**, région UE | Même service qu'Emergent utilisait en coulisse | 0 € jusqu'à 3 000 e-mails/mois |
| Livre romancé | **API Anthropic** (Claude Sonnet 5) | Même modèle qu'aujourd'hui | Quelques centimes par chapitre |
| Transcription | **API OpenAI** (Whisper), facultatif | Sans clé, la saisie/dictée manuelle du texte reste disponible | ~0,006 $/minute d'audio |
| Application mobile | **Expo EAS Build** | Produit l'APK Android et la version iOS (TestFlight) sans Mac | 0 € (offre gratuite) |

**Total bêta : environ 7 à 15 € par mois.** Les données des familles (voix, photos, textes) restent hébergées en Europe.

Pourquoi pas un VPS ? Moins cher (~5 €/mois), mais il faut gérer soi-même les mises à jour de sécurité, les sauvegardes MongoDB et le certificat HTTPS. Pour une bêta portée par une personne, un service géré est plus sûr.

## Étapes

### 1. Mettre le code sur GitHub
Créez un dépôt **privé** et envoyez-y le dossier `Racontelle-Famille-main`. Vérifiez qu'aucun fichier `.env` n'y figure : le `.gitignore` les exclut déjà.

### 2. MongoDB Atlas
1. cloud.mongodb.com → créer un cluster **M0**, fournisseur AWS, région **Paris (eu-west-3)** ou Francfort.
2. *Database Access* → créer un utilisateur avec un mot de passe fort.
3. *Network Access* → `0.0.0.0/0` (Render n'a pas d'IP fixe sur l'offre Starter).
4. *Connect → Drivers* → copier l'URL `mongodb+srv://…` : c'est `MONGO_URL`.

Pour reprendre les données de la bêta Emergent, faites un `mongodump` depuis Emergent puis un `mongorestore` vers Atlas. Les fichiers audio et photo doivent aussi être copiés dans R2 **en gardant les mêmes chemins** (`racontelle-family/uploads/…`, `racontelle-family/photos/…`).

### 3. Cloudflare R2
1. dash.cloudflare.com → R2 → *Create bucket* `racontelle-souvenirs`, *Location* : **European Union**.
2. *Manage R2 API Tokens* → jeton « Object Read & Write » limité à ce bucket.
3. Notez l'*Access Key ID*, le *Secret* et l'endpoint `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`.

Laissez le bucket **privé** : l'API sert les fichiers après vérification de l'appartenance au cercle.

### 4. Resend
1. resend.com → *Domains* → ajoutez votre domaine (ex. `racontelle.fr`), région **EU**, puis ajoutez les enregistrements DNS (SPF, DKIM) indiqués.
2. *API Keys* → créez une clé « Sending access ».
3. `EMAIL_FROM_ADDRESS` = une adresse de ce domaine (ex. `bonjour@racontelle.fr`).

### 5. Clés IA
- console.anthropic.com → *API Keys* → `ANTHROPIC_API_KEY`. Fixez une limite de dépense mensuelle.
- (facultatif) platform.openai.com → `OPENAI_API_KEY`, avec une limite de dépense.

### 6. Render
1. render.com → *New → Blueprint* → choisissez le dépôt GitHub. Render lit `render.yaml`.
2. Renseignez les variables demandées (liste complète dans `backend/.env.example`). `JWT_SECRET` est généré automatiquement.
3. Une fois déployé, vérifiez `https://racontelle-api.onrender.com/api/` → `status: ok`.
4. (Conseillé) *Settings → Custom Domain* → `api.racontelle.fr`, puis mettez cette adresse dans `APP_PUBLIC_URL`.

### 7. Application mobile (EAS)
```powershell
cd frontend
npm install -g eas-cli
eas login
eas init
```
1. Dans `eas.json`, remplacez `https://api.racontelle.fr` par l'adresse réelle de l'API.
2. **Avant la première publication sur les stores**, remplacez dans `app.json` les identifiants `com.emergent.familystories.ubz2aq` par les vôtres (ex. `fr.racontelle.famille`), et `slug`/`scheme` par `racontelle`. Changer l'identifiant crée une nouvelle application : les testeurs devront installer la nouvelle version.
3. Bêta Android : `eas build --profile beta --platform android` → lien de téléchargement de l'APK à envoyer aux testeurs.
4. Bêta iOS : compte Apple Developer (99 $/an), puis `eas build --profile production --platform ios` et `eas submit -p ios` → TestFlight.

## Avant d'ouvrir aux familles (RGPD)
Les voix et souvenirs de famille sont des données personnelles, et la voix peut être une donnée sensible. Minimum à prévoir :
- une politique de confidentialité et des CGU affichées **et acceptées** à l'inscription (aujourd'hui l'app enregistre un consentement sans case à cocher) ;
- une procédure de suppression de compte et de données (pas encore dans l'app) ;
- les contrats de sous-traitance (DPA) de Render, MongoDB, Cloudflare, Resend, Anthropic et OpenAI (disponibles sur leurs sites) ;
- un registre des traitements.
