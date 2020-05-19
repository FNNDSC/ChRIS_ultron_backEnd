
from django.db import models
from django.core.exceptions import ValidationError


class MemoryInt(int):
    def __new__(cls, memory_str, *args, **kwargs):
        """
        Convert memory_str in format of "xMi" or "xGi" to integer in MiB.
        Example: memory_str_to_int("128Mi") -> 128
                 memory_str_to_int("1Gi")   -> 1024
        Throws ValueError if input string is not formatted correctly.
        """
        if isinstance(memory_str, int):
            return super(MemoryInt, cls).__new__(cls, memory_str)
        try:
            suffix = memory_str[-2:]
            if suffix == 'Gi':
                memory_int = int(memory_str[:-2]) * 1024
                assert memory_int > 0
            elif suffix == 'Mi':
                memory_int = int(memory_str[:-2])
                assert memory_int > 0
            else:
                raise ValueError
        except (IndexError, ValueError, AssertionError):
            raise ValueError("Memory format incorrect. Format is xMi or xGi where x is an integer.")
        return  super(MemoryInt, cls).__new__(cls, memory_int)

    def __str__(self):
        return super().__str__() + 'Mi'


class CPUInt(int):
    def __new__(cls, cpu_str, *args, **kwargs):
        """
        Convert cpu_str in format of "xm" to integer in millicores.
        Example: cpu_str_to_int("2000m") -> 2000
        Throws ValueError if input string is not formatted correctly.
        """
        if isinstance(cpu_str, int):
            return super(CPUInt, cls).__new__(cls, cpu_str)
        try:
            cpu_int = int(cpu_str[:-1])
            assert cpu_str[-1] == 'm'
            assert cpu_int > 0
        except (IndexError, ValueError, AssertionError):
            raise ValueError("CPU format incorrect. Format is xm where x is an integer in millicores.")
        return  super(CPUInt, cls).__new__(cls, cpu_int)

    def __str__(self):
        return super().__str__() + 'm'


class MemoryField(models.Field):
    """Stores memory quantity as integer."""
    error_message = "Memory format incorrect. Format is xMi or xGi where x is an integer."

    def get_internal_type(self):
        return "IntegerField"

    def get_prep_value(self, value):
        """Python object --> Query Value."""
        if value is None:
            return None
        return int(value)

    def to_python(self, value):
        """Query value --> Python object."""
        if value is None:
            return None
        try:
            return MemoryInt(value)
        except ValueError:
            raise ValidationError(self.error_message)


class CPUField(models.Field):
    """Stores CPU quantity as integer in millicores."""
    error_message = "CPU format incorrect. Format is xm where x is an integer in millicores."

    def get_internal_type(self):
        return "IntegerField"

    def get_prep_value(self, value):
        """Python object --> Query Value."""
        if value is None:
            return None
        return int(value)

    def to_python(self, value):
        """Query value --> Python object."""
        if value is None:
            return None
        try:
            return CPUInt(value)
        except ValueError:
            raise ValidationError(self.error_message)