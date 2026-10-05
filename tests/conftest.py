import pytest


@pytest.fixture(autouse=True)
def _isolate_from_the_real_profile_server(monkeypatch):
    """RFC-0020: resolver el perfil activo habla con el profile server (get-or-create
    de un repositorio). Sin esto, la suite llegaría al servidor REAL de la máquina y
    registraría repositorios para directorios temporales. Por defecto los tests usan
    solo environment.json; los que prueban la ruta del servidor lo reactivan y
    simulan profile_client."""
    monkeypatch.setenv("HIGPERTEXT_PROFILE_SOURCE", "local")
    from higpertext_mcp import repository_resolution

    repository_resolution.invalidate()
    yield
    repository_resolution.invalidate()
