"""EnVivo · fase 3 · usuarios y sesiones.

De cada usuario se guarda: nombre completo, nombre de usuario, contraseña
(puede estar en plano), privilegios (entero positivo) y el token de sesión si
tiene una activa. Las sesiones duran **un mes** y al caducar desaparecen solas.

Las firmas y los valores de retorno **no deben cambiarse**.
"""

import secrets
import redis

DURACION_SESION = 30 * 24 * 60 * 60      # un mes
SIN_ACCESO = -1


def clave_usuario(usuario: str) -> str:
    """Formato: envivo:usuario:<usuario>"""
    return f"envivo:usuario:{usuario}"


def clave_sesion(token: str) -> str:
    """Formato: envivo:sesion:<token>"""
    return f"envivo:sesion:{token}"


# ── Gestión de usuarios (CRUD) ──────────────────────────────────────────────

def crear_usuario(r: redis.Redis, usuario: str, nombre: str,
                  password: str, privilegios: int) -> bool:
    """Crea el usuario si no existe. Devuelve si se ha creado."""
    return bool(r.hset(clave_usuario(usuario), mapping={
        "nombre": nombre,
        "password": password,
        "privilegios": str(privilegios),
    }, nx=True))


def obtener_usuario(r: redis.Redis, usuario: str) -> dict | None:
    """Todos los campos del usuario, o None si no existe.

    `privilegios` debe venir como **entero**, no como cadena.
    """
    datos = r.hgetall(clave_usuario(usuario))
    return datos if datos else None


def actualizar_usuario(r: redis.Redis, usuario: str, **campos) -> bool:
    """Modifica los campos indicados y **solo** esos.

    Devuelve False si el usuario no existe.
    """
    k = clave_usuario(usuario)
    if not r.exists(k):
        return False
    if campos:
        r.hset(k, mapping={f: str(v) for f, v in campos.items()})
    return True



def borrar_usuario(r: redis.Redis, usuario: str) -> bool:
    """Borra el usuario. Si tenía sesión abierta, debe quedar cerrada."""
    k = clave_usuario(usuario)
    token = r.hget(k, "token")
    borrado = r.delete(k)
    if token:
        r.delete(clave_sesion(token))
    return bool(borrado)
    

# ── Sesiones ────────────────────────────────────────────────────────────────

def login(r: redis.Redis, usuario: str, password: str) -> tuple[int, str | None]:
    """Comprueba las credenciales y abre una sesión.

    Devuelve `(privilegios, token)` si son correctas y `(-1, None)` si no.
    Un login nuevo debe invalidar la sesión anterior del mismo usuario.
    """
    datos = r.hgetall(clave_usuario(usuario)) # credenciales
    if not datos or datos.get("password") != password:
        return (-1, None)

    token_viejo = datos.get("token") # si había borrar el antiguo
    if token_viejo:
        r.delete(clave_sesion(token_viejo))
    
    token = secrets.token_urlsafe(32) #secrets
    r.set(clave_sesion(token), usuario, ex=DURACION_SESION)
    r.hset(clave_usuario(usuario), "token", token)
    return (int(datos["privilegios"]), token) 
    


def login_por_token(r: redis.Redis, token: str) -> int:
    """Privilegios asociados al token, o -1 si no vale.

    Un token cuya sesión ha caducado devuelve -1, igual que uno inventado.
    """
    # TODO
    raise NotImplementedError


def logout(r: redis.Redis, token: str) -> bool:
    """Cierra la sesión. Devuelve si había una sesión que cerrar."""
    # TODO
    raise NotImplementedError


def segundos_de_sesion(r: redis.Redis, token: str) -> int:
    """Segundos que le quedan a la sesión. -2 si no existe."""
    # TODO
    raise NotImplementedError
