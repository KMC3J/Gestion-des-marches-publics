"""Application web de suivi des marchés publics pour une commune.

Lancement :
    pip install -r requirements.txt
    python database.py --seed   (facultatif : données d'exemple)
    python app.py
"""
import sqlite3

from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    FORMES_PRIX,
    PROCEDURES,
    ROLES,
    STATUTS,
    TYPES_MARCHE,
    get_db,
    init_db,
)

app = Flask(__name__)
app.secret_key = "changez-cette-cle-en-production"


@app.before_request
def exiger_connexion():
    if request.endpoint in (None, "static", "connexion"):
        return None
    if not session.get("user_id"):
        return redirect(url_for("connexion"))
    return None


def est_admin():
    return session.get("role") == "admin"


def admin_requis(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not est_admin():
            flash("Action réservée aux administrateurs.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


def f(val, default=0.0):
    try:
        return float(str(val).replace(",", ".")) if str(val).strip() else default
    except ValueError:
        return default


def i(val, default=0):
    try:
        return int(str(val).strip()) if str(val).strip() else default
    except ValueError:
        return default


def euro(val):
    return f"{(val or 0):,.2f}".replace(",", " ").replace(".", ",")


app.jinja_env.filters["euro"] = euro


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE identifiant = ?", (request.form.get("identifiant", "").strip(),)
        ).fetchone()
        db.close()
        if user and check_password_hash(user["mot_de_passe"], request.form.get("mot_de_passe", "")):
            session["user_id"] = user["id"]
            session["identifiant"] = user["identifiant"]
            session["nom"] = user["nom"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Identifiant ou mot de passe incorrect.", "error")
    return render_template("login.html")


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


@app.route("/mon-compte", methods=["GET", "POST"])
def mon_compte():
    if request.method == "POST":
        actuel = request.form.get("mot_de_passe_actuel", "")
        nouveau = request.form.get("nouveau_mot_de_passe", "")
        confirmation = request.form.get("confirmation", "")
        if nouveau != confirmation:
            flash("La confirmation ne correspond pas au nouveau mot de passe.", "error")
        elif len(nouveau) < 8:
            flash("Le nouveau mot de passe doit contenir au moins 8 caractères.", "error")
        else:
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
            if not check_password_hash(user["mot_de_passe"], actuel):
                db.close()
                flash("Mot de passe actuel incorrect.", "error")
            else:
                db.execute(
                    "UPDATE users SET mot_de_passe = ? WHERE id = ?",
                    (generate_password_hash(nouveau), session["user_id"]),
                )
                db.commit()
                db.close()
                flash("Mot de passe modifié avec succès.", "success")
                return redirect(url_for("dashboard"))
    return render_template("mon-compte.html")


@app.route("/")
def dashboard():
    db = get_db()
    stats = {
        "nb_marches": db.execute("SELECT COUNT(*) FROM marches").fetchone()[0],
        "nb_en_cours": db.execute("SELECT COUNT(*) FROM marches WHERE statut = 'En cours'").fetchone()[0],
        "montant_engage": db.execute("SELECT COALESCE(SUM(montant_ht), 0) FROM marches WHERE statut IN ('En cours', 'Réception provisoire', 'Réception définitive')").fetchone()[0],
        "montant_paye": db.execute("SELECT COALESCE(SUM(montant_ht), 0) FROM paiements").fetchone()[0],
        "retenues_en_cours": db.execute("SELECT COALESCE(SUM(montant - montant_restitue), 0) FROM retenues_garantie").fetchone()[0],
        "avances_en_cours": db.execute("SELECT COALESCE(SUM(montant - montant_rembourse), 0) FROM avances").fetchone()[0],
    }
    marches_recents = db.execute(
        "SELECT * FROM marches ORDER BY date_notification DESC, id DESC LIMIT 6"
    ).fetchall()
    echeances = db.execute(
        "SELECT * FROM marches WHERE date_achevement != '' AND statut = 'En cours' ORDER BY date_achevement ASC LIMIT 6"
    ).fetchall()
    db.close()
    return render_template("dashboard.html", stats=stats, marches_recents=marches_recents, echeances=echeances)


# ---------------------------------------------------------------- Marchés


@app.route("/marches")
def marches_liste():
    db = get_db()
    statut = request.args.get("statut", "")
    recherche = request.args.get("q", "").strip()
    sql = "SELECT * FROM marches WHERE 1=1"
    params = []
    if statut:
        sql += " AND statut = ?"
        params.append(statut)
    if recherche:
        sql += " AND (numero LIKE ? OR objet LIKE ?)"
        params += [f"%{recherche}%", f"%{recherche}%"]
    sql += " ORDER BY date_notification DESC, numero DESC"
    marches = db.execute(sql, params).fetchall()
    db.close()
    return render_template("marches/liste.html", marches=marches, statut=statut, recherche=recherche, statuts=STATUTS)


@app.route("/marches/nouveau", methods=["GET", "POST"])
def marche_nouveau():
    if request.method == "POST":
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO marches (numero, objet, type_marche, procedure, forme_prix, statut, service, lieu, montant_ht, taux_tva, date_notification, date_approbation, date_achevement, duree_mois, indice_reference, valeur_indice_notif, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                request.form.get("numero", "").strip(),
                request.form.get("objet", "").strip(),
                request.form.get("type_marche", ""),
                request.form.get("procedure", ""),
                request.form.get("forme_prix", "Firme"),
                request.form.get("statut", "En préparation"),
                request.form.get("service", "").strip(),
                request.form.get("lieu", "").strip(),
                f(request.form.get("montant_ht")),
                f(request.form.get("taux_tva"), 20),
                request.form.get("date_notification", ""),
                request.form.get("date_approbation", ""),
                request.form.get("date_achevement", ""),
                i(request.form.get("duree_mois")),
                request.form.get("indice_reference", "").strip(),
                f(request.form.get("valeur_indice_notif")),
                request.form.get("notes", "").strip(),
            ),
        )
        conn.commit()
        marche_id = cur.lastrowid
        conn.close()
        flash("Marché créé avec succès.", "success")
        return redirect(url_for("marche_detail", marche_id=marche_id))
    return render_template(
        "marches/formulaire.html",
        marche=None,
        types=TYPES_MARCHE,
        procedures=PROCEDURES,
        formes_prix=FORMES_PRIX,
        statuts=STATUTS,
    )


@app.route("/marches/<int:marche_id>")
def marche_detail(marche_id):
    db = get_db()
    marche = db.execute("SELECT * FROM marches WHERE id = ?", (marche_id,)).fetchone()
    if not marche:
        db.close()
        flash("Marché introuvable.", "error")
        return redirect(url_for("marches_liste"))
    intervenants = db.execute(
        "SELECT iv.*, e.raison_sociale FROM intervenants iv JOIN entreprises e ON e.id = iv.entreprise_id WHERE iv.marche_id = ? ORDER BY CASE iv.role WHEN 'Titulaire' THEN 0 WHEN 'Co-traitant' THEN 1 ELSE 2 END",
        (marche_id,),
    ).fetchall()
    retenues = db.execute("SELECT * FROM retenues_garantie WHERE marche_id = ? ORDER BY date_retenue", (marche_id,)).fetchall()
    avances = db.execute("SELECT * FROM avances WHERE marche_id = ? ORDER BY date_versement", (marche_id,)).fetchall()
    revisions = db.execute("SELECT * FROM revisions_prix WHERE marche_id = ? ORDER BY date_periode", (marche_id,)).fetchall()
    paiements = db.execute("SELECT * FROM paiements WHERE marche_id = ? ORDER BY date_paiement DESC", (marche_id,)).fetchall()
    reconductions = db.execute("SELECT * FROM reconductions WHERE marche_origine_id = ? ORDER BY date_debut", (marche_id,)).fetchall()
    entreprises = db.execute("SELECT * FROM entreprises ORDER BY raison_sociale").fetchall()
    total_paye = db.execute("SELECT COALESCE(SUM(montant_ht), 0) FROM paiements WHERE marche_id = ?", (marche_id,)).fetchone()[0]
    total_revise = db.execute("SELECT COALESCE(SUM(montant_revision), 0) FROM revisions_prix WHERE marche_id = ?", (marche_id,)).fetchone()[0]
    montant_ttc = marche["montant_ht"] * (1 + marche["taux_tva"] / 100)
    db.close()
    return render_template(
        "marches/detail.html",
        marche=marche,
        intervenants=intervenants,
        retenues=retenues,
        avances=avances,
        revisions=revisions,
        paiements=paiements,
        reconductions=reconductions,
        entreprises=entreprises,
        roles=ROLES,
        total_paye=total_paye,
        total_revise=total_revise,
        montant_ttc=montant_ttc,
    )


@app.route("/marches/<int:marche_id>/modifier", methods=["GET", "POST"])
def marche_modifier(marche_id):
    db = get_db()
    if request.method == "POST":
        db.execute(
            "UPDATE marches SET numero=?, objet=?, type_marche=?, procedure=?, forme_prix=?, statut=?, service=?, lieu=?, montant_ht=?, taux_tva=?, date_notification=?, date_approbation=?, date_achevement=?, duree_mois=?, indice_reference=?, valeur_indice_notif=?, notes=? WHERE id=?",
            (
                request.form.get("numero", "").strip(),
                request.form.get("objet", "").strip(),
                request.form.get("type_marche", ""),
                request.form.get("procedure", ""),
                request.form.get("forme_prix", "Firme"),
                request.form.get("statut", "En préparation"),
                request.form.get("service", "").strip(),
                request.form.get("lieu", "").strip(),
                f(request.form.get("montant_ht")),
                f(request.form.get("taux_tva"), 20),
                request.form.get("date_notification", ""),
                request.form.get("date_approbation", ""),
                request.form.get("date_achevement", ""),
                i(request.form.get("duree_mois")),
                request.form.get("indice_reference", "").strip(),
                f(request.form.get("valeur_indice_notif")),
                request.form.get("notes", "").strip(),
                marche_id,
            ),
        )
        db.commit()
        db.close()
        flash("Marché mis à jour.", "success")
        return redirect(url_for("marche_detail", marche_id=marche_id))
    marche = db.execute("SELECT * FROM marches WHERE id = ?", (marche_id,)).fetchone()
    db.close()
    if not marche:
        flash("Marché introuvable.", "error")
        return redirect(url_for("marches_liste"))
    return render_template(
        "marches/formulaire.html",
        marche=marche,
        types=TYPES_MARCHE,
        procedures=PROCEDURES,
        formes_prix=FORMES_PRIX,
        statuts=STATUTS,
    )


@app.route("/marches/<int:marche_id>/supprimer", methods=["POST"])
@admin_requis
def marche_supprimer(marche_id):
    conn = get_db()
    conn.execute("DELETE FROM marches WHERE id = ?", (marche_id,))
    conn.commit()
    conn.close()
    flash("Marché supprimé.", "success")
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Intervenants (titulaires / sous-traitants)


@app.route("/marches/<int:marche_id>/intervenants/ajouter", methods=["POST"])
def intervenant_ajouter(marche_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO intervenants (marche_id, entreprise_id, role, montant_ht, part_pct, date_declaration) VALUES (?,?,?,?,?,?)",
        (
            marche_id,
            i(request.form.get("entreprise_id")),
            request.form.get("role", "Titulaire"),
            f(request.form.get("montant_ht")),
            f(request.form.get("part_pct")),
            request.form.get("date_declaration", ""),
        ),
    )
    conn.commit()
    conn.close()
    flash("Intervenant ajouté au marché.", "success")
    return redirect(url_for("marche_detail", marche_id=marche_id))


@app.route("/intervenants/<int:intervenant_id>/supprimer", methods=["POST"])
@admin_requis
def intervenant_supprimer(intervenant_id):
    conn = get_db()
    row = conn.execute("SELECT marche_id FROM intervenants WHERE id = ?", (intervenant_id,)).fetchone()
    conn.execute("DELETE FROM intervenants WHERE id = ?", (intervenant_id,))
    conn.commit()
    conn.close()
    flash("Intervenant retiré du marché.", "success")
    if row:
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Entreprises


@app.route("/entreprises")
def entreprises_liste():
    db = get_db()
    entreprises = db.execute(
        "SELECT e.*, (SELECT COUNT(*) FROM intervenants iv WHERE iv.entreprise_id = e.id) AS nb_marches FROM entreprises e ORDER BY e.raison_sociale"
    ).fetchall()
    db.close()
    return render_template("entreprises/liste.html", entreprises=entreprises)


@app.route("/entreprises/nouvelle", methods=["GET", "POST"])
def entreprise_nouvelle():
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            "INSERT INTO entreprises (raison_sociale, siret, adresse, cp, ville, email, telephone, notes) VALUES (?,?,?,?,?,?,?,?)",
            tuple(request.form.get(k, "").strip() for k in ("raison_sociale", "siret", "adresse", "cp", "ville", "email", "telephone", "notes")),
        )
        conn.commit()
        conn.close()
        flash("Entreprise créée.", "success")
        return redirect(url_for("entreprises_liste"))
    return render_template("entreprises/formulaire.html", entreprise=None)


@app.route("/entreprises/<int:entreprise_id>/modifier", methods=["GET", "POST"])
def entreprise_modifier(entreprise_id):
    db = get_db()
    if request.method == "POST":
        db.execute(
            "UPDATE entreprises SET raison_sociale=?, siret=?, adresse=?, cp=?, ville=?, email=?, telephone=?, notes=? WHERE id=?",
            tuple(request.form.get(k, "").strip() for k in ("raison_sociale", "siret", "adresse", "cp", "ville", "email", "telephone", "notes")) + (entreprise_id,),
        )
        db.commit()
        db.close()
        flash("Entreprise mise à jour.", "success")
        return redirect(url_for("entreprises_liste"))
    entreprise = db.execute("SELECT * FROM entreprises WHERE id = ?", (entreprise_id,)).fetchone()
    db.close()
    return render_template("entreprises/formulaire.html", entreprise=entreprise)


@app.route("/entreprises/<int:entreprise_id>/supprimer", methods=["POST"])
@admin_requis
def entreprise_supprimer(entreprise_id):
    conn = get_db()
    nb = conn.execute("SELECT COUNT(*) FROM intervenants WHERE entreprise_id = ?", (entreprise_id,)).fetchone()[0]
    if nb:
        conn.close()
        flash("Impossible de supprimer : cette entreprise intervient sur des marchés.", "error")
        return redirect(url_for("entreprises_liste"))
    conn.execute("DELETE FROM entreprises WHERE id = ?", (entreprise_id,))
    conn.commit()
    conn.close()
    flash("Entreprise supprimée.", "success")
    return redirect(url_for("entreprises_liste"))


# ---------------------------------------------------------------- Retenues de garantie


@app.route("/marches/<int:marche_id>/retenues/ajouter", methods=["POST"])
def retenue_ajouter(marche_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO retenues_garantie (marche_id, taux, montant, date_retenue, montant_restitue, date_restitution) VALUES (?,?,?,?,?,?)",
        (marche_id, f(request.form.get("taux"), 5), f(request.form.get("montant")), request.form.get("date_retenue", ""), f(request.form.get("montant_restitue")), request.form.get("date_restitution", "")),
    )
    conn.commit()
    conn.close()
    flash("Retenue de garantie enregistrée.", "success")
    return redirect(url_for("marche_detail", marche_id=marche_id))


@app.route("/retenues/<int:retenue_id>/restituer", methods=["POST"])
def retenue_restituer(retenue_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM retenues_garantie WHERE id = ?", (retenue_id,)).fetchone()
    if row:
        conn.execute(
            "UPDATE retenues_garantie SET montant_restitue = montant, date_restitution = ? WHERE id = ?",
            (request.form.get("date_restitution", ""), retenue_id),
        )
        conn.commit()
        flash("Retenue de garantie restituée.", "success")
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    conn.close()
    return redirect(url_for("marches_liste"))


@app.route("/retenues/<int:retenue_id>/supprimer", methods=["POST"])
@admin_requis
def retenue_supprimer(retenue_id):
    conn = get_db()
    row = conn.execute("SELECT marche_id FROM retenues_garantie WHERE id = ?", (retenue_id,)).fetchone()
    conn.execute("DELETE FROM retenues_garantie WHERE id = ?", (retenue_id,))
    conn.commit()
    conn.close()
    flash("Retenue supprimée.", "success")
    if row:
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Avances


@app.route("/marches/<int:marche_id>/avances/ajouter", methods=["POST"])
def avance_ajouter(marche_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO avances (marche_id, taux, montant, date_versement, nb_echeances, montant_rembourse) VALUES (?,?,?,?,?,?)",
        (marche_id, f(request.form.get("taux"), 10), f(request.form.get("montant")), request.form.get("date_versement", ""), i(request.form.get("nb_echeances")), f(request.form.get("montant_rembourse"))),
    )
    conn.commit()
    conn.close()
    flash("Avance enregistrée.", "success")
    return redirect(url_for("marche_detail", marche_id=marche_id))


@app.route("/avances/<int:avance_id>/supprimer", methods=["POST"])
@admin_requis
def avance_supprimer(avance_id):
    conn = get_db()
    row = conn.execute("SELECT marche_id FROM avances WHERE id = ?", (avance_id,)).fetchone()
    conn.execute("DELETE FROM avances WHERE id = ?", (avance_id,))
    conn.commit()
    conn.close()
    flash("Avance supprimée.", "success")
    if row:
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Révisions de prix


@app.route("/marches/<int:marche_id>/revisions/ajouter", methods=["POST"])
def revision_ajouter(marche_id):
    indice_ref = f(request.form.get("valeur_indice_reference"))
    indice_periode = f(request.form.get("valeur_indice_periode"))
    montant_revisable = f(request.form.get("montant_ht_revisable"))
    revision = montant_revisable * (indice_periode / indice_ref - 1) if indice_ref else 0
    conn = get_db()
    conn.execute(
        "INSERT INTO revisions_prix (marche_id, indice, valeur_indice_reference, date_reference, valeur_indice_periode, date_periode, montant_ht_revisable, montant_revision) VALUES (?,?,?,?,?,?,?,?)",
        (marche_id, request.form.get("indice", "").strip(), indice_ref, request.form.get("date_reference", ""), indice_periode, request.form.get("date_periode", ""), montant_revisable, round(revision, 2)),
    )
    conn.commit()
    conn.close()
    flash(f"Révision de prix enregistrée (variation : {euro(revision)} € HT).", "success")
    return redirect(url_for("marche_detail", marche_id=marche_id))


@app.route("/revisions/<int:revision_id>/supprimer", methods=["POST"])
@admin_requis
def revision_supprimer(revision_id):
    conn = get_db()
    row = conn.execute("SELECT marche_id FROM revisions_prix WHERE id = ?", (revision_id,)).fetchone()
    conn.execute("DELETE FROM revisions_prix WHERE id = ?", (revision_id,))
    conn.commit()
    conn.close()
    flash("Révision supprimée.", "success")
    if row:
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Paiements


@app.route("/marches/<int:marche_id>/paiements/ajouter", methods=["POST"])
def paiement_ajouter(marche_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO paiements (marche_id, date_paiement, montant_ht, libelle) VALUES (?,?,?,?)",
        (marche_id, request.form.get("date_paiement", ""), f(request.form.get("montant_ht")), request.form.get("libelle", "").strip()),
    )
    conn.commit()
    conn.close()
    flash("Paiement enregistré.", "success")
    return redirect(url_for("marche_detail", marche_id=marche_id))


@app.route("/paiements/<int:paiement_id>/supprimer", methods=["POST"])
@admin_requis
def paiement_supprimer(paiement_id):
    conn = get_db()
    row = conn.execute("SELECT marche_id FROM paiements WHERE id = ?", (paiement_id,)).fetchone()
    conn.execute("DELETE FROM paiements WHERE id = ?", (paiement_id,))
    conn.commit()
    conn.close()
    flash("Paiement supprimé.", "success")
    if row:
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Reconductions


@app.route("/marches/<int:marche_id>/reconductions/ajouter", methods=["POST"])
def reconduction_ajouter(marche_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO reconductions (marche_origine_id, numero, date_debut, date_fin, montant_ht, statut, notes) VALUES (?,?,?,?,?,?,?)",
        (marche_id, request.form.get("numero", "").strip(), request.form.get("date_debut", ""), request.form.get("date_fin", ""), f(request.form.get("montant_ht")), request.form.get("statut", "En préparation"), request.form.get("notes", "").strip()),
    )
    conn.commit()
    conn.close()
    flash("Reconduction enregistrée.", "success")
    return redirect(url_for("marche_detail", marche_id=marche_id))


@app.route("/reconductions/<int:reconduction_id>/supprimer", methods=["POST"])
@admin_requis
def reconduction_supprimer(reconduction_id):
    conn = get_db()
    row = conn.execute("SELECT marche_origine_id FROM reconductions WHERE id = ?", (reconduction_id,)).fetchone()
    conn.execute("DELETE FROM reconductions WHERE id = ?", (reconduction_id,))
    conn.commit()
    conn.close()
    flash("Reconduction supprimée.", "success")
    if row:
        return redirect(url_for("marche_detail", marche_id=row["marche_id"]))
    return redirect(url_for("marches_liste"))


# ---------------------------------------------------------------- Utilisateurs (administration)


@app.route("/utilisateurs")
@admin_requis
def utilisateurs_liste():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY identifiant").fetchall()
    db.close()
    return render_template("utilisateurs/liste.html", users=users)


@app.route("/utilisateurs/nouveau", methods=["GET", "POST"])
@admin_requis
def utilisateur_nouveau():
    if request.method == "POST":
        identifiant = request.form.get("identifiant", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")
        if not identifiant or len(mot_de_passe) < 8:
            flash("Identifiant requis et mot de passe de 8 caractères minimum.", "error")
            return render_template("utilisateurs/formulaire.html", user=None)
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (identifiant, nom, mot_de_passe, role) VALUES (?,?,?,?)",
                (identifiant, request.form.get("nom", "").strip(), generate_password_hash(mot_de_passe), request.form.get("role", "agent")),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("Cet identifiant existe déjà.", "error")
            return render_template("utilisateurs/formulaire.html", user=None)
        conn.close()
        flash("Utilisateur créé.", "success")
        return redirect(url_for("utilisateurs_liste"))
    return render_template("utilisateurs/formulaire.html", user=None)


@app.route("/utilisateurs/<int:user_id>/modifier", methods=["GET", "POST"])
@admin_requis
def utilisateur_modifier(user_id):
    db = get_db()
    if request.method == "POST":
        mot_de_passe = request.form.get("mot_de_passe", "")
        db.execute(
            "UPDATE users SET nom = ?, role = ? WHERE id = ?",
            (request.form.get("nom", "").strip(), request.form.get("role", "agent"), user_id),
        )
        if mot_de_passe:
            if len(mot_de_passe) < 8:
                db.close()
                flash("Le mot de passe doit contenir au moins 8 caractères.", "error")
                return redirect(url_for("utilisateur_modifier", user_id=user_id))
            db.execute("UPDATE users SET mot_de_passe = ? WHERE id = ?", (generate_password_hash(mot_de_passe), user_id))
        db.commit()
        db.close()
        flash("Utilisateur mis à jour.", "success")
        return redirect(url_for("utilisateurs_liste"))
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    if not user:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("utilisateurs_liste"))
    return render_template("utilisateurs/formulaire.html", user=user)


@app.route("/utilisateurs/<int:user_id>/supprimer", methods=["POST"])
@admin_requis
def utilisateur_supprimer(user_id):
    if user_id == session.get("user_id"):
        flash("Impossible de supprimer votre propre compte.", "error")
        return redirect(url_for("utilisateurs_liste"))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    nb_admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    if user and user["role"] == "admin" and nb_admins <= 1:
        conn.close()
        flash("Impossible de supprimer le dernier administrateur.", "error")
        return redirect(url_for("utilisateurs_liste"))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("Utilisateur supprimé.", "success")
    return redirect(url_for("utilisateurs_liste"))


# ---------------------------------------------------------------- Export CSV


@app.route("/export/marches.csv")
def export_marches():
    import csv
    import io

    db = get_db()
    marches = db.execute("SELECT * FROM marches ORDER BY numero").fetchall()
    db.close()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Numéro", "Objet", "Type", "Procédure", "Forme de prix", "Statut", "Service", "Lieu", "Montant HT", "TVA %", "Notification", "Approbation", "Achèvement", "Durée (mois)", "Indice", "Notes"])
    for m in marches:
        writer.writerow([m[k] for k in ("numero", "objet", "type_marche", "procedure", "forme_prix", "statut", "service", "lieu", "montant_ht", "taux_tva", "date_notification", "date_approbation", "date_achevement", "duree_mois", "indice_reference", "notes")])
    return app.response_class(
        "\ufeff" + buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=marches.csv"},
    )


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
