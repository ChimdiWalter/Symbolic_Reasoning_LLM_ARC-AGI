"""Registers the markers used by the test files of this workspace."""


def pytest_configure(config):
    config.addinivalue_line("markers", "engine: runs the real reasoning engine (minutes)")
