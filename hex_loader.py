class HexLoaderError(Exception):
    pass


def load(path: str) -> bytes:
    """
    Lit un fichier .hex et retourne les octets sous forme de bytes.

    Raises
    ------
    HexLoaderError  si un token n'est pas un octet hex valide (0x00–0xFF)
    FileNotFoundError si le fichier est introuvable
    """
    result = []

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            # supprimer les commentaires et les espaces superflus
            line = raw_line.split(";")[0].strip()
            if not line:
                continue

            for token in line.split():
                try:
                    value = int(token, 16)
                except ValueError:
                    raise HexLoaderError(
                        f"Ligne {lineno} : token invalide '{token}' "
                        f"(attendu : octet hexadécimal 00–FF)"
                    )
                if not (0x00 <= value <= 0xFF):
                    raise HexLoaderError(
                        f"Ligne {lineno} : valeur {token!r} hors plage (00–FF)"
                    )
                result.append(value)

    return bytes(result)


def load_into_cache(path: str, cache, base_address: int = 0) -> int:
    """
    Charge le programme dans le cache à partir de base_address.
    """
    program = load(path)
    for i, byte in enumerate(program):
        cache.write(base_address + i, byte)
    return len(program)


def load_into_ram(path: str, ram, base_address: int = 0) -> int:
    """
    Charge le programme en RAM à partir de base_address.
    Retourne le nombre d'octets chargés.
    """
    program = load(path)
    ram.write_block(base_address, program)
    return len(program)


def load_into_disc(path: str, disc, base_address: int = 0) -> int:
    """
    Charge le programme sur le disque à partir de base_address.
    Retourne le nombre d'octets chargés.
    """
    program = load(path)
    disc.write(base_address, program)
    return len(program)