"""Control de deteccion Imou Ranger Dual por Open Platform.

Uso: python imou_control.py estado|activar|desactivar
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HOST = "https://openapi-fk.easy4ip.com"
REFERENCIAS = {"108800": "Movimiento", "18200": "Deteccion humana"}
CANALES = {0: "Movil", 1: "Fija"}


def cargar_env():
    """Lee .env al lado del script sin dependencias externas."""
    archivo = Path(__file__).resolve().parent / ".env"
    if not archivo.is_file():
        return
    for linea in archivo.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, valor = linea.split("=", 1)
        nombre, valor = nombre.strip(), valor.strip()
        if nombre in {"IMOU_APP_ID", "IMOU_APP_SECRET", "IMOU_DEVICE_ID"}:
            os.environ.setdefault(nombre, valor)


def credencial(nombre):
    valor = os.getenv(nombre, "").strip()
    if not valor:
        raise ValueError(f"Falta {nombre}. Configura el archivo .env")
    return valor


def api(endpoint, params, app_id, app_secret):
    instante = int(time.time())
    nonce = str(uuid.uuid4())
    mensaje = f"time:{instante},nonce:{nonce},appSecret:{app_secret}"
    clave = hashlib.sha256(app_secret.encode()).hexdigest().encode()
    firma = base64.b64encode(hmac.new(clave, mensaje.encode(), hashlib.sha256).digest()).decode()
    cuerpo = {
        "system": {"ver": "1.0", "appId": app_id, "sign": firma, "time": instante, "nonce": nonce},
        "id": str(uuid.uuid4()),
        "params": params,
    }
    peticion = urllib.request.Request(
        f"{HOST}/openapi/{endpoint}",
        data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            contenido = json.load(respuesta)
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Error de red en {endpoint}: {error}") from error
    resultado = contenido.get("result", {})
    if str(resultado.get("code")) != "0":
        raise RuntimeError(
            f"{endpoint} rechazado: {resultado.get('code')} - {resultado.get('msg')}"
        )
    return resultado.get("data") or {}


def obtener_producto(token, device_id, app_id, app_secret):
    for pagina in range(1, 11):
        datos = api("listDeviceDetailsByPage", {
            "token": token, "page": pagina, "pageSize": 20, "source": "bindAndShare"
        }, app_id, app_secret)
        dispositivos = datos.get("deviceList", [])
        for dispositivo in dispositivos:
            if dispositivo.get("deviceId") == device_id:
                producto = dispositivo.get("productId")
                if not producto:
                    raise RuntimeError("La camara no devuelve productId")
                return producto
        if len(dispositivos) < 20:
            break
    raise RuntimeError("La camara no aparece entre los dispositivos vinculados")


def leer(token, device_id, product_id, canal, app_id, app_secret):
    datos = api("getIotDeviceProperties", {
        "token": token,
        "deviceList": [{
            "deviceId": device_id, "channelId": canal,
            "productId": product_id, "properties": list(REFERENCIAS)
        }],
    }, app_id, app_secret)
    lista = datos.get("deviceList") or []
    if not lista or not isinstance(lista[0].get("properties"), dict):
        raise RuntimeError(f"El canal {canal} no ha devuelto propiedades validas")
    propiedades = lista[0]["properties"]
    if not all(ref in propiedades for ref in REFERENCIAS):
        raise RuntimeError(f"Faltan propiedades en canal {canal}: {list(propiedades)}")
    return {ref: propiedades[ref] for ref in REFERENCIAS}


def mostrar_estado(token, device_id, product_id, app_id, app_secret):
    for canal, nombre in CANALES.items():
        valores = leer(token, device_id, product_id, canal, app_id, app_secret)
        print(f"Canal {canal} ({nombre}): " + ", ".join(
            f"{REFERENCIAS[ref]}={valores[ref]}" for ref in REFERENCIAS
        ))


def escribir(token, device_id, product_id, canal, valor, app_id, app_secret):
    api("setIotDeviceProperties", {
        "token": token,
        "deviceList": [{
            "deviceId": device_id, "channelId": canal,
            "productId": product_id,
            "properties": {ref: valor for ref in REFERENCIAS},
        }],
    }, app_id, app_secret)


def main():
    parser = argparse.ArgumentParser(description="Control de deteccion Imou Ranger Dual")
    parser.add_argument("accion", choices=["estado", "activar", "desactivar"])
    args = parser.parse_args()
    cargar_env()
    app_id = credencial("IMOU_APP_ID")
    app_secret = credencial("IMOU_APP_SECRET")
    device_id = credencial("IMOU_DEVICE_ID")

    auth = api("accessToken", {}, app_id, app_secret)
    token = auth.get("accessToken")
    if not token:
        raise RuntimeError("La autenticacion no devolvio un accessToken")
    producto = obtener_producto(token, device_id, app_id, app_secret)

    print("\nEstado inicial:")
    mostrar_estado(token, device_id, producto, app_id, app_secret)
    if args.accion == "estado":
        return

    valor = 1 if args.accion == "activar" else 0
    print(f"\nEjecutando {args.accion} para las dos lentes (sin confirmacion)...")
    errores = []
    for canal, nombre in CANALES.items():
        try:
            escribir(token, device_id, producto, canal, valor, app_id, app_secret)
            print(f"Orden enviada a canal {canal} ({nombre}).")
        except Exception as exc:
            errores.append(f"Canal {canal}: {exc}")
            print(f"ERROR en canal {canal}: {exc}")

    time.sleep(3)
    print("\nVerificacion:")
    for canal, nombre in CANALES.items():
        try:
            estado = leer(token, device_id, producto, canal, app_id, app_secret)
            correcto = all(str(x) == str(valor) for x in estado.values())
            print(f"Canal {canal} ({nombre}): {estado} -> {'OK' if correcto else 'NO COINCIDE'}")
            if not correcto:
                errores.append(f"Canal {canal}: estado distinto del solicitado")
        except Exception as exc:
            errores.append(f"Canal {canal}: fallo de lectura: {exc}")
            print(f"Canal {canal}: no se pudo verificar: {exc}")

    if errores:
        print("\nATENCION: no se puede asegurar que toda la vigilancia tenga el estado solicitado.")
        for error in errores:
            print("-", error)
        sys.exit(1)
    print("\nTodas las propiedades verificadas por API.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, KeyboardInterrupt) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
