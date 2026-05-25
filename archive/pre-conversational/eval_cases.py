"""
Casos d'avaluació per al tutor-ic.

Cada cas és una predicció a priori sobre el comportament esperat del
classificador `llm.judge_step`. L'eval runner executa cada cas i
compara el veredicte real amb l'esperat.

Categories de cas (per cada pas):
  CORR — Resposta canònica o variant clarament correcta
  TYP  — Error típic catalogat (l'error clàssic d'atribuir
         probabilitat a μ, o variants reconeixibles)
  KEY  — Resposta-keyword (típicament breu): conté el mot pertinent
         però no el justifica ni l'aplica. Categoria descoberta
         durant el stress test de sessió en directe.
  GAP  — Buit conceptual genuí (l'alumne no té els fonaments)

Convenció d'id: S{step}-{categoria}-{seq}

Quan `expected_error_label` és None, el runner NO verifica l'etiqueta;
només el veredicte. Quan és una cadena concreta, també es verifica.
"""

CASES = [
    # ============================================================
    # PAS 1 — Interpretació freqüentista del 95%
    # ============================================================

    # ---- CORRECT (els 4 canònics donats a priori) ----
    {
        "id": "S1-CORR-01",
        "step_id": 1,
        "input": (
            "Si repetíssim l'experiment moltes vegades i cada cop "
            "calculéssim un interval del 95%, aproximadament 95 de "
            "cada 100 d'aquests intervals contindrien la veritable μ."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "directe", "freqüentista"],
    },
    {
        "id": "S1-CORR-02",
        "step_id": 1,
        "input": (
            "Imagina que 100 investigadors diferents fan el mateix "
            "estudi amb mostres independents. Uns 95 dels seus "
            "intervals capturaran μ; els altres 5 tindran mala sort i no."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "narratiu"],
    },
    {
        "id": "S1-CORR-03",
        "step_id": 1,
        "input": (
            "El 95% no descriu aquest interval concret, sinó el "
            "procediment: és un mètode que, a llarg termini, encerta "
            "95 vegades de cada 100."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "tècnic"],
    },
    {
        "id": "S1-CORR-04",
        "step_id": 1,
        "input": (
            "Pensem-ho com un pescador que llança una xarxa "
            "dissenyada per capturar el peix el 95% de les vegades. "
            "No sabem si ara l'ha capturat, però sabem que la xarxa és bona."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "metàfora"],
    },

    # ---- TYPICAL_ERROR — l'error clàssic d'Aran ----
    {
        "id": "S1-TYP-01",
        "step_id": 1,
        "input": (
            "Hi ha un 95% de probabilitat que la mitjana poblacional "
            "μ estigui entre 3,2 i 4,8."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": "INT_prob_param",
        "tags": ["aran-classic", "directe"],
    },
    {
        "id": "S1-TYP-02",
        "step_id": 1,
        "input": (
            "El 95% és la probabilitat que μ caigui dins de "
            "l'interval que hem calculat."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": "INT_prob_param",
        "tags": ["aran-classic", "parafrasi"],
    },
    {
        "id": "S1-TYP-03",
        "step_id": 1,
        "input": (
            "Estem segurs al 95% que el paràmetre vertader és "
            "entre 3,2 i 4,8."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": "INT_prob_param",
        "tags": ["aran-classic", "informal"],
    },
    {
        "id": "S1-TYP-04",
        "step_id": 1,
        "input": (
            "El 95% es refereix a la probabilitat que en futures "
            "mostres la mitjana mostral caigui dins d'aquest interval."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,  # podria ser INT_prob_sample
        "tags": ["confusió-mostres-futures"],
    },

    # ---- KEY_only — descoberta del stress test ----
    {
        "id": "S1-KEY-01",
        "step_id": 1,
        "input": "si repetim el mostreig moltes vegades",
        "expected_verdict": "typical_error",
        "expected_error_label": "KEY_only",
        "tags": ["keyword-only", "incomplet", "discovered-in-stress-test"],
    },
    {
        "id": "S1-KEY-02",
        "step_id": 1,
        "input": "es refereix al procediment",
        "expected_verdict": "typical_error",
        "expected_error_label": "KEY_only",
        "tags": ["keyword-only", "no-aplica"],
    },

    # ---- CONCEPTUAL_GAP — sense fonament conceptual ----
    {
        "id": "S1-GAP-01",
        "step_id": 1,
        "input": "no entenc què és μ ni què és un interval de confiança",
        "expected_verdict": "conceptual_gap",
        "expected_error_label": None,
        "tags": ["explicit-no-sap"],
    },
    {
        "id": "S1-GAP-02",
        "step_id": 1,
        "input": (
            "el 95 és perquè la mostra té 95 elements de mitjana o "
            "alguna cosa així, no n'estic segur"
        ),
        "expected_verdict": "conceptual_gap",
        "expected_error_label": None,
        "tags": ["desorientació-greu"],
    },

    # ============================================================
    # PAS 2 — Per què "P(μ ∈ [3,2; 4,8]) = 95%" és incorrecta
    # ============================================================

    # ---- CORRECT ----
    {
        "id": "S2-CORR-01",
        "step_id": 2,
        "input": (
            "μ no és una variable aleatòria: té un valor concret, "
            "simplement no el coneixem. Parlar de 'probabilitat que "
            "μ estigui aquí' és com preguntar quina és la probabilitat "
            "que la Torre Eiffel mesuri 330 metres: o ho fa o no ho fa."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "metàfora"],
    },
    {
        "id": "S2-CORR-02",
        "step_id": 2,
        "input": (
            "La probabilitat ja s'ha 'gastat' en el procés de "
            "construcció de l'interval. Un cop tenim [3,2; 4,8], "
            "μ o hi és dins o no, amb probabilitat 1 o 0 — no 0,95."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "matemàtic"],
    },
    {
        "id": "S2-CORR-03",
        "step_id": 2,
        "input": (
            "Dir que μ té un 95% de probabilitat d'estar a l'interval "
            "seria tractar-lo com si fos aleatori. Però μ és un "
            "paràmetre poblacional fix; el que és aleatori és la "
            "mostra que hem pres."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "tècnic"],
    },
    {
        "id": "S2-CORR-04",
        "step_id": 2,
        "input": (
            "Confondre paràmetre i estadístic és l'error clàssic: "
            "la incertesa és sobre el nostre interval (construït a "
            "partir de dades aleatòries), no sobre μ, que no va a cap lloc."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "meta"],
    },

    # ---- TYPICAL_ERROR ----
    {
        "id": "S2-TYP-01",
        "step_id": 2,
        "input": (
            "Perquè el percentatge és aproximat — no és exactament "
            "95% sinó una mica menys o més."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["raonament-erroni-superficial"],
    },
    {
        "id": "S2-TYP-02",
        "step_id": 2,
        "input": (
            "Perquè caldria dir 'amb probabilitat aproximada del 95%', "
            "ja que mai podem ser exactes."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["raonament-erroni-elaborat"],
    },
    {
        "id": "S2-TYP-03",
        "step_id": 2,
        "input": (
            "La frase és incorrecta perquè es refereix només a una "
            "mostra, però hauríem de considerar moltes mostres futures."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["confusió-mostres-futures"],
    },
    {
        "id": "S2-TYP-04",
        "step_id": 2,
        "input": (
            "Perquè en realitat la probabilitat correcta és del 5%, "
            "no del 95% — és el complement."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["raonament-erroni-invertit"],
    },

    # ---- KEY_only — descoberta del stress test ----
    {
        "id": "S2-KEY-01",
        "step_id": 2,
        "input": "mu és constant",
        "expected_verdict": "typical_error",
        "expected_error_label": "KEY_only",
        "tags": ["keyword-only", "no-justifica", "discovered-in-stress-test"],
    },
    {
        "id": "S2-KEY-02",
        "step_id": 2,
        "input": "perquè és un paràmetre fix",
        "expected_verdict": "typical_error",
        "expected_error_label": "KEY_only",
        "tags": ["keyword-only", "no-justifica"],
    },

    # ---- CONCEPTUAL_GAP ----
    {
        "id": "S2-GAP-01",
        "step_id": 2,
        "input": "no sé per què és incorrecta, a mi em sembla bé la frase",
        "expected_verdict": "conceptual_gap",
        "expected_error_label": None,
        "tags": ["explicit-no-sap"],
    },
    {
        "id": "S2-GAP-02",
        "step_id": 2,
        "input": (
            "què vol dir paràmetre? jo creia que μ era la mitjana "
            "de la mostra que hem agafat"
        ),
        "expected_verdict": "conceptual_gap",
        "expected_error_label": None,
        "tags": ["confusió-paràmetre-estadístic"],
    },

    # ============================================================
    # PAS 3 — Interpretació correcta de l'interval
    # ============================================================

    # ---- CORRECT ----
    {
        "id": "S3-CORR-01",
        "step_id": 3,
        "input": (
            "Tenim un 95% de confiança que l'interval [3,2; 4,8] és "
            "dels que han capturat μ, tot i que no podem saber-ho "
            "amb certesa absoluta."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "concís"],
    },
    {
        "id": "S3-CORR-02",
        "step_id": 3,
        "input": (
            "Amb aquest mètode i aquestes dades, diem amb un 95% de "
            "confiança que μ queda recollit dins de [3,2; 4,8]."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "tècnic"],
    },
    {
        "id": "S3-CORR-03",
        "step_id": 3,
        "input": (
            "No podem afirmar que μ és aquí amb probabilitat 0,95, "
            "però sí que confiem en un 95% que aquest interval "
            "concret és un dels 'encertats'."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "contrast"],
    },
    {
        "id": "S3-CORR-04",
        "step_id": 3,
        "input": (
            "L'interval [3,2; 4,8] ha estat generat per un "
            "procediment que funciona el 95% de les vegades; per "
            "tant tenim un 95% de confiança que aquest n'és un dels bons."
        ),
        "expected_verdict": "correct",
        "expected_error_label": None,
        "tags": ["canonical", "procediment"],
    },

    # ---- TYPICAL_ERROR ----
    {
        "id": "S3-TYP-01",
        "step_id": 3,
        "input": (
            "Hi ha un 95% de probabilitat que μ es trobi entre "
            "3,2 i 4,8."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": "INT_prob_param",
        "tags": ["aran-classic-recidiva"],
    },
    {
        "id": "S3-TYP-02",
        "step_id": 3,
        "input": (
            "L'interval [3,2; 4,8] és la unió de tots els intervals "
            "que contenen el paràmetre vertader."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["definició-inventada"],
    },
    {
        "id": "S3-TYP-03",
        "step_id": 3,
        "input": (
            "L'interval ens diu que el 95% dels valors de la mostra "
            "estan entre 3,2 i 4,8."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["confusió-amb-percentil"],
    },
    {
        "id": "S3-TYP-04",
        "step_id": 3,
        "input": (
            "Si fem 100 mostres més, 95 d'elles donaran una mitjana "
            "entre 3,2 i 4,8."
        ),
        "expected_verdict": "typical_error",
        "expected_error_label": None,
        "tags": ["confusió-mostres-futures"],
    },

    # ---- KEY_only — descoberta del stress test ----
    {
        "id": "S3-KEY-01",
        "step_id": 3,
        "input": "tinc una confiança del 95%",
        "expected_verdict": "typical_error",
        "expected_error_label": "KEY_only",
        "tags": ["keyword-only", "sense-objecte", "discovered-in-stress-test"],
    },
    {
        "id": "S3-KEY-02",
        "step_id": 3,
        "input": "és una qüestió de confiança, no de probabilitat",
        "expected_verdict": "typical_error",
        "expected_error_label": "KEY_only",
        "tags": ["keyword-only", "no-aplica"],
    },

    # ---- CONCEPTUAL_GAP ----
    {
        "id": "S3-GAP-01",
        "step_id": 3,
        "input": "no entenc res, no sé què dir",
        "expected_verdict": "conceptual_gap",
        "expected_error_label": None,
        "tags": ["explicit-no-sap"],
    },
    {
        "id": "S3-GAP-02",
        "step_id": 3,
        "input": (
            "què és la confiança? és el mateix que la probabilitat o "
            "alguna altra cosa? estic perdut"
        ),
        "expected_verdict": "conceptual_gap",
        "expected_error_label": None,
        "tags": ["confessió-perdut"],
    },
]


# ============================================================
# Helpers
# ============================================================
def cases_by_step(step_id):
    return [c for c in CASES if c["step_id"] == step_id]


def cases_by_verdict(verdict):
    return [c for c in CASES if c["expected_verdict"] == verdict]


def case_by_id(case_id):
    for c in CASES:
        if c["id"] == case_id:
            return c
    return None
