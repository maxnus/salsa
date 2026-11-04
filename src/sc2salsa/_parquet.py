"""A table written as Parquet the way `SPEC.md` says: zstd, delta encoding for integer columns and byte-stream-split for
float columns, and the format's own words dictionary-encoded."""

from collections.abc import Sequence

import numpy
import pyarrow
import pyarrow.parquet

# Rows a row group, Parquet's default: smaller groups made a game's unit tables 40 to 60% bigger and read no faster
# (salsa#2).
_ROWS_A_ROW_GROUP = 1024 * 1024


def parquet_bytes(table: pyarrow.Table, *, sorted_by: Sequence[str] = ()) -> bytes:
    """`table` as the bytes of a Parquet file, its rows sorted by the columns `sorted_by`, the first most significant,
    keeping the order they were added in among rows that tie."""
    sink = pyarrow.BufferOutputStream()
    order = _order_by(table, sorted_by) if sorted_by else None
    word_columns = [field.name for field in table.schema if pyarrow.types.is_dictionary(field.type)]
    with pyarrow.parquet.ParquetWriter(
        sink,
        table.schema,
        compression="zstd",
        # pyarrow takes a list of the columns to dictionary-encode, as its docs say; its stubs say a bool alone.
        use_dictionary=word_columns,  # pyright: ignore[reportArgumentType]
        column_encoding=_encodings_of(table.schema),
    ) as writer:
        for start in range(0, max(table.num_rows, 1), _ROWS_A_ROW_GROUP):
            if order is None:
                rows = table.slice(start, _ROWS_A_ROW_GROUP)
            else:
                # A row group at a time, so that the table sorted is never held whole beside the table.
                rows = table.take(order[start : start + _ROWS_A_ROW_GROUP])
            writer.write_table(rows)
    return sink.getvalue().to_pybytes()


def _order_by(table: pyarrow.Table, columns: Sequence[str]) -> numpy.ndarray:
    """The indices of `table`'s rows sorted by `columns`, stably: numpy's lexsort takes its keys least significant
    first."""
    keys = [table.column(name).to_numpy() for name in reversed(columns)]
    return numpy.lexsort(keys)


def _encodings_of(schema: pyarrow.Schema) -> dict[str, str]:
    """The encoding of each column `SPEC.md` names one for: its integer and float columns at the top level."""
    encodings = {}
    for field in schema:
        if pyarrow.types.is_integer(field.type):
            encodings[field.name] = "DELTA_BINARY_PACKED"
        elif pyarrow.types.is_floating(field.type):
            encodings[field.name] = "BYTE_STREAM_SPLIT"
    return encodings
