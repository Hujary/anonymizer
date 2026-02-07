###     CLI für PD-Erkennung & Maskierung
### __________________________________________________________________________

import sys
import click
import time
from collections import Counter

# interne Module
from core.io import read_text, write_text
from pipeline.anonymisieren import maskiere
from core.einstellungen import INPUT_PATH, OUTPUT_PATH, DEBUG, USE_REGEX, USE_NER
from core.warnpolicy import apply_from_settings
from detectors.ner.ner_core import set_spacy_model, get_current_model

# globale Warnunterdrückung anwenden
apply_from_settings()


@click.group()
def cli():
    """Kommandozeilen-Interface für Anonymisierung."""
    pass


# ========================  Methode für PD-Erkennung & Maskierung  ==================================
@cli.command("mask")
@click.option(
    "--in",
    "in_path",
    default=str(INPUT_PATH),
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--out",
    "out_path",
    default=str(OUTPUT_PATH),
    type=click.Path(dir_okay=False),
)
@click.option(
    "--ner-model",
    type=click.Choice(["fast", "large", "de_core_news_md", "de_core_news_lg"], case_sensitive=False),
    help="spaCy-NER-Modell wählen: 'fast' (md), 'large' (lg) oder explizit 'de_core_news_md' / 'de_core_news_lg'.",
)
def cmd_mask(in_path: str, out_path: str, ner_model: str | None):
    """Erkennt und maskiert personenbezogene Daten im Eingabetext."""
    # optional: NER-Modell zur Laufzeit setzen, falls Flag übergeben
    if ner_model:
        effective = set_spacy_model(ner_model)
        if DEBUG:
            click.echo(f"[DEBUG] NER-Modell gesetzt auf: {effective}")

    start_time = time.time()

    text = read_text(in_path)
    masked, treffer = maskiere(text)
    write_text(out_path, masked)

    # Wenn Debug deaktiviert → nur Erfolgsmeldung
    if not DEBUG:
        click.echo("Maskierung erfolgreich.")
        return

    # Wenn Debug aktiv → detaillierte Statistik
    counter_source = Counter(getattr(t, "quelle", "?") for t in treffer)
    counter_label = Counter(t.label for t in treffer)
    total = len(treffer)
    runtime_ms = (time.time() - start_time) * 1000

    click.echo("\n=== DEBUG: Maskierung abgeschlossen ===")
    click.echo(f"Gesamt: {total} Treffer")
    click.echo(f"Laufzeit: {runtime_ms:.2f} ms")
    click.echo(f"NER-Modell: {get_current_model()}\n")

    click.echo("Erkennungsquellen:")
    for src, n in sorted(counter_source.items()):
        click.echo(f"  - {src:>6}: {n:>3}")

    click.echo("\nDatentypen:")
    for lbl, n in sorted(counter_label.items(), key=lambda x: (-x[1], x[0])):
        click.echo(f"  - {lbl:<20} {n:>3}")

    click.echo("\n[DEBUG INFO]")
    click.echo(f"  USE_REGEX: {USE_REGEX}")
    click.echo(f"  USE_NER:   {USE_NER}")
# ====================================================================================================


def main():
    cli(prog_name="cli")


if __name__ == "__main__":
    sys.exit(main())