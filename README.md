# Suivi des marchés publics

Application web interne pour une commune (~8 500 habitants) : suivi complet des marchés publics, de la notification au solde.

## Fonctionnalités

- **Tableau de bord** : nombre de marchés, montants engagés et payés, retenues de garantie et avances en cours, échéances proches.
- **Marchés** : numéro, objet, type (travaux / fournitures / services), procédure (AO ouvert, restreint, MAPA, marché négocié…), forme de prix (ferme, actualisable, révisable), statut, service, lieu, montant HT, TVA, dates (notification, approbation, achèvement), durée, indice de révision.
- **Titulaires et sous-traitants** : entreprises référencées (SIRET, contact), rôles (titulaire, co-traitant, sous-traitant), montants, parts, date de déclaration de sous-traitance.
- **Retenues de garantie** : taux, montant, date, restitution (avec suivi du solde restant).
- **Révisions de prix** : indice de référence et de période, montant HT révisable, calcul automatique de la variation.
- **Avances** : taux, montant, date de versement, nombre d'échéances, remboursement suivi.
- **Paiements** : situations et décomptes, cumul et reste à payer par marché.
- **Reconductions** : reconductions d'un marché (numéro, période, montant, statut).
- **Import PDF / Word** : création d'un marché à partir d'un document (PDF ou Word .docx) — avis d'attribution, arrêté, lettre de notification — avec lecture automatique du numéro, de l'objet, des montants, des dates, du type et du titulaire, puis vérification avant enregistrement. Le document est conservé dans la fiche du marché (téléchargeable).
- **Authentification** : comptes utilisateurs avec rôles (administrateur / agent), mots de passe hachés, changement de mot de passe personnel.
- **Export CSV** de la liste des marchés (compatible tableur).

## Démarrage

```bash
pip install -r requirements.txt
python database.py --seed   # facultatif : jeu de données d'exemple
python app.py
```

Puis ouvrir http://127.0.0.1:5000 dans le navigateur.

**Première connexion** : identifiant `admin`, mot de passe `mairie2025`. Changez immédiatement ce mot de passe via « Mon compte », puis créez les comptes des agents (menu « Utilisateurs », réservé aux administrateurs).

La base de données SQLite (`marches.db`) est créée automatiquement au premier lancement. Pour la placer ailleurs (sauvegarde réseau, dossier partagé) :

```bash
MP_DB_PATH=/chemin/vers/marches.db python app.py
```

## Mise en service à la mairie

L'application est volontairement simple : un seul petit serveur Python, aucune installation de base de données. Pour un poste unique, `python app.py` suffit. Pour un accès depuis plusieurs postes du réseau interne (poste de la régie, service technique, secrétariat de mairie), modifier dans `app.py` :

```python
app.run(host="0.0.0.0", port=5000)
```

et accéder via `http://<adresse-du-poste>:5000`. Prévoir une sauvegarde régulière du fichier `marches.db` (simple copie du fichier). Changer la `secret_key` dans `app.py`.

## Évolutions prévues (développement progressif)

L'architecture est modulaire pour grandir au fil des besoins :

1. **Lots et tranches** par marché, actes d'engagement.
2. **Échéancier d'avance** détaillé avec rappels.
3. **Alertes automatiques** : fins de marché, restitutions de retenues à relancer.
4. **Statistiques annuelles** (répartition par type, carte des fournisseurs locaux).
5. **Import DEPP / extraction BOAMP**, journal des modifications.
6. **Hébergement sur le serveur de la commune** avec sauvegardes planifiées.

## Importer un marché depuis un PDF ou un Word

Menu « Importer » : choisissez un fichier `.pdf` ou `.docx` (par exemple l'avis d'attribution renvoyé signé, ou la lettre de notification). L'application extrait le texte, pré-remplit le formulaire (numéro type « 2025-… », objet, montant en €, dates jj/mm/aaaa, type de marché, SIRET du titulaire, durée en mois, indice de révision) et vous demande de vérifier avant de créer. Si le SIRET correspond à une entreprise déjà enregistrée, le titulaire est ajouté automatiquement. Le document d'origine reste attaché à la fiche du marché.

## Structure du code

```
app.py               # routes Flask (une section par module métier)
database.py          # schéma SQLite + données d'exemple
templates/           # pages HTML (base, tableau de bord, marchés, entreprises)
static/style.css     # feuille de style (sans dépendance externe)
```

Ajouter un nouveau module = ajouter une table dans `database.py`, une section de routes dans `app.py`, et une section dans `templates/marches/detail.html`.
