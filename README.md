poetry run python -m cmdbuild_etl.main
# CMDbuild-DatamodelSync
## CMDBuild-DatamodelSync

Herramienta para sincronizar el **modelo de datos (clases, atributos, dominios y relaciones)** entre dos entornos CMDBuild (por ejemplo, DEV → PRE → PROD).

El objetivo es poder versionar y automatizar la sincronización del modelo de CMDBuild como si fuera *Infrastructure as Code*.

---

# 🚀 Características

* ✅ Exportación del modelo de datos desde CMDBuild (clases, atributos, dominios)
* ✅ Cálculo de **incremental** (solo cambios nuevos o modificados)
* ✅ Aplicación automática del modelo en otro entorno
* ✅ Soporte para **DRY-RUN** (simulación sin aplicar cambios)
* ✅ Persistencia de JSON para trazabilidad
* ✅ Autenticación vía REST API CMDBuild

---

# 🧩 Arquitectura


---

# 🔐 Configuración

Editar variables en `main.py`:

```python
BASE_URL_A = "http://cmdbuild-dev:8080/cmdbuild/services/rest/v3"
BASE_URL_B = "http://cmdbuild-pre:8080/cmdbuild/services/rest/v3"

USERNAME = "usuario@dominio"
PASSWORD = "password"

DRY_RUN = True   # True = solo simula, False = aplica cambios
OUTPUT_DIR = "./data"
```

---

# ▶️ Uso

## 1️⃣ Exportar modelo del entorno origen

```bash
python main.py export
```

Se generan archivos:

```text
./data/classes_a.json
./data/domains_a.json
./data/attributes_a.json
```

---

## 2️⃣ Exportar modelo del entorno destino

```bash
python main.py export-target
```

---

## 3️⃣ Calcular incremental

```bash
python main.py diff
```

Resultado:

* Solo clases, atributos o dominios nuevos/modificados

---

## 4️⃣ Aplicar cambios (sin DRY_RUN)

```bash
python main.py apply
```

⚠️ Recomendado probar siempre con `DRY_RUN=True` primero.

---

# 🧪 DRY RUN (modo seguro)

```python
DRY_RUN = True
```

Salida ejemplo:

```text
[DRY_RUN] Crear clase: ca_servidor
[DRY_RUN] Crear dominio: servidor_a_red
```

---

# 🗂️ Estructura del proyecto

```text
cmdbuild-datamodel-sync/
│
├── src/
│   ├── main.py
│   ├── export.py
│   ├── diff.py
│   ├── apply.py
│   └── utils.py
│
├── data/
│   ├── classes_a.json
│   ├── classes_b.json
│   ├── domains_a.json
│   └── domains_b.json
│
└── README.md
```

---

# ⚠️ Consideraciones importantes

### 🔹 Dominios CMDBuild

* Para crear dominios es obligatorio:

```json
{
  "name": "servidor_a_red",
  "class1": "ca_servidor",
  "class2": "ca_red",
  "cardinality": "1:N",
  "active": true
}
```

* No enviar `_id` en POST
* `class1` y `class2` deben ser IDs de clase (no objetos JSON)

---

### 🔹 Clases y atributos

* Los atributos deben crearse **después** de la clase
* Algunos tipos requieren configuración extra (`reference`, `lookup`, `foreignkey`)

---

# 🧠 Buenas prácticas

* Versionar los JSON exportados en Git
* Ejecutar primero en PRE
* Usar DRY_RUN en PROD
* Documentar cambios de modelo (ADR o changelog)

---

# 🛠️ Roadmap

* [ ] Soporte rollback automático
* [ ] Modo GitOps (PR basado en JSON diff)
* [ ] CLI con Typer / Click
* [ ] Docker container
* [ ] UI Web diff viewer
* [ ] Integración Flyway/Liquibase-like

---

# 👤 Autor

**Gustavo Castro**
Consultor DevOps / CMDBuild Automation

---

# 📜 Licencia

MIT License
