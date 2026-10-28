def test_valid(cldf_dataset, cldf_logger):
    """The standard check for a cldfbench dataset (run with `pytest`, needs pytest-cldf)."""
    assert cldf_dataset.validate(log=cldf_logger)
