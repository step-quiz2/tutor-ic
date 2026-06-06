"""
Definició dels capítols del Tutor de Divisibilitat (1r ESO).

Disseny pensat per a l'Aran (12 anys), que encara:
  - confon "múltiple" i "divisor",
  - no veu que els múltiples són infinits,
  - confon "imparell" amb "nombre primer".

Per això cada PAS demana **una sola cosa**, amb frases molt curtes.
Val més fer molts passos petits que un de gros.

Cada capítol té:
  - id, titol, emoji, introduccio (text curt que veu l'alumne)
  - error_catalog → {codi: descripció} dels malentesos típics del capítol
    (Tasca 4: el control block diagnostica quin error mostra l'alumne)
  - passos: cadascun amb
      id              → "1.1", "1.2", ...
      pregunta        → text que veu l'alumne (UNA sola pregunta, curta)
      descripcio_pas  → resum intern (per al tutor LLM)
      resposta_ref    → resposta de referència (MAI es mostra a l'alumne)
      conceptes_clau  → llista de conceptes a detectar (per al LLM i el mode reserva)
      pistes          → pistes progressives (curtes, una idea cada una)
      typical_error_label → codi del catàleg del capítol amb l'error més
                            probable d'aquest pas (per a pista i diagnòstic;
                            opcional)
      pistes_per_error → {codi: pista} pista mapejada a un error concret
                         (opcional; si falta, es cau a pistes[0])

Codi de diagnòstic comodí, sempre vàlid, quan cap codi específic encaixa.
"""

GEN_OTHER = "GEN_other"


CAPITOLS = [
    # ------------------------------------------------------------------ #
    # CAPÍTOL 1 · Múltiples: 12 de 3 o 3 de 12?                          #
    # ------------------------------------------------------------------ #
    {
        "id": 1,
        "titol": "Múltiples",
        "emoji": "✖️",
        "introduccio": "Avui mirem què vol dir **ser múltiple**. Treballem amb el 12 i el 3.",
        "error_catalog": {
            "MUL_div_inexacta": (
                "Creu que una divisió no exacta (amb decimals o residu) "
                "és vàlida com a 'divisió que funciona'. No distingeix "
                "exacta de no exacta."
            ),
            "MUL_direccio": (
                "Confon la direcció: pensa que 'A múltiple de B' i "
                "'B múltiple de A' són el mateix, o tria la divisió que "
                "no surt exacta."
            ),
            "KEY_only": (
                "Diu una paraula correcta (exacta, múltiple...) sense "
                "justificar-la ni aplicar-la al cas concret."
            ),
            "GEN_other": "Error no catalogat.",
        },
        "passos": [
            {
                "id": "1.1",
                "pregunta": "Quant fa **12 ÷ 3**?",
                "descripcio_pas": "Calcular 12÷3 i veure que és exacta.",
                "resposta_ref": "12 ÷ 3 = 4. Surt rodó, és exacta.",
                "conceptes_clau": ["4", "exacta"],
                "typical_error_label": "MUL_div_inexacta",
                "pistes": [
                    "Reparteix 12 caramels en 3 bosses iguals. Quants en toca a cada bossa?",
                    "12 ÷ 3 = 4. No en sobra cap, per això és exacta.",
                ],
            },
            {
                "id": "1.2",
                "pregunta": "Ara fes **3 ÷ 12**. Et surt un nombre sencer?",
                "descripcio_pas": "Veure que 3÷12 no és exacta.",
                "resposta_ref": "3 ÷ 12 = 0,25. No és sencer, no és exacta.",
                "conceptes_clau": ["no", "0,25", "no exacta"],
                "typical_error_label": "MUL_div_inexacta",
                "pistes": [
                    "Vols donar 3 caramels a 12 nens. Arriba a tocar-ne un sencer a cadascú?",
                    "3 ÷ 12 = 0,25. Com que no és sencer, no és exacta.",
                ],
            },
            {
                "id": "1.3",
                "pregunta": "El **12 és múltiple del 3**? (Pista: mira quina divisió surt exacta.)",
                "descripcio_pas": "Aplicar la definició: A és múltiple de B si A÷B és exacta.",
                "resposta_ref": (
                    "Sí. 12 és múltiple de 3 perquè 12÷3 és exacta. "
                    "En canvi, 3 no és múltiple de 12."
                ),
                "conceptes_clau": ["si", "12 es multiple de 3"],
                "typical_error_label": "MUL_direccio",
                "pistes": [
                    "Múltiple vol dir que la divisió surt exacta. Quina ha sortit exacta?",
                    "12 ÷ 3 = 4, és exacta. Per tant el 12 és múltiple del 3.",
                ],
                "pistes_per_error": {
                    "MUL_direccio": (
                        "Recorda: només una de les dues divisions ha sortit "
                        "exacta (12÷3). Mira quin nombre dividies per quin."
                    ),
                },
            },
        ],
    },

    # ------------------------------------------------------------------ #
    # CAPÍTOL 2 · Divisors i múltiples de 15 (els múltiples són infinits) #
    # ------------------------------------------------------------------ #
    {
        "id": 2,
        "titol": "Divisors i múltiples del 15",
        "emoji": "➗",
        "introduccio": "Ara veiem la diferència entre **divisors** i **múltiples**, amb el 15.",
        "error_catalog": {
            "DIV_mult_confusio": (
                "Confon divisor amb múltiple: dona múltiples quan es "
                "demanen divisors o a l'inrevés."
            ),
            "MUL_finits": (
                "Creu que els múltiples d'un nombre s'acaben / són una "
                "llista finita."
            ),
            "KEY_only": (
                "Diu 'divisor' o 'múltiple' sense aplicar-ho ni comptar res."
            ),
            "GEN_other": "Error no catalogat.",
        },
        "passos": [
            {
                "id": "2.1",
                "pregunta": (
                    "El 15 es divideix exacte per 1, 3, 5 i 15. "
                    "Aquests són els seus **divisors**. Quants en té?"
                ),
                "descripcio_pas": "Comptar els divisors del 15 (en té 4).",
                "resposta_ref": "El 15 té 4 divisors: 1, 3, 5 i 15.",
                "conceptes_clau": ["4", "quatre"],
                "typical_error_label": "DIV_mult_confusio",
                "pistes": [
                    "Compta'ls a poc a poc: 1, 3, 5, 15.",
                    "Són quatre nombres, així que el 15 té 4 divisors.",
                ],
            },
            {
                "id": "2.2",
                "pregunta": "Ara escriu els **3 primers múltiples** del 15.",
                "descripcio_pas": "Calcular 15·1, 15·2, 15·3.",
                "resposta_ref": "15, 30, 45 (que són 15×1, 15×2 i 15×3).",
                "conceptes_clau": ["15", "30", "45"],
                "typical_error_label": "DIV_mult_confusio",
                "pistes": [
                    "15 × 1 = 15. 15 × 2 = 30. I el següent?",
                    "15 × 3 = 45. Per tant: 15, 30, 45.",
                ],
                "pistes_per_error": {
                    "DIV_mult_confusio": (
                        "Un múltiple del 15 surt de MULTIPLICAR el 15 "
                        "(15×1, 15×2...), no de dividir-lo. Prova-ho."
                    ),
                },
            },
            {
                "id": "2.3",
                "pregunta": "Els múltiples del 15, **s'acaben en algun moment**?",
                "descripcio_pas": "Veure que els múltiples són infinits.",
                "resposta_ref": (
                    "No s'acaben mai. Sempre pots multiplicar per un nombre més gran. "
                    "Els múltiples són infinits."
                ),
                "conceptes_clau": ["no", "no s'acaben", "mai", "infinits"],
                "typical_error_label": "MUL_finits",
                "pistes": [
                    "Pots fer 15 × 100? I 15 × 1.000?",
                    "Sempre pots posar un nombre més gran. Per això no s'acaben mai.",
                ],
            },
        ],
    },

    # ------------------------------------------------------------------ #
    # CAPÍTOL 3 · Pocs o molts divisors                                  #
    # ------------------------------------------------------------------ #
    {
        "id": 3,
        "titol": "Pocs o molts divisors",
        "emoji": "📊",
        "introduccio": "Alguns nombres tenen pocs divisors i d'altres en tenen molts. Mirem-ho!",
        "error_catalog": {
            "DIV_compta_malament": (
                "Compta malament els divisors: n'oblida algun, hi posa "
                "nombres que no divideixen exacte, o inclou/exclou l'1 o "
                "el mateix nombre per error."
            ),
            "DIV_exacta": (
                "No comprova bé si la divisió és exacta abans de comptar "
                "un nombre com a divisor."
            ),
            "KEY_only": "Diu un nombre sense comptar ni justificar.",
            "GEN_other": "Error no catalogat.",
        },
        "passos": [
            {
                "id": "3.1",
                "pregunta": "Quins d'aquests nombres són **divisors del 7**? (1, 2, 3, 4, 5, 6, 7)",
                "descripcio_pas": "Triar els divisors del 7 de la llista (només 1 i 7).",
                "resposta_ref": "Només l'1 i el 7. El 7 té 2 divisors.",
                "conceptes_clau": ["1 i 7", "2 divisors", "dos"],
                "typical_error_label": "DIV_exacta",
                "pistes": [
                    "Mira quins divideixen exacte el 7: 7÷1, 7÷2, 7÷3...",
                    "Només 7÷1 i 7÷7 surten exactes. Per tant: 1 i 7.",
                ],
            },
            {
                "id": "3.2",
                "pregunta": "Ara els divisors del **12**. Quins nombres el divideixen exacte?",
                "descripcio_pas": "Trobar els divisors del 12 (en té 6).",
                "resposta_ref": "1, 2, 3, 4, 6 i 12. El 12 té 6 divisors.",
                "conceptes_clau": ["1 2 3 4 6 12", "6 divisors", "sis"],
                "typical_error_label": "DIV_compta_malament",
                "pistes": [
                    "Prova 12÷1, 12÷2, 12÷3, 12÷4, 12÷6, 12÷12.",
                    "Surten: 1, 2, 3, 4, 6, 12. Són sis.",
                ],
                "pistes_per_error": {
                    "DIV_compta_malament": (
                        "Ves un per un de l'1 al 12 i queda't només els que "
                        "divideixen exacte. No t'oblidis de l'1 ni del 12."
                    ),
                },
            },
            {
                "id": "3.3",
                "pregunta": "Qui té **més divisors**, el 7 o el 12?",
                "descripcio_pas": "Comparar la quantitat de divisors.",
                "resposta_ref": "El 12 (en té 6), molt més que el 7 (que en té 2).",
                "conceptes_clau": ["12", "el 12"],
                "typical_error_label": "GEN_other",
                "pistes": [
                    "El 7 en té 2. El 12 en té 6.",
                    "6 és més que 2, així que el 12 en té més.",
                ],
            },
        ],
    },

    # ------------------------------------------------------------------ #
    # CAPÍTOL 4 · Nombres primers                                        #
    # ------------------------------------------------------------------ #
    {
        "id": 4,
        "titol": "Nombres primers",
        "emoji": "⭐",
        "introduccio": (
            "Un **nombre primer** té només 2 divisors: l'1 i ell mateix. Anem a descobrir-los!"
        ),
        "error_catalog": {
            "PRIME_imparell": (
                "Confon primer amb imparell: pensa que tot nombre senar és "
                "primer (o que el criteri de primer té a veure amb ser "
                "parell/senar)."
            ),
            "PRIME_definicio": (
                "No aplica la definició de primer = exactament 2 divisors: "
                "no compta els divisors o accepta nombres amb més de 2."
            ),
            "KEY_only": (
                "Diu 'primer' o 'no primer' sense comptar els divisors."
            ),
            "GEN_other": "Error no catalogat.",
        },
        "passos": [
            {
                "id": "4.1",
                "pregunta": (
                    "Al capítol anterior, el 7 tenia 2 divisors i el 12 en tenia 6. "
                    "Quin dels dos és **primer**?"
                ),
                "descripcio_pas": "Aplicar la definició: primer = exactament 2 divisors. El 7 ho és, el 12 no.",
                "resposta_ref": "El 7. Té només 2 divisors, així que és primer. El 12 en té 6, no és primer.",
                "conceptes_clau": ["7", "el 7"],
                "typical_error_label": "PRIME_definicio",
                "pistes": [
                    "Un primer en té només 2. Quin dels dos en té 2?",
                    "El 7 en té 2 → primer. El 12 en té 6 → no primer.",
                ],
            },
            {
                "id": "4.2",
                "pregunta": "Ara el **9**. Es divideix per 1, per 3 i per 9. El 9 és primer?",
                "descripcio_pas": "Veure que el 9 NO és primer: té 3 divisors, no 2.",
                "resposta_ref": "No. El 9 té 3 divisors (1, 3 i 9), i un primer en té només 2.",
                "conceptes_clau": ["no", "no es primer", "3 divisors"],
                "typical_error_label": "PRIME_imparell",
                "pistes": [
                    "Compta els seus divisors: 1, 3 i 9. Quants són?",
                    "Són 3 divisors, no 2. Per tant el 9 no és primer.",
                ],
                "pistes_per_error": {
                    "PRIME_imparell": (
                        "Que un nombre sigui senar no el fa primer. El 9 és "
                        "senar, però mira: 1, 3 i 9 el divideixen. Quants "
                        "divisors són?"
                    ),
                },
            },
        ],
    },
]


# ───────────────────────── helpers ───────────────────────────────────── #

def get_capitol(id_cap: int) -> dict | None:
    for c in CAPITOLS:
        if c["id"] == id_cap:
            return c
    return None


def num_capitols() -> int:
    return len(CAPITOLS)


# ─────────────── catàleg d'errors / diagnòstic (Tasca 4) ──────────────── #
# El control block del tutor retorna un `diagnostic`: un codi del catàleg
# d'errors que nomena la malentesa conceptual de l'alumne. El catàleg viu
# per CAPÍTOL (els errors són transversals als seus passos). Aquests helpers
# l'exposen a la capa LLM (per injectar codis al marcador de posició) i al
# caller (per validar/normalitzar el codi rebut). El diagnòstic NO influeix
# mai en la màquina d'estats; només alimenta pista i panell del professor.

def error_catalog(cap: dict) -> dict:
    """Catàleg d'errors d'un capítol: {codi: descripció}. Buit si no en té."""
    return cap.get("error_catalog", {}) if cap else {}


def allowed_diagnostics(cap: dict) -> list:
    """Codis de diagnòstic vàlids per al capítol (tots els del catàleg, amb
    GEN_other garantit al final). Llista de strings."""
    catalog = error_catalog(cap)
    codes = [c for c in catalog.keys() if c != GEN_OTHER]
    codes.append(GEN_OTHER)
    return codes


def likely_diagnostic_for_step(pas: dict):
    """`typical_error_label` del pas (codi més probable) o None."""
    return pas.get("typical_error_label") if pas else None


def normalize_diagnostic(cap: dict, code):
    """Normalitza un codi rebut del model contra el catàleg del capítol.

    - None / "" / "null" / no-string → None (cap diagnòstic).
    - codi del catàleg → es retorna tal qual.
    - codi desconegut → GEN_other.

    Punt únic de validació del caller; el parser de llm.py no valida.
    """
    if not isinstance(code, str):
        return None
    code = code.strip()
    if not code or code.lower() == "null":
        return None
    return code if code in error_catalog(cap) else GEN_OTHER


def hint_for_diagnostic(pas: dict, code):
    """Pista mapejada a un codi via `pistes_per_error` del pas, o None si no
    n'hi ha cap (el caller cau llavors a pistes[0])."""
    if not code or not pas:
        return None
    return (pas.get("pistes_per_error") or {}).get(code)
