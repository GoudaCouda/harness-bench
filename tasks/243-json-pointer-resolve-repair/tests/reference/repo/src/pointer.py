"""RFC 6901 JSON Pointer resolver for mill documents."""


def resolve_pointer(document, pointer):
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError("pointer")
    current = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit():
                raise ValueError("missing")
            index = int(token)
            if index < 0 or index >= len(current):
                raise ValueError("missing")
            current = current[index]
        elif isinstance(current, dict):
            if token not in current:
                raise ValueError("missing")
            current = current[token]
        else:
            raise ValueError("missing")
    return current
