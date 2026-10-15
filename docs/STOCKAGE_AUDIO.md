# Racontelle Care — Stockage des enregistrements audio

Les fichiers audio sont conservés dans un stockage objet **compatible S3**.
L'API est la seule à y accéder : les téléphones et le site n'ont jamais la clé.
Le stockage S3 est utilisé dès que `S3_BUCKET` est renseigné ; sinon l'API retombe
sur l'ancien stockage Emergent (inutilisable en dehors d'Emergent).

## Fournisseur recommandé : Scaleway Object Storage (Paris)

Données hébergées en France, facturation au volume (quelques centimes par Go et par mois).

1. Créer un compte sur https://console.scaleway.com.
2. **Object Storage → Create bucket** : nom `racontelle-audio` (ou autre nom libre),
   région **Paris (fr-par)**, visibilité **Private**.
3. **IAM → API keys → Generate an API key** : choisir l'usage *Object Storage*.
   Noter l'**Access Key** et la **Secret Key** (affichée une seule fois).
4. Railway → service **API** → **Variables** :

| Variable | Valeur |
|----------|--------|
| `S3_BUCKET` | `racontelle-audio` |
| `S3_ENDPOINT` | `https://s3.fr-par.scw.cloud` |
| `S3_REGION` | `fr-par` |
| `S3_ACCESS_KEY_ID` | l'Access Key |
| `S3_SECRET_ACCESS_KEY` | la Secret Key |

5. Après le redéploiement, les **Deploy Logs** ne doivent plus afficher
   `stockage objet indisponible au démarrage`.

Autres fournisseurs compatibles : Cloudflare R2 (`S3_ENDPOINT=https://<compte>.r2.cloudflarestorage.com`,
`S3_REGION=auto`), Railway Buckets (reprendre l'endpoint, la région et les clés fournis par Railway).

## Vérifier

Enregistrer un court souvenir depuis l'application, puis le réécouter depuis un autre
appareil connecté au même établissement : il doit être lu depuis le serveur. Le fichier
apparaît dans le bucket sous `racontelle-care/…`.
