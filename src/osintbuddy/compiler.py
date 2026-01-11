"""JSON to Python entity compiler for OSINTBuddy plugins.

This module compiles JSON entity definitions into Python Plugin classes,
enabling a JSON-first development workflow where entities can be defined
in a user-friendly format and automatically converted to Python artifacts.

Example JSON input:
    {
        "label": "Example Entity",
        "color": "#22C55E99",
        "icon": "shield-checkered",
        "description": "An example entity",
        "authors": ["OSIB", "Community"],
        "elements": [
            [
                {"type": "text", "label": "Name", "icon": "user", "width": 6},
                {"type": "dropdown", "label": "Category", "icon": "list", "width": 6}
            ],
            {"type": "textarea", "label": "Notes", "icon": "notes", "width": 12}
        ]
    }

Example output:
    from osintbuddy.elements import TextInput, DropdownInput, TextAreaInput
    import osintbuddy as ob


    class ExampleEntity(ob.Plugin):
        version = "1.0.0"
        label = "Example Entity"
        color = "#22C55E99"
        icon = "shield-checkered"
        description = "An example entity"
        elements = [...]

        author = ["OSIB", "Community"]
"""
from __future__ import annotations

import json
import re
from typing import Any
from pathlib import Path


# Map JSON element types to Python class names
ELEMENT_TYPE_MAP = {
    # Inputs
    "text": "TextInput",
    "textarea": "TextAreaInput",
    "dropdown": "DropdownInput",
    "upload": "UploadFileInput",
    # Displays
    "title": "Title",
    "section": "Text",
    "copy-text": "CopyText",
    "copy-code": "CopyCode",
    "json": "Json",
    "img": "Image",
    "image": "Image",
    "video": "Video",
    "pdf": "Pdf",
    "list": "List",
    "table": "Table",
    "empty": "Empty",
}

# Which classes are inputs vs displays
INPUT_CLASSES = {"TextInput", "TextAreaInput", "DropdownInput", "UploadFileInput"}
DISPLAY_CLASSES = {"Title", "Text", "CopyText", "CopyCode", "Json", "Image", "Video", "Pdf", "List", "Table", "Empty"}


def to_pascal_case(label: str) -> str:
    """Convert a label to PascalCase for class names."""
    # Remove non-alphanumeric characters, split on spaces/underscores
    words = re.split(r'[\s_-]+', label)
    return ''.join(word.capitalize() for word in words if word)


def format_value(value: Any, indent: str = "") -> str:
    """Format a Python value for code generation."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        # Escape quotes and newlines
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        # Check if it's a simple list (no dicts) or complex
        if all(isinstance(v, (str, int, float, bool)) for v in value):
            items = ", ".join(format_value(v) for v in value)
            return f"[{items}]"
        # Complex list (e.g., options with dicts) - format on multiple lines
        lines = ["["]
        for v in value:
            lines.append(f"{indent}    {format_value(v, indent + '    ')},")
        lines.append(f"{indent}]")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = ", ".join(f"{format_value(k)}: {format_value(v)}" for k, v in value.items())
        return f"{{{items}}}"
    return repr(value)


def format_options(options: list, base_indent: str) -> str:
    """Format dropdown options with proper indentation."""
    if not options:
        return "[]"

    lines = ["["]
    for opt in options:
        lines.append(f"{base_indent}    {format_value(opt)},")
    lines.append(f"{base_indent}]")
    return "\n".join(lines)


def generate_element_code(element: dict, base_indent: str = "        ") -> tuple[str, bool]:
    """Generate Python code for a single element.

    Returns:
        Tuple of (code_string, is_multiline)
    """
    element_type = element.get("type", "text")
    class_name = ELEMENT_TYPE_MAP.get(element_type, "TextInput")

    # Build kwargs for the element constructor
    kwargs = []
    has_options = False

    # Label is always first
    if label := element.get("label"):
        kwargs.append(f'label={format_value(label)}')

    # Icon
    if icon := element.get("icon"):
        kwargs.append(f'icon={format_value(icon)}')

    # Field type (for type-based transform matching)
    if field_type := element.get("field_type"):
        # Use FieldType enum if it matches a known type
        kwargs.append(f'field_type={format_value(field_type)}')

    # Value (for inputs)
    if "value" in element and element["value"]:
        kwargs.append(f'value={format_value(element["value"])}')

    # Width
    if width := element.get("width"):
        kwargs.append(f'width={width}')

    # Options (for dropdowns) - needs special formatting
    if options := element.get("options"):
        has_options = True
        options_str = format_options(options, base_indent)
        kwargs.append(f'options={options_str}')

    # Placeholder
    if placeholder := element.get("placeholder"):
        kwargs.append(f'placeholder={format_value(placeholder)}')

    if has_options:
        # Multi-line format for elements with options
        kwargs_str = ", ".join(kwargs)
        return f"{class_name}({kwargs_str})", True
    else:
        kwargs_str = ", ".join(kwargs)
        return f"{class_name}({kwargs_str})", False


def generate_elements_code(elements: list, indent: str = "        ") -> str:
    """Generate Python code for the elements list."""
    if not elements:
        return "[]"

    lines = ["["]

    for i, element in enumerate(elements):
        if isinstance(element, list):
            # Row of elements (grouped in same row)
            if len(element) == 1:
                elem_code, _ = generate_element_code(element[0], indent)
                lines.append(f"{indent}[{elem_code}],")
            else:
                lines.append(f"{indent}[")
                for j, elem in enumerate(element):
                    elem_code, is_multiline = generate_element_code(elem, indent + "    ")
                    lines.append(f"{indent}    {elem_code},")
                lines.append(f"{indent}],")
        else:
            # Single element (own row)
            elem_code, _ = generate_element_code(element, indent)
            lines.append(f"{indent}{elem_code},")

    lines.append(f"    ]")
    return "\n".join(lines)


def compile_entity(entity_json: dict | str, version: str = "1.0.0") -> str:
    """Compile a JSON entity definition to Python code.

    Args:
        entity_json: JSON dict or JSON string defining the entity
        version: Version string for the generated Plugin

    Returns:
        Python source code for the Plugin class
    """
    if isinstance(entity_json, str):
        entity_json = json.loads(entity_json)

    # Extract entity metadata
    label = entity_json.get("label", "Unnamed Entity")
    color = entity_json.get("color", "#145070")
    icon = entity_json.get("icon", "atom-2")
    description = entity_json.get("description", "")
    authors = entity_json.get("authors", [])
    elements = entity_json.get("elements", [])
    category = entity_json.get("category", "")
    tags = entity_json.get("tags", [])
    show_in_ui = entity_json.get("show_in_ui", True)
    deps = entity_json.get("deps", [])

    # Generate class name from label
    class_name = to_pascal_case(label)

    # Determine required imports
    used_classes = set()
    for element in elements:
        if isinstance(element, list):
            for elem in element:
                elem_type = elem.get("type", "text")
                used_classes.add(ELEMENT_TYPE_MAP.get(elem_type, "TextInput"))
        else:
            elem_type = element.get("type", "text")
            used_classes.add(ELEMENT_TYPE_MAP.get(elem_type, "TextInput"))

    input_imports = sorted(used_classes & INPUT_CLASSES)
    display_imports = sorted(used_classes & DISPLAY_CLASSES)

    # Build import lines
    all_element_imports = input_imports + display_imports
    imports = []
    if all_element_imports:
        imports.append(f"from osintbuddy.elements import {', '.join(all_element_imports)}")
    imports.append("import osintbuddy as ob")

    # Format author as list
    if isinstance(authors, list):
        if len(authors) == 0:
            author_str = '["Unknown"]'
        else:
            author_str = format_value(authors)
    else:
        author_str = format_value([authors] if authors else ["Unknown"])

    # Generate elements code
    elements_code = generate_elements_code(elements)

    # Build the class
    class_attrs = []
    class_attrs.append(f'    version = {format_value(version)}')
    class_attrs.append(f'    label = {format_value(label)}')
    class_attrs.append(f'    color = {format_value(color)}')
    class_attrs.append(f'    icon = {format_value(icon)}')
    class_attrs.append(f'    description = {format_value(description)}')

    if category:
        class_attrs.append(f'    category = {format_value(category)}')

    if tags:
        class_attrs.append(f'    tags = {format_value(tags)}')

    if not show_in_ui:
        class_attrs.append(f'    show_in_ui = False')

    if deps:
        class_attrs.append(f'    deps = {format_value(deps)}')

    class_attrs.append(f'    elements = {elements_code}')
    class_attrs.append('')  # Empty line before author
    class_attrs.append(f'    author = {author_str}')

    code = f'''{chr(10).join(imports)}



class {class_name}(ob.Plugin):
{chr(10).join(class_attrs)}
'''
    return code


def compile_file(json_path: str | Path, output_path: str | Path | None = None, version: str = "1.0.0") -> str:
    """Compile a JSON entity file to a Python file.

    Args:
        json_path: Path to the JSON entity definition file
        output_path: Optional output path. If not provided, uses same name with .py extension
        version: Version string for the generated Plugin

    Returns:
        The generated Python code
    """
    json_path = Path(json_path)

    with open(json_path, 'r') as f:
        entity_json = json.load(f)

    code = compile_entity(entity_json, version=version)

    if output_path is None:
        output_path = json_path.with_suffix('.py')
    else:
        output_path = Path(output_path)

    with open(output_path, 'w') as f:
        f.write(code)

    return code


def compile_directory(
    json_dir: str | Path,
    output_dir: str | Path | None = None,
    version: str = "1.0.0"
) -> dict[str, str]:
    """Compile all JSON entity files in a directory.

    Args:
        json_dir: Directory containing JSON entity definitions
        output_dir: Optional output directory. If not provided, outputs to same directory
        version: Version string for generated Plugins

    Returns:
        Dict mapping input filenames to generated code
    """
    json_dir = Path(json_dir)
    output_dir = Path(output_dir) if output_dir else json_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for json_file in json_dir.glob("*.json"):
        output_file = output_dir / json_file.with_suffix('.py').name
        code = compile_file(json_file, output_file, version=version)
        results[json_file.name] = code

    return results
