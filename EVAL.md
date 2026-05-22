# Sistema d'avaluació (EVAL)

Aquest mòdul comprova que `llm.judge_step` (la crida central del sistema)
es comporta com prediuen les precondicions/postcondicions declarades a
priori a `eval_cases.py`.

## Estructura

- **`eval_cases.py`** — *dataset*. 30 casos:
  - 12 `correct` (4 per pas, paràfrasis canòniques)
  - 12 `typical_error` (4 per pas, l'error d'Aran en diferents formes)
  - 6 `conceptual_gap` (2 per pas, buits clars)
- **`eval_runner.py`** — *runner*. Itera, crida la IA real, compara,
  reporta.

## Execució

```bash
# Cas bàsic — una passada, només verdict
export GEMINI_API_KEY=...
python eval_runner.py

# Mesura de variància — 3 repeticions per cas
python eval_runner.py --repeat 3

# Verificar també etiquetes d'error (mode estricte)
python eval_runner.py --check-labels

# Filtrar per pas o categoria
python eval_runner.py --filter S1            # només Pas 1
python eval_runner.py --filter S2-TYP        # només errors típics del Pas 2
python eval_runner.py --filter S3-CORR-02    # un cas concret
```

## Sortides

### Consola

Per cas: `[idx/total] id  (verdict_esperat)  ✓` o `✗` + detall.

Al final: resum agregat, taxa per veredicte i per pas, **llista de
falsos positius i negatius**, matriu de confusió.

### JSON

Per defecte `eval_results_<timestamp>.json`. Conté el cas complet
(input + expectativa) i totes les repeticions amb la resposta de la
IA: veredicte obtingut, etiqueta, raó textual, temps. Permet auditar
manualment qualsevol discrepància.

## Falsos positius vs falsos negatius

El runner distingeix els dos tipus d'error perquè **no són pedagògicament
equivalents**:

- **Fals positiu** — el sistema diu *correct* quan l'esperat era
  *typical_error* o *conceptual_gap*. **Inacceptable**: l'alumne avança
  amb un error que ningú no ha detectat.
- **Fals negatiu** — el sistema diu *typical_error* o *conceptual_gap*
  quan l'esperat era *correct*. Menys greu: bloqueja l'alumne però
  existeix `!text` per registrar discrepància.

La mètrica clau de fiabilitat a minimitzar és **el nombre absolut de
falsos positius**, no la taxa global d'acord.

## Cost

Una execució completa: ~30 crides × ~3 000 tokens ≈ 90 000 tokens.
Amb Gemini Flash, ~0,01 € per execució. Es pot iterar lliurement.

## Iteració del prompt

Si veus un patró de fallades, edita el `_SYSTEM_JUDGE` a `llm.py` i
torna a executar. El runner és intencionadament ràpid (~2 min) perquè
sigui el bucle natural de desenvolupament del prompt.
