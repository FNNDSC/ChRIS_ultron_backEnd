import pytest

from benchmarks.units import parse_size, to_dbg_params


@pytest.mark.parametrize("text,expected", [
    ("1024B", 1024),
    ("1KiB", 1024),
    ("1MiB", 1024 ** 2),
    ("1GiB", 1024 ** 3),
    ("1k", 1024),            # bare k -> binary
    ("1mb", 1000 ** 2),      # decimal mb
    ("100KiB", 100 * 1024),
    ("512", 512),            # bare number -> bytes
    ("1.5MiB", int(1.5 * 1024 ** 2)),
])
def test_parse_size(text, expected):
    assert parse_size(text) == expected


def test_parse_size_passthrough_numbers():
    assert parse_size(2048) == 2048


def test_parse_size_rejects_garbage():
    with pytest.raises(ValueError):
        parse_size("abc")


def test_to_dbg_params_exact_count():
    # total = count * size guarantees exactly `count` files in dbg-bigfiles
    assert to_dbg_params(10, "1KiB") == {"total": "10240B", "size": "1024B"}
    assert to_dbg_params(1, "1MiB") == {"total": "1048576B", "size": "1048576B"}


def test_to_dbg_params_never_emits_kib():
    # dbg-bigfiles cannot parse KiB; we must always emit bytes
    params = to_dbg_params(100, "100KiB")
    assert params["total"].endswith("B") and "i" not in params["total"]


def test_to_dbg_params_rejects_zero_count():
    with pytest.raises(ValueError):
        to_dbg_params(0, "1KiB")
