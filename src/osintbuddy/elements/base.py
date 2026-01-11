"""Base element classes for OSINTBuddy plugins.

Elements are the building blocks of entity definitions, providing
input fields and display components for the UI.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from osintbuddy.types import FieldType


class BaseElement(object):
    """
    The BaseElement class represents a basic building block used in OsintBuddy
    plugins. It is designed to implement the base styles used
    in other nodes that can render a nodes element
    with a specific element type, label, and style on the OSINTbuddy UI.

    Attributes:
        label: A string representing the label for the node.
        style: A dictionary representing the react style properties for the node.
        placeholder: A string representing the placeholder for the node.
        width: The grid width of the element (1-12, where 12 is full width).
        field_type: The semantic type of data this element holds (e.g., email, ip_address).
                   Used for type-based transform matching.
    """
    element_type: str

    def __init__(self, **kwargs):
        self.label: str = kwargs.get('label', '')
        self.width: int | None = kwargs.get('width')
        self.field_type: str | None = None

        # Handle field_type - can be string or FieldType enum
        if ft := kwargs.get('field_type'):
            if hasattr(ft, 'value'):
                self.field_type = ft.value
            else:
                self.field_type = str(ft)

    def _base_entity_element(self, **kwargs) -> dict:
        """Build base element dictionary for serialization."""
        base_element = {}
        if kwargs:
            base_element = {
                k: v for k, v in kwargs.items()
            }
        base_element['label'] = self.label
        base_element['type'] = self.element_type
        if self.width is not None:
            base_element['width'] = self.width
        if self.field_type is not None:
            base_element['field_type'] = self.field_type
        return base_element

    def to_dict(self) -> dict[str, str]:
        """Convert element to dictionary representation."""
        return self._base_entity_element()


class BaseInput(BaseElement):
    """Base class for input elements (text fields, dropdowns, etc.)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class BaseDisplay(BaseElement):
    """Base class for display elements (titles, images, etc.)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
