import re
import math


def sanitize_expr(expr):
    """Sanitize and fix common calculator expression errors"""
    # Remove spaces
    expr = expr.replace(" ", "")
    # Fix double operators
    expr = re.sub(r"\+\+", "+", expr)
    expr = re.sub(r"--", "+", expr)
    expr = re.sub(r"\+\-", "-", expr)
    expr = re.sub(r"-\+", "-", expr)
    # Add * for implicit multiplication
    expr = re.sub(r"(\d)\(", r"\1*(", expr)
    expr = re.sub(r"\)(\d)", r")*\1", expr)
    expr = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr)  # e.g., 2pi -> 2*pi
    return expr


def evaluate_calculator(expr):
    """Evaluate calculator expression with proper error handling"""
    if not expr.strip():
        return None, "Empty expression"

    if len(expr) > 100:
        return None, "Expression too long"

    # Check for invalid characters (only allow numbers, operators, parentheses, and common math functions)
    allowed_chars = set("0123456789+-*/().eEpiPIcosintaqrtlg")
    if not all(c in allowed_chars for c in expr):
        return None, "Invalid characters in expression"
    # Prevent power operator for safety
    if "**" in expr:
        return None, "Power operator not allowed"

    try:
        # Use a restricted environment for eval
        safe_dict = {
            "__builtins__": {},
            "pi": 3.141592653589793,
            "e": 2.718281828459045,
            "cos": math.cos,
            "sin": math.sin,
            "tan": math.tan,
            "sqrt": math.sqrt,
            "log": math.log,
            "lg": math.log10,
        }
        result = eval(expr, safe_dict)
        if isinstance(result, complex):
            return None, "Complex numbers not supported"
        return str(result), None
    except SyntaxError:
        return None, "Invalid syntax"
    except NameError:
        return None, "Unknown function or variable"
    except ZeroDivisionError:
        return None, "Division by zero"
    except OverflowError:
        return None, "Result too large"
    except ValueError as e:
        if "math domain" in str(e):
            return None, "Math domain error"
        return None, f"Value error: {e}"
    except Exception as e:
        return None, f"Calculation error: {e}"
