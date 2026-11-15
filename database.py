"""Base de données SQLite de l'application de suivi des marchés publics."""
import os
import sqlite3

from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get("MP_DB_PATH", os.path.join(os.path.dirname(__file__), "marches.db"))

TYPES_MARCHE = ["Travaux", "Fournitures", "Services"]
PROCEDURES = [
    "Appel d'offres ouvert",
    "Appel d'offres restreint",
    "Procédure adaptée (MAPA)",
    "Marché négocié",
    "Marché de maîtrise d'œuvre",
    "Accord-cadre",
    "Demande de cotation",
]
FORMES_PRIX = ["Firme", "Firme et actualisable", "Actualisable", "Révisable"]
STATUTS = ["En préparation", "En cours", "Réception provisoire", "Réception définitive", "Soldé", "Résilié"]
ROLES = ["Titulaire", "Co-traitant", "Sous-traitant"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS entreprises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raison_sociale TEXT NOT NULL,
    siret TEXT DEFAULT '',
    adresse TEXT DEFAULT '',
    cp TEXT DEFAULT '',
    ville TEXT DEFAULT '',
    email TEXT DEFAULT '',
    telephone TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS marches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL,
    objet TEXT NOT NULL,
    type_marche TEXT NOT NULL,
    procedure TEXT DEFAULT '',
    forme_prix TEXT DEFAULT 'Firme',
    statut TEXT DEFAULT 'En préparation',
    service TEXT DEFAULT '',
    lieu TEXT DEFAULT '',
    montant_ht REAL DEFAULT 0,
    taux_tva REAL DEFAULT 20,
    date_notification TEXT DEFAULT '',
    date_approbation TEXT DEFAULT '',
    date_achevement TEXT DEFAULT '',
    duree_mois INTEGER DEFAULT 0,
    indice_reference TEXT DEFAULT '',
    valeur_indice_notif REAL DEFAULT 0,
    reconduit_de INTEGER REFERENCES marches(id),
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS intervenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marche_id INTEGER NOT NULL REFERENCES marches(id) ON DELETE CASCADE,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'Titulaire',
    montant_ht REAL DEFAULT 0,
    part_pct REAL DEFAULT 0,
    date_declaration TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS retenues_garantie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marche_id INTEGER NOT NULL REFERENCES marches(id) ON DELETE CASCADE,
    taux REAL DEFAULT 5,
    montant REAL DEFAULT 0,
    date_retenue TEXT DEFAULT '',
    montant_restitue REAL DEFAULT 0,
    date_restitution TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS avances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marche_id INTEGER NOT NULL REFERENCES marches(id) ON DELETE CASCADE,
    taux REAL DEFAULT 10,
    montant REAL DEFAULT 0,
    date_versement TEXT DEFAULT '',
    nb_echeances INTEGER DEFAULT 0,
    montant_rembourse REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS revisions_prix (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marche_id INTEGER NOT NULL REFERENCES marches(id) ON DELETE CASCADE,
    indice TEXT DEFAULT '',
    valeur_indice_reference REAL DEFAULT 0,
    date_reference TEXT DEFAULT '',
    valeur_indice_periode REAL DEFAULT 0,
    date_periode TEXT DEFAULT '',
    montant_ht_revisable REAL DEFAULT 0,
    montant_revision REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS paiements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marche_id INTEGER NOT NULL REFERENCES marches(id) ON DELETE CASCADE,
    date_paiement TEXT DEFAULT '',
    montant_ht REAL DEFAULT 0,
    libelle TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifiant TEXT NOT NULL UNIQUE,
    nom TEXT NOT NULL,
    mot_de_passe TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'agent',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reconductions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marche_origine_id INTEGER NOT NULL REFERENCES marches(id) ON DELETE CASCADE,
    numero TEXT DEFAULT '',
    date_debut TEXT DEFAULT '',
    date_fin TEXT DEFAULT '',
    montant_ht REAL DEFAULT 0,
    statut TEXT DEFAULT 'En préparation',
    notes TEXT DEFAULT ''
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed=False):
    conn = get_db()
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        conn.execute(
            "INSERT INTO users (identifiant, nom, mot_de_passe, role) VALUES (?, ?, ?, 'admin')",
            ("admin", "Administrateur", generate_password_hash("mairie2025")),
        )
    if seed:
        _seed(conn)
    conn.commit()
    conn.close()


def _seed(conn):
    if conn.execute("SELECT COUNT(*) FROM marches").fetchone()[0]:
        return
    entreprises = [
        ("Routier & Travaux SAS", "81234567800012", "3 rue de l'Industrie", "85000", "La Roche-sur-Yon", "contact@routier-travaux.fr", "02 51 00 00 01", ""),
        ("Menuiserie Dupont", "82345678900023", "12 avenue des Ateliers", "85100", "Les Sables-d'Olonne", "dupont@menuiserie85.fr", "02 51 00 00 02", ""),
        ("Nettoyage Océan Services", "83456789000034", "5 rue du Port", "85000", "La Roche-sur-Yon", "contact@nos-cleaning.fr", "02 51 00 00 03", ""),
        ("Bureau d'Études Vert & Co", "84567890100045", "8 place du Marché", "85200", "Fontenay-le-Comte", "etudes@vertco.fr", "02 51 00 00 04", ""),
    ]
    for e in entreprises:
        conn.execute("INSERT INTO entreprises (raison_sociale, siret, adresse, cp, ville, email, telephone, notes) VALUES (?,?,?,?,?,?,?,?)", e)

    marches = [
        ("2025-001", "Réfection de la voirie communale - rue des Écoles", "Travaux", "Procédure adaptée (MAPA)", "Révisable", "En cours", "Services techniques", "Rue des Écoles", 185000, 20, "2025-03-15", "2025-04-02", "2025-10-30", 8, "TP-BTP (2015)", 118.5),
        ("2025-002", "Fourniture de mobilier pour l'école primaire", "Fournitures", "Demande de cotation", "Firme", "Réception provisoire", "Services scolaires", "École primaire", 22400, 20, "2025-05-10", "2025-05-20", "2025-08-15", 3, "", 0),
        ("2025-003", "Nettoyage des bâtiments communaux", "Services", "Appel d'offres ouvert", "Firme et actualisable", "En cours", "Services généraux", "Bâtiments communaux", 96000, 20, "2025-01-02", "2025-01-15", "2026-12-31", 24, "", 0),
        ("2024-014", "Aménagement de la place du bourg", "Travaux", "Appel d'offres ouvert", "Révisable", "Soldé", "Services techniques", "Place du bourg", 310000, 20, "2024-04-01", "2024-04-20", "2025-02-28", 10, "TP-BTP (2015)", 115.2),
    ]
    for m in marches:
        conn.execute(
            "INSERT INTO marches (numero, objet, type_marche, procedure, forme_prix, statut, service, lieu, montant_ht, taux_tva, date_notification, date_approbation, date_achevement, duree_mois, indice_reference, valeur_indice_notif) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            m,
        )

    attributions = [
        (1, 1, "Titulaire", 185000, 100),
        (2, 2, "Titulaire", 22400, 100),
        (3, 3, "Titulaire", 96000, 100),
        (4, 1, "Titulaire", 285000, 90),
        (4, 4, "Co-traitant", 25000, 8),
    ]
    for a in attributions:
        conn.execute("INSERT INTO intervenants (marche_id, entreprise_id, role, montant_ht, part_pct) VALUES (?,?,?,?,?)", a)

    conn.execute("INSERT INTO intervenants (marche_id, entreprise_id, role, montant_ht, part_pct, date_declaration) VALUES (1, 2, 'Sous-traitant', 25000, 13.5, '2025-03-20')")

    conn.execute("INSERT INTO retenues_garantie (marche_id, taux, montant, date_retenue, montant_restitue, date_restitution) VALUES (1, 5, 9250, '2025-06-30', 0, '')")
    conn.execute("INSERT INTO retenues_garantie (marche_id, taux, montant, date_retenue, montant_restitue, date_restitution) VALUES (4, 5, 14250, '2024-12-20', 14250, '2025-12-01')")

    conn.execute("INSERT INTO avances (marche_id, taux, montant, date_versement, nb_echeances, montant_rembourse) VALUES (1, 10, 18500, '2025-04-15', 8, 9250)")
    conn.execute("INSERT INTO avances (marche_id, taux, montant, date_versement, nb_echeances, montant_rembourse) VALUES (3, 15, 14400, '2025-02-01', 24, 6000)")

    conn.execute("INSERT INTO revisions_prix (marche_id, indice, valeur_indice_reference, date_reference, valeur_indice_periode, date_periode, montant_ht_revisable, montant_revision) VALUES (1, 'TP-BTP (2015)', 118.5, '2025-03-15', 121.3, '2025-09-15', 185000, 4370.89)")

    conn.execute("INSERT INTO paiements (marche_id, date_paiement, montant_ht, libelle) VALUES (1, '2025-05-10', 45000, 'Situation n°1')")
    conn.execute("INSERT INTO paiements (marche_id, date_paiement, montant_ht, libelle) VALUES (1, '2025-07-12', 52000, 'Situation n°2')")

    conn.execute("INSERT INTO reconductions (marche_origine_id, numero, date_debut, date_fin, montant_ht, statut, notes) VALUES (3, '2026-003-R1', '2026-01-01', '2026-12-31', 98000, 'En préparation', 'Reconduction annuelle prévue au marché')")


if __name__ == "__main__":
    import sys

    init_db(seed="--seed" in sys.argv)
    print(f"Base initialisée : {DB_PATH}")
