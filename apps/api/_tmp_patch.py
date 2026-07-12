import pathlib
p = pathlib.Path(r"C:\Users\KOURO\omniagent\apps\api\src\omniagent\agents\emploi\router.py")
src = p.read_text(encoding="utf-8")

old_async_get = '''async def _aget(user_mem, key: str, user_id: str, tenant_id: str):
    """Lecture unifiee : supporte UserMemory (async) et InMemoryUserMemory (sync)."""
    if hasattr(user_mem, "aget"):
        return await user_mem.aget(key, user_id=user_id, tenant_id=tenant_id)
    # InMemoryUserMemory : pas de notion de user/tenant, fallback sur get().
    # En pratique sur stack in-memory on n isole pas par user (limite assumee dev).
    return user_mem.get(key)


async def _aset(user_mem, key: str, value: dict, user_id: str, tenant_id: str):
    if hasattr(user_mem, "aset"):
        await user_mem.aset(key, value, user_id=user_id, tenant_id=tenant_id)
        return
    user_mem.set(key, value)


async def _adelete(user_mem, key: str, user_id: str, tenant_id: str):
    if hasattr(user_mem, "adelete"):
        await user_mem.adelete(key, user_id=user_id, tenant_id=tenant_id)
        return
    user_mem.delete(key)'''

new_async_get = '''async def _aget(user_mem, key: str, user_id: str, tenant_id: str):
    """Lecture unifiee : supporte UserMemory (async) et InMemoryUserMemory (sync).
    Best-effort : toute erreur (DB down, etc.) est capturee et retournee comme
    "profil absent" plutot que de faire tomber l endpoint.
    """
    try:
        if hasattr(user_mem, "aget"):
            return await user_mem.aget(key, user_id=user_id, tenant_id=tenant_id)
        # InMemoryUserMemory : pas de notion de user/tenant, fallback sur get().
        return user_mem.get(key)
    except Exception:
        return None


async def _aset(user_mem, key: str, value: dict, user_id: str, tenant_id: str):
    try:
        if hasattr(user_mem, "aset"):
            await user_mem.aset(key, value, user_id=user_id, tenant_id=tenant_id)
            return
        user_mem.set(key, value)
    except Exception:
        # On laisse remonter : un echec d ecriture doit etre visible a l appelant.
        raise


async def _adelete(user_mem, key: str, user_id: str, tenant_id: str):
    try:
        if hasattr(user_mem, "adelete"):
            await user_mem.adelete(key, user_id=user_id, tenant_id=tenant_id)
            return
        user_mem.delete(key)
    except Exception:
        raise'''

if old_async_get not in src:
    print("OLD NOT FOUND")
else:
    src = src.replace(old_async_get, new_async_get, 1)
    p.write_text(src, encoding="utf-8")
    print("PATCHED router.py (_aget/_aset/_adelete hardened)")
