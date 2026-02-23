from __future__ import annotations

import version


def test_version_label_contains_version_and_build_date() -> None:
    label = version.version_label()
    assert isinstance(version.__version__, str)
    assert isinstance(version.__build_date__, str)
    assert version.__version__ in label
    assert version.__build_date__ in label

