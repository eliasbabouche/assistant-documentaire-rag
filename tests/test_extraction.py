"""Tests du nettoyage de l'extraction, sur de petits textes construits a la main (sans PDF
ni reseau)."""

from src.extraction import lignes_repetees, nettoyer_balisage, retirer_lignes


def test_le_gras_retire_ne_colle_pas_les_mots():
    # Cas reel du referentiel RH : l'espace suivait le gras dans le PDF.
    assert nettoyer_balisage("**5 ans**à compter du départ") == "5 ans à compter du départ"


def test_br_de_cellule_remplace_par_une_espace():
    resultat = nettoyer_balisage("|Registre unique du<br>personnel|")
    assert resultat == "|Registre unique du personnel|"


def test_ponctuation_recollee_apres_le_gras():
    assert nettoyer_balisage("par principe**,** pendant") == "par principe, pendant"


def test_balises_html_retirees_texte_garde():
    texte = "<!-- Start of picture text -->\nVoir l'<u>article 5</u> et le <mark>point</mark>"
    assert nettoyer_balisage(texte) == "Voir l' article 5 et le point"


def test_structure_markdown_conservee():
    texte = "## Titre\n\n|Finalité|Durée|\n|---|---|\n|Paie|5 ans|\n\n- point 1\n  - sous-point"
    assert nettoyer_balisage(texte) == texte


def test_lignes_vides_en_serie_reduites():
    assert nettoyer_balisage("Paragraphe 1\n\n\n\n\nParagraphe 2") == "Paragraphe 1\n\nParagraphe 2"


def page_type(i):
    return (
        "Guide pratique RGPD\n"
        f"Introduction de la page {i}.\n"
        f"Article {i} : une ligne de contenu qui ne differe que par un chiffre.\n"
        f"Conclusion de la page {i}.\n"
        f"Passez à l'action | RGPD | {i}"
    )


def test_pied_de_page_numerote_retire_et_contenu_garde():
    pages = [page_type(i) for i in range(1, 7)]
    repetees = lignes_repetees(pages)
    nettoyee = retirer_lignes(pages[2], repetees)
    assert "Passez à l'action" not in nettoyee
    assert "Guide pratique RGPD" not in nettoyee
    # Repetee sur toutes les pages au chiffre pres, mais au milieu : c'est du contenu.
    assert "Article 3 : une ligne de contenu" in nettoyee


def test_ligne_identique_a_l_en_tete_gardee_au_milieu_de_page():
    pages = [page_type(i) for i in range(1, 7)]
    repetees = lignes_repetees(pages)
    page = "Guide pratique RGPD\nIntro.\nSuite.\nGuide pratique RGPD\nFin.\nAutre.\nPied"
    assert retirer_lignes(page, repetees).count("Guide pratique RGPD") == 1


def test_en_tete_de_tableau_repete_conserve():
    pages = [f"|Finalité|Durée|\n|---|---|\n|Cas {i}|{i} ans|" for i in range(1, 7)]
    assert lignes_repetees(pages) == set()


def test_pas_de_detection_sur_un_document_trop_court():
    pages = ["CNIL.\nTexte A", "CNIL.\nTexte B", "CNIL.\nTexte C"]
    assert lignes_repetees(pages) == set()
