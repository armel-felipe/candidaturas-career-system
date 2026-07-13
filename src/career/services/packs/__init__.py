PACK_REGISTRY = {}

def register(name):
    def decorator(func):
        PACK_REGISTRY[name] = func
        return func
    return decorator

def build_pack(name, application_id, db):
    builder = PACK_REGISTRY.get(name)
    if not builder:
        raise ValueError(f"Unknown pack: {name}")
    return builder(application_id, db)

def list_packs():
    return list(PACK_REGISTRY.keys())


from . import cv_input_pack
from . import feras_input_pack
from . import cover_letter_pack
from . import habilidades_pack
from . import fit_map_seed
