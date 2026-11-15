"""EnVivo · fase 3 · reserva temporal de asientos.

Una reserva dura cinco minutos y, si nadie la confirma, **se libera sola**.
No debe haber ningún proceso de limpieza: la propia base de datos se encarga.

Las firmas y los valores de retorno **no deben cambiarse**.
"""

import redis

SEGUNDOS_POR_DEFECTO = 300


def clave(evento_id, asiento) -> str:
    """Clave de Redis. Formato: envivo:asiento:<evento>:<asiento>"""
    return f"envivo:asiento:{evento_id}:{asiento}"


def reservar(r: redis.Redis, evento_id, asiento, usuario_id,
             segundos: int = SEGUNDOS_POR_DEFECTO) -> bool:
    """Reserva el asiento si está libre. Devuelve si se ha conseguido.

    Dos usuarios que lo intenten a la vez: **solo uno** puede conseguirlo.
    """
    return bool(r.set(clave(evento_id, asiento), str(usuario_id),
                      nx=True, ex=segundos))


def propietario(r: redis.Redis, evento_id, asiento) -> str | None:
    """Quién tiene reservado el asiento, o None si está libre."""
    return r.get(clave(evento_id, asiento))


def segundos_restantes(r: redis.Redis, evento_id, asiento) -> int:
    """Segundos que quedan. -1 si la reserva es firme, -2 si no hay reserva."""
    resultado = r.ttl(clave(evento_id, asiento))
    if resultado is None:
        return -2

    return int(resultado)


def liberar(r: redis.Redis, evento_id, asiento, usuario_id) -> bool:
    """Libera la reserva, **solo si es de ese usuario**.

    Devuelve True si la ha liberado y False si el asiento estaba libre o
    reservado por otro. Comprobar y borrar en dos comandos desde el cliente
    **no es correcto**: entre uno y otro la reserva puede caducar y pasar a
    otro usuario, y se le borraría la suya.
    """
    script = """
    local propietario = redis.call('GET', KEYS[1])

    if propietario == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end

    return 0
    """
    # script de lua que comprueba que el propietario 
    # coincide con el usuario que quiere liberar la reserva
    # y elimina la clave de redis
    resultado = r.eval(
        script,
        1,
        clave(evento_id, asiento),
        str(usuario_id)
    )

    return bool(resultado)


def confirmar(r: redis.Redis, evento_id, asiento, usuario_id) -> bool:
    """Convierte la reserva en firme: deja de caducar.

    Solo puede hacerlo el propietario. Devuelve si se ha confirmado.
    """
    script = """
    local propietario = redis.call('GET', KEYS[1])

    if propietario == ARGV[1] then
        redis.call('PERSIST', KEYS[1])
        return 1
    end

    return 0
    """
    # PERSIST elimina el tiempo de expiración de de una clave Redis
    resultado = r.eval(
        script,
        1,
        clave(evento_id, asiento),
        str(usuario_id)
    )

    return bool(resultado)
