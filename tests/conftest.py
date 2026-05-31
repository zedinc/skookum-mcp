import pytest
from src.types import Quantity

@pytest.fixture
def make_quantity():
    """
    Factory fixture (Section 3.1 of Best Practices Guide) that returns a function 
    to create clean physical Quantity instances with customized attributes.
    """
    def _make_quantity(value, unit):
        return Quantity(value, unit)
    return _make_quantity
