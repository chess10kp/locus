# ruff: ignore

from typing import List, Tuple, Union
from gi.repository import Gdk


def parse_key_binding(binding: str) -> Tuple[int, int]:
    """Parse a key binding string into keyval and modifiers.

    Supports basic key bindings like "Ctrl+F", "Alt+Tab", "Shift+Return", etc.

    Args:
        binding: A string like "Ctrl+F" or "Tab"

    Returns:
        Tuple of (keyval, modifiers) that can be used with Gdk
    """
    # Split on '+' to separate modifiers from key
    parts = binding.split("+")
    if len(parts) == 1:
        # No modifiers, just the key
        key_name = parts[0].strip()
        modifiers = 0
    else:
        # Last part is the key, earlier parts are modifiers
        key_name = parts[-1].strip()
        modifier_names = [p.strip() for p in parts[:-1]]

        modifiers = 0
        for mod in modifier_names:
            if mod.lower() == "ctrl":
                modifiers |= Gdk.ModifierType.CONTROL_MASK
            elif mod.lower() == "alt":
                modifiers |= Gdk.ModifierType.ALT_MASK
            elif mod.lower() == "shift":
                modifiers |= Gdk.ModifierType.SHIFT_MASK
            elif mod.lower() == "super":
                modifiers |= Gdk.ModifierType.SUPER_MASK
            elif mod.lower() == "meta":
                modifiers |= Gdk.ModifierType.META_MASK
            else:
                raise ValueError(f"Unknown modifier: {mod}")

    # Get keyval from key name
    key_name_upper = key_name.upper()

    # For letter keys, use lowercase ASCII value to match GTK's behavior with modifiers
    if len(key_name) == 1 and key_name.isalpha():
        keyval = ord(key_name.lower())
    else:
        # First try to get it as a Gdk constant
        gdk_attr = f"KEY_{key_name_upper}"
        if hasattr(Gdk, gdk_attr):
            keyval = getattr(Gdk, gdk_attr)
        else:
            # Handle special cases
            special_keys = {
                "RETURN": Gdk.KEY_Return,
                "ENTER": Gdk.KEY_Return,
                "KP_ENTER": Gdk.KEY_KP_Enter,
                "ESC": Gdk.KEY_Escape,
                "ESCAPE": Gdk.KEY_Escape,
                "DEL": Gdk.KEY_Delete,
                "DELETE": Gdk.KEY_Delete,
                "INS": Gdk.KEY_Insert,
                "INSERT": Gdk.KEY_Insert,
                "HOME": Gdk.KEY_Home,
                "END": Gdk.KEY_End,
                "PGUP": Gdk.KEY_Page_Up,
                "PAGEUP": Gdk.KEY_Page_Up,
                "PGDOWN": Gdk.KEY_Page_Down,
                "PAGEDOWN": Gdk.KEY_Page_Down,
                "UP": Gdk.KEY_Up,
                "DOWN": Gdk.KEY_Down,
                "LEFT": Gdk.KEY_Left,
                "RIGHT": Gdk.KEY_Right,
                "TAB": Gdk.KEY_Tab,
                "BACKSPACE": Gdk.KEY_BackSpace,
                "BKSP": Gdk.KEY_BackSpace,
                "SPACE": Gdk.KEY_space,
            }
            if key_name_upper in special_keys:
                keyval = special_keys[key_name_upper]
            elif len(key_name) == 1:
                # Single character - use ASCII value
                keyval = ord(key_name_upper.lower())
            else:
                raise ValueError(f"Unknown key: {key_name}")

    return keyval, modifiers


def parse_key_bindings(bindings: Union[str, List[str]]) -> List[Tuple[int, int]]:
    """Parse one or more key binding strings into a list of (keyval, modifiers) tuples.

    Args:
        bindings: A single binding string or list of binding strings

    Returns:
        List of (keyval, modifiers) tuples
    """
    if isinstance(bindings, str):
        bindings = [bindings]

    parsed = []
    for binding in bindings:
        parsed.append(parse_key_binding(binding))
    return parsed


def key_matches(
    keyval: int, state: int, parsed_bindings: List[Tuple[int, int]]
) -> bool:
    """Check if a key press matches any of the parsed key bindings.

    Args:
        keyval: The key value from the key press event
        state: The modifier state from the key press event
        parsed_bindings: List of (keyval, modifiers) tuples to check against

    Returns:
        True if the key press matches any binding, False otherwise
    """
    for binding_keyval, binding_modifiers in parsed_bindings:
        if (
            keyval == binding_keyval
            and (state & binding_modifiers) == binding_modifiers
        ):
            return True
    return False
