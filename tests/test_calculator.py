"""Unit tests for calculator functionality"""

import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculator import sanitize_expr, evaluate_calculator


class TestCalculator:
    """Test calculator functions"""

    def test_sanitize_expr_basic(self):
        """Test basic expression sanitization"""
        assert sanitize_expr("2 + 2") == "2+2"
        assert sanitize_expr("2 - 2") == "2-2"
        assert sanitize_expr("2 * 2") == "2*2"
        assert sanitize_expr("2 / 2") == "2/2"

    def test_sanitize_expr_double_operators(self):
        """Test fixing double operators"""
        assert sanitize_expr("2++2") == "2+2"
        assert sanitize_expr("2--2") == "2+2"
        assert sanitize_expr("2+-2") == "2-2"
        assert sanitize_expr("2-+2") == "2-2"

    def test_sanitize_expr_implicit_multiplication(self):
        """Test adding implicit multiplication"""
        assert sanitize_expr("2(3+4)") == "2*(3+4)"
        assert sanitize_expr("(3+4)5") == "(3+4)*5"
        assert sanitize_expr("2pi") == "2*pi"
        assert sanitize_expr("3cos(0)") == "3*cos(0)"

    def test_evaluate_calculator_basic(self):
        """Test basic arithmetic evaluation"""
        result, error = evaluate_calculator("2+2")
        assert error is None
        assert result == "4"

        result, error = evaluate_calculator("10-3")
        assert error is None
        assert result == "7"

        result, error = evaluate_calculator("3*4")
        assert error is None
        assert result == "12"

        result, error = evaluate_calculator("15/3")
        assert error is None
        assert result == "5.0"

    def test_evaluate_calculator_constants(self):
        """Test mathematical constants"""
        result, error = evaluate_calculator("pi")
        assert error is None
        assert result == "3.141592653589793"

        result, error = evaluate_calculator("e")
        assert error is None
        assert result == "2.718281828459045"

    def test_evaluate_calculator_functions(self):
        """Test mathematical functions"""
        result, error = evaluate_calculator("cos(0)")
        assert error is None
        assert result == "1.0"

        result, error = evaluate_calculator("sin(0)")
        assert error is None
        assert result == "0.0"

        result, error = evaluate_calculator("sqrt(16)")
        assert error is None
        assert result == "4.0"

        result, error = evaluate_calculator("log(10)")
        assert error is None
        assert result == "2.302585092994046"

        result, error = evaluate_calculator("lg(100)")
        assert error is None
        assert result == "2.0"

    def test_evaluate_calculator_complex_expressions(self):
        """Test complex mathematical expressions"""
        result, error = evaluate_calculator("2+3*4")
        assert error is None
        assert result == "14"

        result, error = evaluate_calculator("(2+3)*4")
        assert error is None
        assert result == "20"

        result, error = evaluate_calculator("2*pi")
        assert error is None
        assert result == "6.283185307179586"

    def test_evaluate_calculator_error_cases(self):
        """Test error handling"""
        # Empty expression
        result, error = evaluate_calculator("")
        assert result is None
        assert error == "Empty expression"

        # Too long expression
        result, error = evaluate_calculator("1" * 101)
        assert result is None
        assert error == "Expression too long"

        # Invalid characters
        result, error = evaluate_calculator("2+@")
        assert result is None
        assert error == "Invalid characters in expression"

        # Power operator not allowed
        result, error = evaluate_calculator("2**3")
        assert result is None
        assert error == "Power operator not allowed"

        # Division by zero
        result, error = evaluate_calculator("1/0")
        assert result is None
        assert error == "Division by zero"

        # Invalid syntax
        result, error = evaluate_calculator("2+")
        assert result is None
        assert error == "Invalid syntax"

        # Unknown function
        result, error = evaluate_calculator("unknown(2)")
        assert result is None
        assert error == "Invalid characters in expression"

        # Math domain error
        result, error = evaluate_calculator("sqrt(-1)")
        assert result is None
        assert error == "Math domain error"

    def test_evaluate_calculator_complex_numbers(self):
        """Test that complex numbers are not supported"""
        result, error = evaluate_calculator("sqrt(-1)")
        assert result is None
        assert error == "Math domain error"
