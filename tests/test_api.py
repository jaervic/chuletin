"""Pruebas de la API HTTP."""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient


def test_health(temp_db):
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_crud_de_materias(temp_db):
    with TestClient(app) as client:
        created = client.post("/api/subjects", json={"name": "Biologia"})
        assert created.status_code == 201
        subject_id = created.json()["id"]

        duplicated = client.post("/api/subjects", json={"name": "biologia"})
        assert duplicated.status_code == 409

        listing = client.get("/api/subjects").json()
        assert len(listing) == 1
        assert listing[0]["name"] == "Biologia"

        renamed = client.patch(
            f"/api/subjects/{subject_id}", json={"name": "Biologia celular"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Biologia celular"

        assert client.delete(f"/api/subjects/{subject_id}").status_code == 204
        assert client.get("/api/subjects").json() == []


def test_rechaza_archivo_falso(temp_db):
    with TestClient(app) as client:
        subject = client.post("/api/subjects", json={"name": "Historia"}).json()
        response = client.post(
            "/api/documents",
            data={"subject_id": subject["id"]},
            files={"file": ("tema.pdf", b"<html>no soy un pdf</html>", "application/pdf")},
        )
        assert response.status_code == 400
        assert "contenido" in response.json()["detail"].lower()


def test_rechaza_extension_no_admitida(temp_db):
    with TestClient(app) as client:
        subject = client.post("/api/subjects", json={"name": "Fisica"}).json()
        response = client.post(
            "/api/documents",
            data={"subject_id": subject["id"]},
            files={"file": ("script.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert response.status_code == 400


def test_ajustes_no_exponen_claves(temp_db):
    with TestClient(app) as client:
        settings = client.get("/api/settings").json()
        assert settings["current"] == "gemini"
        assert len(settings["providers"]) >= 4
        for provider in settings["providers"]:
            assert "api_key" not in provider


def test_bloquea_origen_cruzado(temp_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/subjects",
            json={"name": "Quimica"},
            headers={"origin": "https://sitio-malicioso.example"},
        )
        assert response.status_code == 403
