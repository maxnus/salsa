"""The rows of one table, gathered during a playback and handed over as an Arrow table at its end."""

from collections.abc import Sequence

import pyarrow

# Rows gathered as tuples before they become Arrow arrays, which hold a whole game's rows at their columns' size rather
# than at a Python object a value.
_ROWS_A_BLOCK = 100_000


class TableBuilder:
    """The rows of a table of `schema`, each a tuple of its values in the schema's order, `None` for null. A column
    the format names with its own words takes the word's index in `words[column]`."""

    def __init__(self, schema: pyarrow.Schema, *, words: dict[str, Sequence[str]] | None = None) -> None:
        self._schema = schema
        self._words = {
            name: pyarrow.array(column_words, pyarrow.string()) for name, column_words in (words or {}).items()
        }
        self._rows: list[tuple[object, ...]] = []
        self._batches: list[pyarrow.RecordBatch] = []

    def add(self, row: tuple[object, ...]) -> None:
        """Add one row."""
        self._rows.append(row)
        if len(self._rows) >= _ROWS_A_BLOCK:
            self._turn_rows_into_a_batch()

    def table(self) -> pyarrow.Table:
        """Every row added, in the order added."""
        self._turn_rows_into_a_batch()
        return pyarrow.Table.from_batches(self._batches, schema=self._schema)

    def _turn_rows_into_a_batch(self) -> None:
        if not self._rows:
            return
        columns = list(zip(*self._rows, strict=True))
        arrays = [self._array_of(field, values) for field, values in zip(self._schema, columns, strict=True)]
        self._batches.append(pyarrow.RecordBatch.from_arrays(arrays, schema=self._schema))
        self._rows = []

    def _array_of(self, field: pyarrow.Field, values: Sequence[object]) -> pyarrow.Array:
        words = self._words.get(field.name)
        if words is None:
            return pyarrow.array(values, field.type)
        return pyarrow.DictionaryArray.from_arrays(pyarrow.array(values, pyarrow.int8()), words)
