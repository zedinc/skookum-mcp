from abc import ABC
from typing import Generic, TypeVar, Union, Any, cast, TypedDict
from sympy import Rational

class MathematicalError(ValueError):
    """Raised when a physically or mathematically nonsense operation is attempted."""
    pass

# --- 1. CARDINALITY DEFINITION ---

class Cardinality(TypedDict, total=False):
    L: int      # Length
    M: int      # Mass
    T: int      # Time
    Theta: int  # Temperature
    I: int      # Electric Current
    N: int      # Amount of Substance
    J: int      # Luminous Intensity

# --- 2. BASE DIMENSIONS ---

class Dimension(ABC):
    CARDINALITY: Cardinality = {
        "L": 0, "M": 0, "T": 0, "Theta": 0, "I": 0, "N": 0, "J": 0
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        declared_card = cls.__dict__.get("CARDINALITY", None)
        if declared_card is None:
            for base in cls.__mro__:
                if base is not cls and hasattr(base, "CARDINALITY"):
                    declared_card = getattr(base, "CARDINALITY")
                    if declared_card is not None:
                        break
        full_card = {
            "L": 0, "M": 0, "T": 0, "Theta": 0, "I": 0, "N": 0, "J": 0
        }
        if declared_card:
            full_card.update(declared_card)
        cls.CARDINALITY = full_card

class Length(Dimension):
    CARDINALITY = {"L": 1}

class Mass(Dimension):
    CARDINALITY = {"M": 1}

class Time(Dimension):
    CARDINALITY = {"T": 1}

class Temperature(Dimension):
    CARDINALITY = {"Theta": 1}

class ElectricCurrent(Dimension):
    CARDINALITY = {"I": 1}

class AmountOfSubstance(Dimension):
    CARDINALITY = {"N": 1}

class LuminousIntensity(Dimension):
    CARDINALITY = {"J": 1}

# --- Derived Dimensions ---

class Area(Dimension):
    CARDINALITY = {"L": 2}

class Volume(Dimension):
    CARDINALITY = {"L": 3}

class Velocity(Dimension):
    CARDINALITY = {"L": 1, "T": -1}

class Acceleration(Dimension):
    CARDINALITY = {"L": 1, "T": -2}

class Force(Dimension):
    CARDINALITY = {"L": 1, "M": 1, "T": -2}

class Pressure(Dimension):
    CARDINALITY = {"L": -1, "M": 1, "T": -2}

class Energy(Dimension):
    CARDINALITY = {"L": 2, "M": 1, "T": -2}

class Power(Dimension):
    CARDINALITY = {"L": 2, "M": 1, "T": -3}

# --- Dimensionless Specializations ---

class Dimensionless(Dimension):
    CARDINALITY = {}

class Angle(Dimensionless):
    CARDINALITY = {}

class Ratio(Dimensionless):
    CARDINALITY = {}

class Percentage(Dimensionless):
    CARDINALITY = {}

T_Dim = TypeVar("T_Dim", bound=Dimension)
T_OtherDim = TypeVar("T_OtherDim", bound=Dimension)

# --- 3. THE UNIT SEAM ---

class Unit(Generic[T_Dim]):
    """
    A physical unit of measurement.
    Embeds its semantic Dimension (T_Dim), runtime Cardinality, and conversion scale factor.
    """
    def __init__(self, name: str, cardinality: Cardinality, scale_factor: Union[int, float, Rational], offset: Union[int, float, Rational] = 0):
        self.name = name
        self.cardinality = cardinality
        self.scale_factor = Rational(scale_factor) if not isinstance(scale_factor, Rational) else scale_factor
        self.offset = Rational(offset) if not isinstance(offset, Rational) else offset

    def __repr__(self) -> str:
        return self.name

    def __mul__(self, other: Any) -> Any:
        if isinstance(other, (int, float, Rational)):
            return Quantity(other, self)
        if isinstance(other, Unit):
            from .engine import combine_cardinalities
            new_card = combine_cardinalities(self.cardinality, other.cardinality, "add")
            new_scale = self.scale_factor * other.scale_factor
            new_name = f"{self.name} * {other.name}"
            return Unit(new_name, new_card, new_scale, 0)
        return NotImplemented

    def __rmul__(self, other: Any) -> Any:
        return self.__mul__(other)

    def __truediv__(self, other: Any) -> Any:
        if isinstance(other, Unit):
            from .engine import combine_cardinalities
            new_card = combine_cardinalities(self.cardinality, other.cardinality, "sub")
            new_scale = self.scale_factor / other.scale_factor
            new_name = f"{self.name} / {other.name}"
            return Unit(new_name, new_card, new_scale, 0)
        return NotImplemented

    def __rtruediv__(self, other: Any) -> Any:
        if isinstance(other, (int, float, Rational)):
            from .engine import combine_cardinalities
            empty_card = Dimension.CARDINALITY
            new_card = combine_cardinalities(empty_card, self.cardinality, "sub")
            new_scale = 1 / self.scale_factor
            new_name = f"1 / {self.name}"
            res_unit = Unit(new_name, new_card, new_scale, 0)
            return Quantity(other, res_unit)
        return NotImplemented

    def __pow__(self, exponent: Any) -> Any:
        if isinstance(exponent, (int, float, Rational)):
            new_card = {k: v * int(exponent) for k, v in self.cardinality.items()}
            new_scale = self.scale_factor ** exponent
            new_name = f"{self.name} ** {exponent}"
            return Unit(new_name, new_card, new_scale, 0)
        return NotImplemented

# --- 4. THE QUANTITY VALUE OBJECT ---

class Quantity(Generic[T_Dim]):
    """
    An immutable scalar physical Quantity value object.
    Represents a numerical value paired with a statically-typed Unit.
    All conversion logic and registry resolutions are delegated to the Converter seam.
    """
    def __init__(self, value: Union[int, float, Rational, str], unit: Union[str, Unit[T_Dim], Any]):
        from .engine import resolve_unit
        
        if hasattr(unit, 'magnitude') and hasattr(unit, 'units'):
            # It's a pint.Quantity!
            value = value * Rational(str(unit.magnitude))
            unit = resolve_unit(str(unit.units))
        elif hasattr(unit, 'units') or 'pint' in str(type(unit)):
            # It's a pint.Unit
            unit = resolve_unit(str(unit))
        elif isinstance(unit, str):
            unit = resolve_unit(unit)
            
        self.unit = unit
        
        # Parse exact mathematical rational value
        import sympy
        if isinstance(value, sympy.Expr):
            parsed_val = value
        elif isinstance(value, str):
            try:
                parsed_val = Rational(value)
            except Exception:
                raise ValueError(f"Invalid or insecure numerical value: {value}")
        elif isinstance(value, (int, float, Rational)):
            parsed_val = Rational(value) if not isinstance(value, Rational) else value
        else:
            try:
                parsed_val = Rational(str(value))
            except Exception:
                raise ValueError(f"Invalid or insecure numerical value: {value}")
                
        # Apply the scaling factor and offset from the unit to store value in SI-base units internally
        self.value = parsed_val * unit.scale_factor + getattr(unit, "offset", 0)

    @property
    def unit_name(self) -> str:
        return self.unit.name

    @property
    def expressed_value(self) -> Rational:
        """Returns the value in the explicit user expressed units (reversing the offset and scale factor)."""
        return (self.value - getattr(self.unit, "offset", 0)) / self.unit.scale_factor

    @property
    def dimensionality(self) -> str:
        """Returns a string representation of the physical dimension."""
        dim_names = {
            'L': '[length]',
            'M': '[mass]',
            'T': '[time]',
            'Theta': '[temperature]',
            'I': '[current]',
            'N': '[substance]',
            'J': '[luminosity]'
        }
        parts = []
        for k, v in self.unit.cardinality.items():
            if v != 0:
                name = dim_names.get(k, f"[{k}]")
                if v == 1:
                    parts.append(name)
                else:
                    parts.append(f"{name} ** {v}")
        if not parts:
            return "dimensionless"
        return " * ".join(parts)

    def to(self, target_unit: Union[str, Unit[T_Dim]]) -> "Quantity[T_Dim]":
        """Converts this quantity to a target unit, delegating entirely to the Converter engine."""
        from .engine import convert_quantity, resolve_unit
        if isinstance(target_unit, str):
            target_unit = resolve_unit(target_unit)
        return convert_quantity(self, target_unit)

    def __repr__(self) -> str:
        return f"{self.expressed_value} {self.unit.name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quantity):
            return False
        # Same dimension check
        if self.unit.cardinality != other.unit.cardinality:
            return False
        import math
        return math.isclose(float(self.value), float(other.value), rel_tol=1e-9, abs_tol=1e-12)

    def __add__(self, other: Any) -> "Quantity[Any]":
        if not isinstance(other, Quantity):
            other = Quantity(other, Unit("dimensionless", Dimensionless.CARDINALITY, 1, 0))

        if self.unit.cardinality != other.unit.cardinality:
            raise TypeError(f"Dimensional Mismatch: Cannot add incompatible dimensions {self.unit.cardinality} and {other.unit.cardinality}")

        # Check coordinate addition rule: cannot add two absolute quantities (non-zero offsets)
        self_offset = getattr(self.unit, "offset", 0)
        other_offset = getattr(other.unit, "offset", 0)
        if self_offset != 0 and other_offset != 0:
            raise TypeError("Nonsense: Cannot add two absolute temperatures (apples to apples coordinate addition is physically invalid).")

        # Result unit uses the non-zero offset coordinate unit if one exists, else self.unit
        if self_offset != 0:
            res_unit = self.unit
        elif other_offset != 0:
            res_unit = other.unit
        else:
            res_unit = self.unit

        # Adding internal absolute values in base units
        new_val = self.value + other.value
        
        # Determine the expressed value for the new Quantity constructor
        expressed_val = (new_val - res_unit.offset) / res_unit.scale_factor
        return Quantity(expressed_val, res_unit)

    def __sub__(self, other: Any) -> "Quantity[Any]":
        if not isinstance(other, Quantity):
            other = Quantity(other, Unit("dimensionless", Dimensionless.CARDINALITY, 1, 0))

        if self.unit.cardinality != other.unit.cardinality:
            raise TypeError(f"Dimensional Mismatch: Cannot subtract incompatible dimensions {self.unit.cardinality} and {other.unit.cardinality}")

        # Coordinate subtraction rule: delta - absolute is invalid
        if self._is_delta_temp() and other._is_absolute_temp():
            raise TypeError("Nonsense: Cannot subtract an absolute temperature from a temperature difference.")

        new_val = self.value - other.value

        # Absolute - Absolute -> relative delta (reference/offset = 0)
        if self._is_absolute_temp() and other._is_absolute_temp():
            from .engine import get_relative_temp_unit_for
            delta_unit = get_relative_temp_unit_for(self.unit)
            expressed_val = (new_val - delta_unit.offset) / delta_unit.scale_factor
            return Quantity(expressed_val, delta_unit)

        # For absolute - delta, result uses absolute unit
        res_unit = self.unit
        expressed_val = (new_val - res_unit.offset) / res_unit.scale_factor
        return Quantity(expressed_val, res_unit)

    def __radd__(self, other: Any) -> "Quantity[Any]":
        return self.__add__(other)

    def __rsub__(self, other: Any) -> "Quantity[Any]":
        if not isinstance(other, Quantity):
            other = Quantity(other, Unit("dimensionless", Dimensionless.CARDINALITY, 1, 0))
        return other.__sub__(self)

    def __neg__(self) -> "Quantity[T_Dim]":
        if self._is_absolute_temp():
            raise TypeError("Nonsense: Cannot negate absolute temperatures.")
        new_val = -self.value
        expressed_val = (new_val - self.unit.offset) / self.unit.scale_factor
        return Quantity(expressed_val, self.unit)

    def __mul__(self, other: Union[int, float, Rational, "Quantity[Any]", Unit[Any]]) -> "Quantity[Any]":
        from sympy import Rational
        if isinstance(other, Unit):
            other = Quantity(1, other)

        if self._is_absolute_temp() or (isinstance(other, Quantity) and other._is_absolute_temp()):
            raise TypeError("Nonsense: Cannot multiply absolute temperatures.")

        if isinstance(other, Quantity):
            from .engine import combine_cardinalities
            new_card = combine_cardinalities(self.unit.cardinality, other.unit.cardinality, "add")
            new_scale = self.unit.scale_factor * other.unit.scale_factor
            new_name = f"{self.unit.name} * {other.unit.name}"
            res_unit = Unit(new_name, new_card, new_scale, 0)
            new_val = (self.value * other.value) / new_scale
            return Quantity(new_val, res_unit)
        else:
            val = Rational(other) if not isinstance(other, Rational) else other
            new_val = self.value * val
            expressed_val = (new_val - self.unit.offset) / self.unit.scale_factor
            return Quantity(expressed_val, self.unit)

    def __rmul__(self, other: Union[int, float, Rational]) -> "Quantity[T_Dim]":
        if self._is_absolute_temp():
            raise TypeError("Nonsense: Cannot multiply absolute temperatures.")
        return self.__mul__(other)

    def __truediv__(self, other: Union[int, float, Rational, "Quantity[Any]", Unit[Any]]) -> "Quantity[Any]":
        from sympy import Rational
        if isinstance(other, Unit):
            other = Quantity(1, other)

        if self._is_absolute_temp() or (isinstance(other, Quantity) and other._is_absolute_temp()):
            raise TypeError("Nonsense: Cannot divide absolute temperatures.")

        if isinstance(other, Quantity):
            from .engine import combine_cardinalities
            new_card = combine_cardinalities(self.unit.cardinality, other.unit.cardinality, "sub")
            new_scale = self.unit.scale_factor / other.unit.scale_factor
            new_name = f"{self.unit.name} / {other.unit.name}"
            res_unit = Unit(new_name, new_card, new_scale, 0)
            new_val = (self.value / other.value) / new_scale
            return Quantity(new_val, res_unit)
        else:
            val = Rational(other) if not isinstance(other, Rational) else other
            new_val = self.value / val
            expressed_val = (new_val - self.unit.offset) / self.unit.scale_factor
            return Quantity(expressed_val, self.unit)

    def __rtruediv__(self, other: Union[int, float, Rational]) -> "Quantity[Any]":
        from sympy import Rational
        if self._is_absolute_temp():
            raise TypeError("Nonsense: Cannot divide absolute temperatures.")
        val = Rational(other) if not isinstance(other, Rational) else other
        
        from .engine import combine_cardinalities
        empty_card = Dimension.CARDINALITY
        new_card = combine_cardinalities(empty_card, self.unit.cardinality, "sub")
        new_scale = 1 / self.unit.scale_factor
        new_name = f"1 / {self.unit.name}"
        res_unit = Unit(new_name, new_card, new_scale, 0)
        
        new_val = (val / self.value) / new_scale
        return Quantity(new_val, res_unit)

    def _is_absolute_temp(self) -> bool:
        # Check if the unit is temperature and is absolute (not relative delta)
        return self.unit.cardinality == Temperature.CARDINALITY and 'delta' not in self.unit.name

    def _is_delta_temp(self) -> bool:
        # Check if the unit is temperature and is relative delta
        return self.unit.cardinality == Temperature.CARDINALITY and 'delta' in self.unit.name
