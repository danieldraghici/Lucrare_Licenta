DIRECTION_LEFT = "L"
DIRECTION_RIGHT = "R"
DIRECTION_FORWARD = "F"
DIRECTION_STOP = "S"
DIRECTION_BACKWARD = "B"
MANUAL_MODE = 'manual'
AUTO_MODE = 'auto'

DIRECTION_INTERSECTION_LEFT = "INTERSECTION_LEFT"
DIRECTION_INTERSECTION_RIGHT = "INTERSECTION_RIGHT"
DIRECTION_INTERSECTION_FORWARD = "INTERSECTION_FORWARD"

ACTION_PRIORITY = {
    "stop": 10,
    "accesul_interzis": 8,
    "inainte_sau_la_dreapta": 1,
    "inainte_sau_la_stanga": 1,
    "la_dreapta": 1,
    "la_stanga": 1,
}

COMMAND_MAP = {
    "stop": DIRECTION_RIGHT,
    "accesul_interzis": DIRECTION_STOP,
    "inainte_sau_la_dreapta": DIRECTION_RIGHT,
    "inainte_sau_la_stanga": DIRECTION_LEFT,
    "la_dreapta": DIRECTION_RIGHT,
    "la_stanga": DIRECTION_LEFT,
}