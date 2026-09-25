"""Publicación y retención de los artefactos generados por el pipeline."""
from pathlib import Path


def _same_path(left: Path, right: Path | None) -> bool:
    return right is not None and left.resolve() == right.resolve()


def limpiar_salidas(json_dir: Path, word_dir: Path, *, json_actual: Path | None,
                    word_actual: Path | None = None, recibo_actual: Path | None = None) -> dict[str, int]:
    """Conserva sólo los artefactos publicados por la ejecución exitosa actual.

    Las carpetas ``output/json`` y ``output/word`` pertenecen al pipeline. Los
    bloqueos ``~$`` se omiten: Word los administra mientras el documento está
    abierto y normalmente los elimina al cerrarlo.
    """
    removidos = {'json': 0, 'word': 0}
    for path in json_dir.glob('*.json') if json_dir.exists() else ():
        if path.is_file() and not _same_path(path, json_actual) and not _same_path(path, recibo_actual):
            path.unlink()
            removidos['json'] += 1
    for path in word_dir.glob('*.docx') if word_dir.exists() else ():
        if path.name.startswith('~$'):
            continue
        if path.is_file() and not _same_path(path, word_actual):
            path.unlink()
            removidos['word'] += 1
    return removidos
