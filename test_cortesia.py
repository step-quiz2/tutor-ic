"""
test_cortesia.py — guarda-raïl de la regla d'estil "imperatiu directe".

Cobreix el detector `detect_cortesia_interrogativa` i el senyal
`cortesia_interrogativa_*` que s'adjunta a quality_signals. La filosofia
del detector és ser CONSERVADOR: ha de caçar les fórmules que la regla del
prompt prohibeix, però MAI marcar una pregunta socràtica genuïna (això
inflaria la mètrica i la faria inútil). Per això hi ha tants casos negatius
com positius.
"""

import simulator as S


# --- Casos que SÍ s'han de marcar (reincidència de cortesia) ------------- #
POSITIUS = [
    "Podries desenvolupar una mica més què vols dir?",
    "Series capaç de justificar aquesta afirmació?",
    "T'importaria explicar-ho amb les teves paraules?",
    # A mitja resposta, després d'una frase d'introducció:
    "Bon punt. Podries concretar a què et refereixes amb «encert»?",
    # Amb signe d'obertura i cometes:
    "¿Podries posar-ho en context?",
]

# --- Casos que NO s'han de marcar (pedagogia legítima o imperatiu) ------- #
NEGATIUS = [
    # Imperatiu directe: el que la regla VOL.
    "Desenvolupa una mica més què significa «encertar la mitjana».",
    "Explica-ho amb les teves paraules.",
    # Preguntes socràtiques genuïnes, no de cortesia:
    "Per què aquesta frase és incorrecta?",
    "Què té de diferent μ respecte de la mostra?",
    "Sobre què fa referència aquesta probabilitat?",
    # "Podries" enmig sense ser obertura de cortesia interrogativa:
    "Fixa't que aquí podries caure en l'error de sempre. Mira-ho de nou.",
    # Buit / no-string:
    "",
]


def test_detecta_positius():
    fails = [t for t in POSITIUS if not S.detect_cortesia_interrogativa(t)]
    assert not fails, "Hauria d'haver marcat:\n" + "\n".join(fails)


def test_no_marca_negatius():
    fails = [t for t in NEGATIUS if S.detect_cortesia_interrogativa(t)]
    assert not fails, "NO hauria d'haver marcat:\n" + "\n".join(fails)


def test_no_string():
    assert S.detect_cortesia_interrogativa(None) is False
    assert S.detect_cortesia_interrogativa(123) is False


def _state_amb_history(entrades):
    """Construeix un state mínim amb un history sintètic per provar el senyal."""
    return {
        "history": entrades,
        "finished": True,
        "turn_count": len(entrades),
        "problem_id": "IC-001",
        "started_at": 0.0,
    }


def test_senyal_compta_nomes_torns_ia():
    """El mode de reserva (reply_source='py') NO s'ha de comptar, encara
    que el seu text contingui una fórmula de cortesia."""
    history = [
        {"tutor_reply": "Podries explicar-ho?", "reply_source": "ai",
         "action": "stay", "control_parse_ok": True, "position_before": {"step": 1}},
        {"tutor_reply": "Podries explicar-ho?", "reply_source": "py",
         "action": "stay", "control_parse_ok": True, "position_before": {"step": 1}},
        {"tutor_reply": "Explica-ho.", "reply_source": "ai",
         "action": "advance", "control_parse_ok": True, "position_before": {"step": 1}},
    ]
    qs = S.compute_quality_signals(_state_amb_history(history))
    # 2 torns IA, 1 amb cortesia → hits=1, rate=0.5
    assert qs["cortesia_interrogativa_hits"] == 1, qs["cortesia_interrogativa_hits"]
    assert qs["cortesia_interrogativa_rate"] == 0.5, qs["cortesia_interrogativa_rate"]


def test_senyal_sense_torns_ia():
    """Sense cap torn IA, el rate és None (no 0.0: no hi ha res a mesurar)."""
    history = [
        {"tutor_reply": "Podries explicar-ho?", "reply_source": "py",
         "action": "stay", "control_parse_ok": True, "position_before": {"step": 1}},
    ]
    qs = S.compute_quality_signals(_state_amb_history(history))
    assert qs["cortesia_interrogativa_hits"] == 0
    assert qs["cortesia_interrogativa_rate"] is None


def test_senyal_rastre_antic_assumeix_ia():
    """Rastres sense `reply_source` (anteriors a aquest canvi) s'han de
    tractar com a IA per no perdre senyal."""
    history = [
        {"tutor_reply": "Podries explicar-ho?",
         "action": "stay", "control_parse_ok": True, "position_before": {"step": 1}},
    ]
    qs = S.compute_quality_signals(_state_amb_history(history))
    assert qs["cortesia_interrogativa_hits"] == 1


if __name__ == "__main__":
    tests = [
        test_detecta_positius,
        test_no_marca_negatius,
        test_no_string,
        test_senyal_compta_nomes_torns_ia,
        test_senyal_sense_torns_ia,
        test_senyal_rastre_antic_assumeix_ia,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}\n    {e}")
            failed += 1
    print("=" * 60)
    print(f"Tests passats: {passed}")
    print(f"Tests fallits: {failed}")
    print("=" * 60)
    raise SystemExit(1 if failed else 0)
