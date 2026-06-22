"""
Tutor — base de dades pedagògica.

Un problema disponible: IC-001 (interval de confiança). L'alumne el
treballa des de l'inici de la sessió.

Estructura:
  PROBLEMS:           dict[str, dict] — registry indexat per id del
                      problema. Cada entrada conté:
                        "id":            id del problema
                        "title_human":   etiqueta breu per al picker UI
                        "problem":       dict amb id/tema/enunciat/passos
                        "prerequisites": dict de prerequisits (PRE-*)
                        "dependencies":  dict de dependències conceptuals
                        "error_catalog": dict d'errors típics
                        "prereq_id":     id del prerequisit únic
  DEFAULT_PROBLEM_ID: id per defecte per a back-compat (tests, scripts
                      que accedeixen als noms globals PROBLEM, etc.).
  get(problem_id):    retorna el bundle per a aquest id.
  list_ids():         retorna [(id, title_human), ...] per al picker.

Per a codi que encara depèn dels noms globals (PROBLEM, PREREQUISITES,
DEPENDENCIES, ERROR_CATALOG), aquests apunten al problema per defecte
(IC-001) per back-compat. Codi nou hauria d'usar PB.get(problem_id).
"""

# =============================================================================
# IC-001 — Interpretació d'un interval de confiança
# =============================================================================

_IC001_ERROR_CATALOG = {
    "INT_prob_param": (
        "Atribueix probabilitat al paràmetre poblacional. "
        "Tracta μ com si fos una variable aleatòria."
    ),
    "INT_prob_sample": (
        "Confon l'IC amb una afirmació sobre futures mostres."
    ),
    "KEY_only": (
        "Resposta-keyword: conté un terme correcte (constant, fix, "
        "paràmetre, confiança, repetició, procediment...) però no el "
        "justifica ni l'aplica a la pregunta concreta. Cal desenvolupar "
        "el raonament: explicar QUÈ vol dir el terme en aquest context "
        "i PER QUÈ respon la pregunta."
    ),
    "GEN_other": "Error no catalogat.",
}

_IC001_DEPENDENCIES = {
    "param_vs_stat": {
        "description": (
            "Diferència entre paràmetre poblacional (μ, fix, "
            "desconegut) i estadístic mostral (x̄, aleatori)."
        ),
        "keywords": ["fix", "fixa", "fixe", "constant", "paràmetre",
                     "aleatori", "aleatòri", "varia", "no aleatori"],
        "prerequisite": "PRE-PARAM",
    },
}

_IC001_PREREQUISITES = {
    "PRE-PARAM": {
        "id": "PRE-PARAM",
        "concept": "param_vs_stat",
        "question": (
            "Quina diferència hi ha entre μ (la mitjana poblacional) i "
            "x̄ (la mitjana d'una mostra concreta)? "
            "Quina de les dues és aleatòria i quina és fixa?"
        ),
        "keywords_required": ["fix", "fixa", "fixe", "constant",
                              "paràmetre", "no aleatori"],
        "forbidden_keywords": ["μ és aleatòria", "mu és aleatòria",
                               "μ és aleatòri", "mu és aleatòri"],
        "explanation": (
            """**μ és un paràmetre poblacional**: un nombre fix, desconegut, però **no aleatori**.
**x̄ és un estadístic mostral**: varia d'una mostra a una altra, és **aleatori**.

La inferència freqüentista fa afirmacions probabilístiques sobre x̄ (i els intervals construïts a partir de x̄), però no sobre μ."""
        ),
    },
}

_IC001_PROBLEM = {
    "id": "IC-001",
    "tema": "Interpretació d'un interval de confiança",
    "enunciat": (
        """S'ha fet una recerca per estimar quantes hores al dia estudien, durant l'època d'exàmens, els estudiants de primer curs d'un Grau universitari. La població d'interès són aproximadament 250 estudiants.
A partir d'una mostra aleatòria de 44 estudiants obtenim:
  - Mitjana mostral: x̄ = 4,0 hores/dia
  - Desviació estàndard estimada: σ ≈ 2,7 hores

S'obté un interval de confiança del 95% per a la mitjana (μ):

  [3,2 ; 4,8] hores/dia"""
    ),
    "dependencies": ["param_vs_stat"],
    "passos": [
        {
            "id": 1,
            "text": (
                """Explica, amb les teves paraules, com interpretes l'interval següent que té una confiança del 95%:

[3,2 ; 4,8] hores/dia, per a la mitjana μ d'hores d'estudi diari."""
            ),
            "expected_summary": (
                "El 95% és una propietat del procediment: si "
                "repetíssim el procés amb moltes mostres diferents, "
                "el 95% dels intervals construïts contindrien μ. "
                "És una afirmació sobre intervals (que sí són "
                "aleatoris perquè depenen de la mostra), NO sobre μ."
            ),
            "typical_error": (
                "Dir que hi ha un 95% de probabilitat que μ "
                "estigui entre 3,2 i 4,8 (atribuir probabilitat al "
                "paràmetre poblacional)."
            ),
            "typical_error_label": "INT_prob_param",
            "key_concepts": ["param_vs_stat"],
            "canonical_question": (
                """Explica, amb les teves paraules, com interpretes l'interval següent que té una confiança del 95%:

[3,2 ; 4,8] hores/dia, per a la mitjana μ d'hores d'estudi diari."""
            ),
            "pistes": [
                """La mitjana mostral i l'interval que en surt canviarien si repetíssim l'estudi; en canvi, la mitjana (μ) no canviaria.""",
                "El 95% és una propietat del *procediment*: de tots els "
                "intervals que construiríem repetint el mostreig, el 95% "
                "contindrien μ. No és una afirmació sobre μ.",
            ],
        },
        {
            "id": 2,
            "text": (
                """Imagina que algú diu:
«Hi ha una probabilitat del 95% que la mitjana real (μ) estigui entre 3,2h/dia i 4,8h/dia».

Per què aquesta frase és incorrecta?"""
            ),
            "expected_summary": (
                "Perquè μ és un paràmetre fix, no una variable "
                "aleatòria. Un cop l'interval [3,2; 4,8] està "
                "calculat, μ hi és o no hi és — no té sentit parlar "
                "de probabilitat sobre un fet ja determinat. "
                "L'aleatorietat era a la mostra (i a l'interval "
                "construït a partir d'ella), no al paràmetre."
            ),
            "typical_error": (
                "Justificar-ho parlant de mostres futures, o "
                "no veure que un cop construït l'interval ja "
                "no queda aleatorietat residual."
            ),
            "typical_error_label": "INT_prob_param",
            "key_concepts": ["param_vs_stat"],
            "canonical_question": (
                """Imagina que algú diu:
«Hi ha una probabilitat del 95% que la mitjana real (μ) estigui entre 3,2h/dia i 4,8h/dia».

Per què aquesta frase és incorrecta?"""
            ),
            "pistes": [
                "Què té de diferent μ respecte de la mostra? Una de les "
                "dues coses és aleatòria i l'altra no.",
                "Un cop l'interval [3,2 ; 4,8] ja està calculat, μ hi és "
                "o no hi és. No té sentit parlar de probabilitat sobre un "
                "fet ja determinat: l'aleatorietat era a la mostra.",
            ],
        },
        {
            "id": 3,
            "text": (
                """Per acabar, explica amb les teves paraules com interpretes l'interval [3,2 ; 4,8] hores/dia, per a la mitjana μ d'hores d'estudi diari."""
            ),
            "expected_summary": (
                "Tenim una *confiança* del 95% que μ estigui dins "
                "de [3,2; 4,8], entenent 'confiança' com la "
                "fiabilitat a llarg termini del procediment: si "
                "repetíssim moltes vegades, el 95% dels intervals "
                "construïts d'aquesta manera contindrien μ. "
                "Per a aquest interval concret no podem parlar de "
                "probabilitat."
            ),
            "typical_error": (
                "Tornar a dir 'probabilitat del 95%' encara que "
                "estigui demanant una formulació correcta."
            ),
            "typical_error_label": "INT_prob_param",
            "key_concepts": ["param_vs_stat"],
            "canonical_question": (
                """Per acabar, explica amb les teves paraules com interpretes l'interval [3,2 ; 4,8] hores/dia, per a la mitjana μ d'hores d'estudi diari."""
            ),
            "pistes": [
                "Comença la frase amb «Tenim una confiança del 95%...» en "
                "lloc de «la probabilitat...». El canvi de paraula no és "
                "cosmètic: és el cor del concepte.",
                "'Confiança' aquí vol dir la fiabilitat a llarg termini "
                "del procediment: si el repetíssim moltes vegades, el 95% "
                "dels intervals construïts contindrien μ.",
            ],
        },
    ],
}


# =============================================================================
# Registry públic
# =============================================================================

PROBLEMS = {
    "IC-001": {
        "id": "IC-001",
        "title_human": "Interval de confiança",
        "problem": _IC001_PROBLEM,
        "prerequisites": _IC001_PREREQUISITES,
        "dependencies": _IC001_DEPENDENCIES,
        "error_catalog": _IC001_ERROR_CATALOG,
        "prereq_id": "PRE-PARAM",
    },
}

# Problema usat per defecte quan no se n'especifica cap (tests,
# back-compat dels accessos globals). Ara IC-001 és l'únic problema
# disponible i, per tant, el default; canviar aquest valor només
# afecta el default, no els tests que demanen explícitament un problema.
DEFAULT_PROBLEM_ID = "IC-001"


def get(problem_id):
    """Retorna el bundle complet per a un problem_id.

    Llança KeyError amb un missatge informatiu si l'id no existeix.
    """
    if problem_id not in PROBLEMS:
        raise KeyError(
            f"Problema desconegut: {problem_id!r}. "
            f"Disponibles: {sorted(PROBLEMS)}"
        )
    return PROBLEMS[problem_id]


def list_ids():
    """Retorna [(id, title_human), ...] per construir el picker UI.

    L'ordre és el d'inserció al dict (en Python 3.7+). Actualment
    només hi ha IC-001.
    """
    return [(pid, bundle["title_human"]) for pid, bundle in PROBLEMS.items()]


# =============================================================================
# Accessors per a la capa determinista (Python posa preguntes i pistes)
# =============================================================================
# Aquests helpers donen a la màquina d'estats (simulator.py / app.py) accés
# directe a la pregunta canònica i a les pistes pre-escrites de cada pas,
# sense que el model les hagi de redactar. És el suport del transvasament
# Tier 1 (Python garanteix l'enunciat del pas) i Tier 3 (pistes amb control).

def _step_by_id(problem_id, step_num):
    """Retorna el dict del pas `step_num` (1-based) del problema indicat."""
    passos = PROBLEMS[problem_id]["problem"]["passos"]
    if not (1 <= step_num <= len(passos)):
        raise IndexError(
            f"Pas {step_num} fora de rang per a {problem_id} "
            f"(té {len(passos)} passos)."
        )
    return passos[step_num - 1]


def canonical_question(problem_id, step_num):
    """Pregunta canònica curta del pas `step_num` (1-based) d'un problema.

    És l'àncora determinista que Python injecta quan el tutor avança: així
    l'enunciat del pas següent sempre apareix, encara que el model no
    l'escrigui (o l'escrigui malament). Si un pas no defineix
    `canonical_question` explícitament, caiem al seu camp `text` complet.
    """
    paso = _step_by_id(problem_id, step_num)
    return paso.get("canonical_question") or paso["text"]


def step_hints(problem_id, step_num):
    """Llista de pistes progressives pre-escrites del pas (pot ser buida)."""
    return list(_step_by_id(problem_id, step_num).get("pistes", []))


def prereq_question(problem_id):
    """Pregunta canònica del prerequisit del problema (per al retrocés)."""
    bundle = PROBLEMS[problem_id]
    return bundle["prerequisites"][bundle["prereq_id"]]["question"]


# =============================================================================
# Accessors del catàleg d'errors (Tasca 4: el control block diagnostica)
# =============================================================================
# El `diagnostic` que retorna el model nomena la MALENTESA conceptual en curs
# fent servir un codi del catàleg d'errors del problema. Aquests helpers
# exposen els codis i les seves descripcions a la capa LLM (per injectar-los
# al position marker del pas actual) i al caller (per validar i normalitzar el
# codi rebut). El catàleg sempre conté `GEN_other` com a calaix de sastre.

# Codi que es retorna quan el model no diagnostica res (alumne encertant /
# acció d'avançar) o quan el codi rebut no encaixa al catàleg del pas.
GEN_OTHER = "GEN_other"


def error_catalog(problem_id):
    """Catàleg d'errors del problema: {codi: descripció}."""
    return PROBLEMS[problem_id].get("error_catalog", {})


def allowed_diagnostics(problem_id, step_num=None):
    """Codis de diagnòstic vàlids per al pas indicat (o per a tot el
    problema si step_num és None).

    Estratègia: oferim al model el catàleg sencer del problema com a opcions
    (els catàlegs són curts i els codis són transversals als passos), i a més
    destaquem el `typical_error_label` del pas actual com a candidat probable.
    Sempre s'hi inclou `GEN_other`. La validació final (codi rebut → catàleg)
    la fa el caller; aquí només enumerem el que és acceptable.

    Retorna una llista de codis (strings), amb `GEN_other` garantit al final.
    """
    catalog = error_catalog(problem_id)
    codes = [c for c in catalog.keys() if c != GEN_OTHER]
    if GEN_OTHER not in codes:
        codes.append(GEN_OTHER)
    return codes


def likely_diagnostic_for_step(problem_id, step_num):
    """`typical_error_label` del pas (codi més probable), o None si no en té
    o el pas no existeix. Pur ajut per pista/prompt; mai obligatori."""
    try:
        paso = _step_by_id(problem_id, step_num)
    except (IndexError, KeyError, TypeError):
        return None
    return paso.get("typical_error_label")


def normalize_diagnostic(problem_id, step_num, code):
    """Normalitza un codi de diagnòstic rebut del model.

    - None / "" / no-string → None (cap diagnòstic).
    - codi del catàleg del problema → es retorna tal qual.
    - codi desconegut → GEN_other (l'spec: out-of-catalog → GEN_other).

    Aquesta funció és el punt únic de validació del caller. El parser de
    llm.py es manté "ximple" i no valida contra el catàleg.
    """
    if not isinstance(code, str):
        return None
    code = code.strip()
    if not code or code.lower() == "null":
        return None
    catalog = error_catalog(problem_id)
    if code in catalog:
        return code
    return GEN_OTHER


def hint_for_diagnostic(problem_id, step_num, code):
    """Pista mapejada a un codi de diagnòstic, si el pas en defineix via
    `pistes_per_error: {codi: pista}`. Si no n'hi ha cap per al codi, retorna
    None i el caller cau a la pista per defecte (`step_hints(...)[0]`)."""
    if not code:
        return None
    try:
        paso = _step_by_id(problem_id, step_num)
    except (IndexError, KeyError, TypeError):
        return None
    mapping = paso.get("pistes_per_error") or {}
    return mapping.get(code)


# =============================================================================
# Back-compat: noms globals apuntant al problema per defecte
# =============================================================================
# Codi antic que accedeix directament a PB.PROBLEM (per exemple, tests
# heretats) continua funcionant sense canvis. Codi nou hauria d'usar
# PB.get(problem_id) per ser explícit sobre quin problema treballa.

PROBLEM = PROBLEMS[DEFAULT_PROBLEM_ID]["problem"]
PREREQUISITES = PROBLEMS[DEFAULT_PROBLEM_ID]["prerequisites"]
DEPENDENCIES = PROBLEMS[DEFAULT_PROBLEM_ID]["dependencies"]
ERROR_CATALOG = PROBLEMS[DEFAULT_PROBLEM_ID]["error_catalog"]


# =============================================================================
# Validació d'invariants al càrrega del mòdul
# =============================================================================
# Aquestes comprovacions detecten errors a la base de dades pedagògica
# tan aviat com s'importa el mòdul, en comptes de fallar a runtime
# enmig d'una sessió. Si fallen, és que algú ha trencat l'esquema en
# editar un problema.

for _pid, _bundle in PROBLEMS.items():
    assert _bundle["id"] == _pid, f"Mismatch id/clau a {_pid}"
    assert len(_bundle["problem"]["passos"]) == 3, (
        f"{_pid} ha de tenir exactament 3 passos (té {len(_bundle['problem']['passos'])})"
    )
    assert _bundle["prereq_id"] in _bundle["prerequisites"], (
        f"prereq_id {_bundle['prereq_id']} no existeix a prerequisites de {_pid}"
    )
    _dep_keys = list(_bundle["dependencies"].keys())
    assert _bundle["problem"]["dependencies"] == _dep_keys[:len(_bundle["problem"]["dependencies"])], (
        f"problem['dependencies'] no coincideix amb DEPENDENCIES a {_pid}"
    )
    for _paso in _bundle["problem"]["passos"]:
        assert _paso["typical_error_label"] in _bundle["error_catalog"], (
            f"typical_error_label {_paso['typical_error_label']} de {_pid} "
            f"no existeix a ERROR_CATALOG"
        )
        for _kc in _paso["key_concepts"]:
            assert _kc in _bundle["dependencies"], (
                f"key_concept {_kc} de {_pid} no existeix a DEPENDENCIES"
            )

del _pid, _bundle, _dep_keys, _paso, _kc
