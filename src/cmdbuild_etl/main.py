from . import BASE_URL_A, BASE_URL_B, COOKIE_A, COOKIE_B, LIMIT, DRY_RUN
from . import get_headers, guardar_json, cargar_json
import requests
import json

# ----------- FUNCIONES ETL -----------

# ---------- CLASES ----------





def listar_clases(base_url, cookie):
    resp = requests.get(f"{base_url}/classes", headers=get_headers(cookie))
    resp.raise_for_status()
    return [c["name"] for c in resp.json().get("data", [])]

def extraer_clase(base_url, cookie, clase):
    registros = []
    offset = 0
    while True:
        url = f"{base_url}/classes/{clase}/cards?limit={LIMIT}&offset={offset}"
        resp = requests.get(url, headers=get_headers(cookie))
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        registros.extend(data)
        if len(data) < LIMIT:
            break
        offset += LIMIT
    return registros

def extraer_atributos(base_url, cookie, clase):
    url = f"{base_url}/classes/{clase}/attributes"
    resp = requests.get(url, headers=get_headers(cookie))
    resp.raise_for_status()
    return resp.json().get("data", [])

def limpiar_atributo(attr):
    campos_no_migrables = [
        "id", "owner", "system", "inherited",
        "creationDate", "modificationDate"
    ]
    for c in campos_no_migrables:
        attr.pop(c, None)
    return attr

# ---------- DOMINIOS ----------
def extraer_dominios(base_url, cookie):
    url = f"{base_url}/domains"
    resp = requests.get(url, headers=get_headers(cookie))
    resp.raise_for_status()
    return resp.json().get("data", [])

def calcular_incremental_dominios(dom_a, dom_b):
    """
    dom_a: lista de dominios de origen (lo que quieres aplicar)
    dom_b: lista de dominios existentes en destino (CMDB B)
    Devuelve solo los dominios nuevos o modificados.
    """

    existentes = {d["name"]: normalize_domain(d) for d in dom_b}
    incremental = []

    CAMPOS = ["name", "class1", "class2", "cardinality", "active", "description"]

    for d in dom_a:
        d = normalize_domain(d)
        name = d["name"]

        if name not in existentes:
            print(f"[DOMINIO NUEVO] {name}")
            incremental.append(d)
            continue

        existente = existentes[name]
        cambios = {}

        for campo in CAMPOS:
            if d.get(campo) != existente.get(campo):
                cambios[campo] = d.get(campo)

        if cambios:
            print(f"[DOMINIO MODIFICADO] {name}")
            # Merge completo para no perder datos
            completo = existente.copy()
            completo.update(d)
            incremental.append(completo)

    return incremental

def normalize_domain(d):
    d = dict(d)  # copia

    # Flatten class1 / class2 si vienen como dict
    if isinstance(d.get("class1"), dict):
        d["class1"] = d["class1"].get("_id")

    if isinstance(d.get("class2"), dict):
        d["class2"] = d["class2"].get("_id")

    # Eliminar _id interno (CMDBuild no lo quiere en POST)
    d.pop("_id", None)

    # Defaults
    if "active" not in d:
        d["active"] = True

    return d

def aplicar_dominios(base_url, cookie, incremental):
    """
    Aplica la lista de dominios incremental a la CMDB.
    Si dry_run=True solo imprime lo que se haría.
    """

    headers = get_headers(cookie)

    for d in incremental:
        d = normalize_domain(d)
        name = d["name"]

        print("JSON DOMINIO:", json.dumps(d, indent=2))

        if DRY_RUN:
            print(f"[DRY_RUN] Dominio {name} se aplicaría")
            continue

        # POST para crear, PUT para actualizar
        if "class1" in d and "class2" in d:
            url = f"{base_url}/domains"
            resp = requests.post(url, headers=headers, json=d)
        else:
            url = f"{base_url}/domains/{name}"
            resp = requests.put(url, headers=headers, json=d)

        if not resp.ok:
            print(f"❌ Error dominio {name}: {resp.status_code} {resp.text} {d}")
            sys.exit(1)
        else:
            print(f"✅ Dominio aplicado: {name}")

# ---------- ATRIBUTOS ----------
def calcular_incremental_atributos(attrs_a, attrs_b):
    existentes = {a.get("name") for a in attrs_b}
    nuevos = []
    for attr in attrs_a:
        name = attr.get("name")
        if name not in existentes:
            nuevos.append(attr)
            print(f"[ATRIBUTO NUEVO] {name}")
        else:
            print(f"[SKIP ATRIBUTO EXISTENTE] {name}")
    return nuevos

def aplicar_atributos(base_url, cookie, clase, atributos, attrs_b):
    url = f"{base_url}/classes/{clase}/attributes"
    existentes = {a["name"] for a in attrs_b}
    ALLOWED_TYPES = {"varchar", "text", "integer", "double", "boolean", "date", "timestamp", "reference"}

    for attr in atributos:
        name = attr.get("name")
        atype = attr.get("type")
        if name in existentes:
            print(f"⚠️ NO SE MODIFICA ATRIBUTO EXISTENTE {clase}.{name}")
            continue
        if atype not in ALLOWED_TYPES:
            print(f"⚠️ TIPO NO PERMITIDO {name} ({atype})")
            continue
        attr = limpiar_atributo(attr)
        if DRY_RUN:
            print(f"[DRY_RUN] CREAR ATRIBUTO {clase}.{name} TYPE={atype}")
            continue
        resp = requests.post(url, headers=get_headers(cookie), data=json.dumps(attr))
        if resp.status_code not in (200, 201):
            print(f"❌ Error creando atributo {clase}.{name}: {resp.text}")
        else:
            print(f"✅ Atributo creado {clase}.{name}")

# ---------- REGISTROS ----------
def calcular_incremental(origen, destino):
    def obtener_id(r):
        return r.get("_id")
    destino_dict = {obtener_id(r): r for r in destino}
    incremental = []
    for reg in origen:
        rid = obtener_id(reg)
        if rid not in destino_dict:
            incremental.append(reg)
            print(f"[NUEVO REGISTRO] {reg}")
            continue
        src_date = reg.get("_beginDate")
        dst_date = destino_dict[rid].get("_beginDate")
        if src_date and dst_date and src_date > dst_date:
            incremental.append(reg)
            print(f"[REGISTRO MODIFICADO] {rid} {src_date} > {dst_date}")
        elif src_date is None or dst_date is None:
            if reg != destino_dict[rid]:
                incremental.append(reg)
                print(f"[REGISTRO MODIFICADO] {rid}")
    return incremental

def aplicar_incremental(base_url, cookie, clase, registros, registros_b):
    url = f"{base_url}/classes/{clase}/cards"
    ids_b = {r.get("_id") for r in registros_b}
    for reg in registros:
        rid = reg.get("_id")
        method = "PUT" if rid in ids_b else "POST"
        url_item = f"{url}/{rid}" if method == "PUT" else url
        if DRY_RUN:
            print(f"[DRY_RUN] {method} {clase} Id={rid}")
            continue
        resp = requests.put(url_item, headers=get_headers(cookie), data=json.dumps(reg)) if method=="PUT" else requests.post(url_item, headers=get_headers(cookie), data=json.dumps(reg))
        if resp.status_code not in (200, 201):
            print(f"❌ Error {method} {clase} Id={rid}: {resp.text}")
        else:
            print(f"✅ {method} OK {clase} Id={rid}")

# ---------- RELACIONES ----------
def extraer_relaciones(base_url, cookie, clase):
    url = f"{base_url}/classes/{clase}/relations"
    resp = requests.get(url, headers=get_headers(cookie))
    resp.raise_for_status()
    return resp.json().get("data", [])

def calcular_incremental_relaciones(rel_a, rel_b):
    def clave_rel(r):
        return (r.get("_id_source"), r.get("_id_target"), r.get("type"))
    existentes = {clave_rel(r) for r in rel_b if None not in clave_rel(r)}
    incremental = []
    for r in rel_a:
        key = clave_rel(r)
        if None in key:
            print(f"⚠️ Relación ignorada por campos incompletos: {r} {rel_a}")
            continue
        if key not in existentes:
            incremental.append(r)
            print(f"[NUEVA RELACIÓN] {key}")
    return incremental

def aplicar_relaciones(base_url, cookie, relaciones, registros_b):
    url = f"{base_url}/relations"
    ids_b = {r["_id"] for r in registros_b}
    for rel in relaciones:
        source = rel.get("_id_source")
        target = rel.get("_id_target")
        if not source or not target or "type" not in rel:
            print(f"⚠️ Relación ignorada por campos incompletos: {rel}")
            continue
        if source not in ids_b or target not in ids_b:
            print(f"⚠️ Relación omitida, registro fuente/destino no existe: {rel}")
            continue
        if DRY_RUN:
            print(f"[DRY_RUN] CREAR RELACIÓN {source} -> {target}")
            continue
        resp = requests.post(url, headers=get_headers(cookie), data=json.dumps(rel))
        if resp.status_code not in (200, 201):
            print(f"❌ Error creando relación: {resp.text}")
        else:
            print(f"✅ Relación creada: {source} -> {target}")

import copy

def sincronizar_clase_completa(base_url_a, cookie_a, base_url_b, cookie_b, clase):
    # Obtener definición completa de la clase desde ambos entornos
    resp_a = requests.get(f"{base_url_a}/classes/{clase}", headers=get_headers(cookie_a))
    resp_b = requests.get(f"{base_url_b}/classes/{clase}", headers=get_headers(cookie_b))
    resp_a.raise_for_status()
    resp_b.raise_for_status()

    # ⚡️ Extraer la key "data" donde está la definición real
    clase_a = resp_a.json()["data"]
    clase_b = resp_b.json()["data"]

    # Campos simples y complejos
    campos_simples = [
        "description", "_description_translation", "_description_plural_translation",
        "prototype", "parent", "active", "type", "speciality", "_icon",
        "defaultFilter", "defaultImportTemplate", "defaultExportTemplate",
        "_can_read","_can_create","_can_update","_can_delete",
        "_can_clone","_can_modify","_can_print","_can_search",
        "_can_bulk_update","_can_bulk_delete","_attachment_access_read","_attachment_access_write",
        "_detail_access_read","_detail_access_write",
        "_email_access_read","_email_access_write",
        "_history_access_read","_history_access_write",
        "_note_access_read","_note_access_write",
        "_relation_access_read","_relation_access_write",
        "_schedule_access_read","_schedule_access_write",
        "_relgraph_access","uiRouting_mode","uiRouting_target"
    ]

    campos_dict = ["metadata"]
    campos_list_dict = [
        "dmsCategories", "widgets", "formTriggers", "contextMenuItems",
        "attributeGroups", "lookupValues"
    ]

    necesita_actualizar = False
    clase_b_actualizada = copy.deepcopy(clase_b)

    # Comparar campos simples
    for campo in campos_simples:
        if clase_a.get(campo) != clase_b.get(campo):
            clase_b_actualizada[campo] = clase_a.get(campo)
            necesita_actualizar = True

    # Comparar campos dict
    for campo in campos_dict:
        if clase_a.get(campo, {}) != clase_b.get(campo, {}):
            clase_b_actualizada[campo] = clase_a.get(campo)
            necesita_actualizar = True

    # Comparar campos list/dict
    for campo in campos_list_dict:
        lista_a = clase_a.get(campo, [])
        lista_b = clase_b.get(campo, [])
        if sorted(lista_a, key=lambda x: str(x)) != sorted(lista_b, key=lambda x: str(x)):
            clase_b_actualizada[campo] = clase_a.get(campo)
            necesita_actualizar = True

    if necesita_actualizar:
        print(f"[Clase {clase}] Cambios detectados, actualizando...")
        if DRY_RUN:
            print(f"[DRY_RUN] Actualizar clase {clase} con: {json.dumps(clase_b_actualizada, indent=2)}")
        else:
            resp = requests.put(
                f"{base_url_b}/classes/{clase}",
                headers=get_headers(cookie_b),
                data=json.dumps(clase_b_actualizada)
            )
            if resp.status_code in (200, 201):
                print(f"✅ Clase {clase} actualizada correctamente")
            else:
                print(f"❌ Error actualizando clase {clase}: {resp.text}")
    else:
        print(f"[Clase {clase}] No hay cambios relevantes, no se actualiza")

# ----------- MAIN -----------

def main():
    print("=== CMDBuild ETL COMPLETO ARRANCANDO ===")
    EXCLUDE_CLASSES = {"User", "Role", "Audit", "_System"}

    # ---------- DOMINIOS ----------
    dominios_a = extraer_dominios(BASE_URL_A, COOKIE_A)
    dominios_b = extraer_dominios(BASE_URL_B, COOKIE_B)
    guardar_json("dominios", "A", dominios_a)
    guardar_json("dominios", "B", dominios_b)
    incremental_dom = calcular_incremental_dominios(dominios_a, dominios_b)
    aplicar_dominios(BASE_URL_B, COOKIE_B, incremental_dom)

    # ---------- CLASES ----------
    clases = listar_clases(BASE_URL_A, COOKIE_A)
    print(f"Clases encontradas: {len(clases)}")

    for clase in clases:
        if clase in EXCLUDE_CLASSES:
            continue
        print(f"\n--- Procesando clase: {clase} ---")
        try:
            # SINCRONIZAR PROPIEDADES DE LA CLASE
            sincronizar_clase_completa(BASE_URL_A, COOKIE_A, BASE_URL_B, COOKIE_B, clase)

            # ATRIBUTOS
            attrs_a = extraer_atributos(BASE_URL_A, COOKIE_A, clase)
            attrs_b = extraer_atributos(BASE_URL_B, COOKIE_B, clase)
            guardar_json(clase + "_attrs", "A", attrs_a)
            guardar_json(clase + "_attrs", "B", attrs_b)
            incremental_attrs = calcular_incremental_atributos(attrs_a, attrs_b)
            if incremental_attrs:
                aplicar_atributos(BASE_URL_B, COOKIE_B, clase, incremental_attrs, attrs_b)
            else:
                print("No hay cambios en atributos")

            # REGISTROS
            registros_a = extraer_clase(BASE_URL_A, COOKIE_A, clase)
            registros_b = extraer_clase(BASE_URL_B, COOKIE_B, clase)
            guardar_json(clase, "A", registros_a)
            guardar_json(clase, "B", registros_b)
            incremental = calcular_incremental(registros_a, registros_b)
            print(f"Incremental detectado: {len(incremental)} registros")
            if incremental:
                aplicar_incremental(BASE_URL_B, COOKIE_B, clase, incremental, registros_b)
            else:
                print("No hay cambios")

            # RELACIONES
            relaciones_a = extraer_relaciones(BASE_URL_A, COOKIE_A, clase)
            relaciones_b = extraer_relaciones(BASE_URL_B, COOKIE_B, clase)
            guardar_json(clase + "_rel", "A", relaciones_a)
            guardar_json(clase + "_rel", "B", relaciones_b)
            incremental_rel = calcular_incremental_relaciones(relaciones_a, relaciones_b)
            aplicar_relaciones(BASE_URL_B, COOKIE_B, incremental_rel, registros_b)

        except Exception as e:
            print(f"❌ Error procesando clase {clase}: {e}")

    print("\n=== ETL COMPLETO FINALIZADO ===")

if __name__ == "__main__":
    main()