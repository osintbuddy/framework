"""Input elements for OSINTBuddy plugins.

Input elements capture user data in entity forms.
"""
from __future__ import annotations

from typing import Any
from osintbuddy.elements.base import BaseInput


class UploadFileInput(BaseInput):
    """File upload input element.

    Attributes:
        icon: Icon identifier for the element.

    Example:
        UploadFileInput(label="Upload Document", icon="file-upload")
    """
    element_type: str = "upload"

    def __init__(self, value: str = "", icon: str = "IconAlphabetLatin", **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "icon": icon
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class TextInput(BaseInput):
    """Single-line text input element.

    Attributes:
        value: The current value of the input.
        icon: Icon identifier for the element.
        placeholder: Placeholder text shown when empty.

    Example:
        TextInput(label="Email", icon="mail", field_type=FieldType.EMAIL)
    """
    element_type: str = "text"

    def __init__(self, value: str = "", icon: str = "IconAlphabetLatin", **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value,
            "icon": icon
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class TextAreaInput(BaseInput):
    """Multi-line text area input element.

    Attributes:
        value: The current value of the textarea.

    Example:
        TextAreaInput(label="Notes", field_type=FieldType.NOTES)
    """
    element_type: str = "textarea"

    def __init__(self, value: str = "", **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value,
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class DropdownInput(BaseInput):
    """Dropdown selection input element.

    Attributes:
        options: List of option dictionaries with 'label' and optional 'tooltip'.
        value: The currently selected option.

    Example:
        DropdownInput(
            label="Category",
            options=[
                {'label': 'Personal', 'tooltip': 'Personal accounts'},
                {'label': 'Business'}
            ],
            value={'label': 'Personal'}
        )
    """
    element_type: str = "dropdown"

    def __init__(
        self,
        options: list[dict[str, Any]] | None = None,
        value: dict[str, Any] | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.element = {
            "options": options or [],
            "value": value or {'label': '', 'tooltip': '', 'value': ''}
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)
