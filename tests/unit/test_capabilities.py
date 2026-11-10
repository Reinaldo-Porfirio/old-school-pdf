import socket
import subprocess

from oldschoolpdf.application.capability_service import CapabilitiesService
from oldschoolpdf.domain.security import SIGNING_VERSION
from oldschoolpdf.infrastructure.dependency_probe import LocalDependencyProbe


class Probe:
    """Fake apenas em testes internos, nunca instanciado pela aplicação."""

    def __init__(self, installed=False):
        self.installed = installed

    def package_version(self, name):
        return "test-version" if self.installed else None

    def executable_exists(self, name):
        return self.installed


def test_missing_optional_components_leave_desktop_available():
    report = CapabilitiesService(Probe()).check()
    assert report.get("desktop").implemented
    assert not report.get("pdf").detected
    assert not report.get("tesseract").detected
    assert report.get("certificates").detected is None


def test_installed_components_never_enable_future_operations():
    report = CapabilitiesService(Probe(True)).check()
    future = [item for item in report.items if item.key not in {"desktop", "pdf", "tesseract"}]
    assert all(not item.implemented for item in future)
    assert report.get("pdf").detected
    assert report.get("pdf").implemented
    assert report.get("tesseract").implemented
    assert not report.get("tesseract").detected
    assert "não validada" in report.get("office").detail
    assert report.get("certificates").detected is None


def test_supported_signing_version_only_enables_local_signing():
    class SigningProbe(Probe):
        def package_version(self, name):
            return SIGNING_VERSION if name == "pyhanko" else None

    service = CapabilitiesService(SigningProbe())
    report = service.check()
    assert service.signing_available()
    assert report.get("signing").implemented and report.get("signing").detected
    assert report.get("certificates").implemented and report.get("certificates").detected is None
    assert not report.get("office").implemented


def test_real_probe_cannot_spawn_or_use_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Rede e processos externos são proibidos neste diagnóstico")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    report = CapabilitiesService(LocalDependencyProbe()).check()
    assert len(report.items) == 7
    assert report.get("desktop").implemented
