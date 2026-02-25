import os
import requests
import json

import uuid

def login(base_url, username, password):
    s = requests.Session()

    # 1) Crear sesión
    resp = s.post(
        f"{base_url}/sessions",
        json={
            "username": username,
            "password": password,
            "scope": "ui"
        }
    )
    resp.raise_for_status()

    # 2) Activar sesión con grupo
    headers = {
        "Content-Type": "application/json",
        "CMDBuild-ActionId": "login",
        "CMDBuild-ClientId": str(uuid.uuid4()),
        "CMDBuild-View": "default",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Usa el rol que CMDBuild te devolvió
    body = {"role": "SuperUser", "username":"at_devops11@miteco.es"}

    resp2 = s.put(
        f"{base_url}/sessions/current?ext=true",
        json=body,
        headers=headers
    )
    resp2.raise_for_status()

    token = s.cookies.get("CMDBuild-Authorization")
    if not token:
        raise Exception("CMDBuild no devolvió token tras activar la sesión")
    print(f"[TOKEN] {token}")
    return token



# ================= CONFIGURACIÓN =================
BASE_URL_A = "http://localhost:8080/cmdbuild/services/rest/v3"
BASE_URL_B = "http://localhost:8080/cmdbuild-pre/services/rest/v3"

COOKIE_A = login(BASE_URL_A, "at_devops11@miteco.es", "a")
COOKIE_B = login(BASE_URL_B, "at_devops11@miteco.es", "a")

LIMIT = 10000
OUTPUT_DIR = "./data"
DRY_RUN = False   # True = solo simula, False = aplica cambios

# Crear carpeta de datos si no existe
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ----------- UTILIDADES -----------

def get_headers(token):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "CMDBuild-Authorization": token
    }



def guardar_json(clase, entorno, datos):
    path = os.path.join(OUTPUT_DIR, f"{clase}_{entorno}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    return path


def cargar_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
