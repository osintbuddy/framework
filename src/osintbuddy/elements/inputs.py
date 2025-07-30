from typing import List, Any
from osintbuddy.elements.base import BaseInput


class UploadFileInput(BaseInput):
    ...


class TextInput(BaseInput):
    """The TextInput class represents a text input node used
    in the OsintBuddy plugin system.
    value : str
        The value stored in the element.
    icon : str
        The icon to be displayed with the input element.
    default : str
        The default value for the input element.

    Usage Example:
    class Plugin(OBPlugin):
        node = [TextInput(label='Email search', placeholder='Enter email')]
    """
    element_type: str = "text"

    def __init__(self, value="", default="", icon="IconAlphabetLatin", **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value,
            "icon": icon
        }
    def to_dict(self):
        return self._base_entity_element(**self.element)


class TextAreaInput(BaseInput):
    """The TextInput class represents a text input node used
    in the OsintBuddy plugin system.
    value : str
        The value stored in the element.
    icon : str
        The icon to be displayed with the input element.
    default : str
        The default value for the input element.

    Usage Example:
    class Plugin(OBPlugin):
        node = [TextInput(label='Email search', placeholder='Enter email')]
    """
    element_type: str = "textarea"

    def __init__(self, value="", **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value,
        }
    def to_dict(self):
        return self._base_entity_element(**self.element)


class DropdownInput(BaseInput):
    """
    The DropdownInput class represents a dropdown menu node used
    in the OsintBuddy plugin system.
    options : List[any]
        A list of options for the dropdown menu.
    value : str
        The initially selected option in the dropdown menu.

    Usage Example:
    class Plugin(OBPlugin):
        node = [
            DropdownInput(
                options=[{'label': 'Option 1', 'tooltip': 'Hello on hover!'}],
                value='Option 1'
            )
        ]
    """
    element_type: str = "dropdown"

    def __init__(self, options=[], value={'label': '', 'tooltip': '', 'value': ''}, **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "options": options,
            "value": value
        }

    def to_dict(self):
        return self._base_entity_element(**self.element)



class NumberInput(BaseInput):
    ...
