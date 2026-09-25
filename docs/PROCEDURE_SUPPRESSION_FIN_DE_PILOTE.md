# Racontelle Care — Suppression des données et fin de pilote

## 1. Supprimer un souvenir

Administrateur : sur la carte du souvenir → **Supprimer** → confirmer.
- L'audio est effacé du stockage serveur, les liens famille sont révoqués, la fiche est supprimée
  et le fichier est effacé de l'appareil.
- L'action est inscrite au journal (`capsule.delete`).
- Hors connexion, rien n'est effacé : réessayer une fois connecté.

## 2. Départ d'un résident (retrait)

Fiche du résident → **Retirer ou supprimer le profil** (code professionnel demandé) :
1. **Extraire les souvenirs** : un fichier ZIP (audios + liste datée) est généré pour le service.
2. **Retirer le profil** : le profil disparaît de l'application, **les souvenirs restent conservés
   sur le serveur**. Les fichiers audio de la tablette sont effacés **uniquement** s'ils sont tous
   « Sauvegardé » sur le serveur ; sinon le retrait est bloqué jusqu'à l'envoi.

## 3. Demande de suppression RGPD (résident, proche ou représentant)

1. Recevoir et dater la demande (courrier, email, formulaire de l'établissement).
2. Fiche du résident → **Retirer ou supprimer le profil** → **Supprimer définitivement les données** → confirmer.
3. Effet : tous les souvenirs et audios du profil sont effacés du serveur et de la tablette,
   le profil est anonymisé (« Profil supprimé »). Seule la trace de l'opération reste au journal
   (`resident.purge`, nombre de souvenirs effacés).
4. Répondre au demandeur en indiquant la date de l'opération.

## 4. Fin de pilote

À définir **avant** le lancement : durée de conservation des comptes et des capsules de bêta
(cahier des charges §12).

1. Exporter les **indicateurs** (CSV) et les **retours** pour le bilan final.
2. Pour chaque résident : extraire les souvenirs (ZIP) si l'établissement souhaite les conserver.
3. Supprimer définitivement chaque profil (§3) à l'échéance convenue.
4. Désactiver les comptes membres et l'établissement (opération serveur : `disabled: true`
   sur les utilisateurs, `active: false` sur l'établissement).
5. Sur chaque tablette : se déconnecter puis désinstaller l'application (efface les données locales).
6. Conserver le journal d'audit le temps requis par la politique de l'établissement, puis le purger.
