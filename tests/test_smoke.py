"""Smoke-test: de belangrijkste pakketten zijn geïnstalleerd."""


def test_pakketten_importeren() -> None:
    """ortools, pandas en streamlit laten zich importeren."""
    import ortools  # noqa: F401
    import pandas  # noqa: F401
    import streamlit  # noqa: F401
    from ortools.sat.python import cp_model  # noqa: F401
