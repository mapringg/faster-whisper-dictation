import enum
from transitions import Machine

class States(enum.Enum):
    READY        = 1
    RECORDING    = 2
    TRANSCRIBING = 3
    REPLAYING    = 4

transitions = [
    {'trigger':'start_recording'     ,'source': States.READY        ,'dest': States.RECORDING    },
    {'trigger':'finish_recording'    ,'source': States.RECORDING    ,'dest': States.TRANSCRIBING },
    {'trigger':'finish_transcribing' ,'source': States.TRANSCRIBING ,'dest': States.REPLAYING    },
    {'trigger':'finish_replaying'    ,'source': States.REPLAYING    ,'dest': States.READY        },
]

def create_state_machine():
    """Create and configure the state machine."""
    return Machine(
        states=States,
        transitions=transitions,
        send_event=True,
        ignore_invalid_triggers=True,
        initial=States.READY
    )
