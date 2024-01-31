from enum import Enum


class AccessLevel(Enum):
    USER = 0
    POWERUSER = 1
    SUPERUSER = 2


class CTX_MODE(Enum):
    SIMPLE = 0
    CONTEXT = 1
