# Elements

Elements are the building blocks of entity forms. They define what data an entity can hold and how it's displayed in the UI. Elements are divided into **inputs** (for user data entry) and **displays** (for read-only content).

## Element Basics

All elements share common attributes:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element identifier and display label |
| `width` | `int` | `12` | Grid width (1-12, where 12 is full width) |

Import elements from `osintbuddy.elements`:

```python
from osintbuddy.elements import TextInput, CopyText, Title, Image
```

## Layout

Elements are arranged using a grid system. Use a list of lists for multi-column layouts:

```python
elements = [
    # Full width (default)
    TextInput(label="Full Name"),

    # Two columns
    [
        TextInput(label="First Name", width=6),
        TextInput(label="Last Name", width=6),
    ],

    # Three columns
    [
        TextInput(label="City", width=4),
        TextInput(label="State", width=4),
        TextInput(label="Country", width=4),
    ],

    # Asymmetric layout
    [
        Image(label="Avatar", width=3),
        Title(label="Display Name", width=9),
    ],
]
```

---

## Input Elements

Input elements capture user data and support the `field_type` attribute for semantic typing.

### TextInput

A single-line text field.

```python
from osintbuddy.elements import TextInput
from osintbuddy.types import FieldType

TextInput(
    label="Email",
    icon="mail",
    value="",                       # Default value
    field_type=FieldType.EMAIL,     # Semantic type
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Field label |
| `icon` | `str` | `None` | Icon identifier |
| `value` | `str` | `""` | Default value |
| `field_type` | `FieldType` | `None` | Semantic field type |
| `width` | `int` | `12` | Grid width |

### TextAreaInput

A multi-line text area for longer content.

```python
from osintbuddy.elements import TextAreaInput

TextAreaInput(
    label="Notes",
    value="",
    field_type=FieldType.NOTES,
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Field label |
| `value` | `str` | `""` | Default value |
| `field_type` | `FieldType` | `None` | Semantic field type |
| `width` | `int` | `12` | Grid width |

### DropdownInput

A dropdown select with predefined options.

```python
from osintbuddy.elements import DropdownInput

DropdownInput(
    label="Status",
    options=[
        {"label": "Active", "value": "active"},
        {"label": "Inactive", "value": "inactive"},
        {"label": "Unknown", "value": "unknown"},
    ],
    value="unknown",  # Default selection
    width=6,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Field label |
| `options` | `list[dict]` | `[]` | Options with `label` and `value` |
| `value` | `str` | `""` | Default selected value |
| `width` | `int` | `12` | Grid width |

### UploadFileInput

A file upload field.

```python
from osintbuddy.elements import UploadFileInput

UploadFileInput(
    label="Document",
    icon="file-upload",
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Field label |
| `icon` | `str` | `None` | Icon identifier |

---

## Display Elements

Display elements render read-only content in various formats.

### Title

A prominent title/heading display.

```python
from osintbuddy.elements import Title

Title(
    label="Organization Name",
    value="Acme Corporation",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `value` | `str` | `""` | Display value |
| `width` | `int` | `12` | Grid width |

### Text

A simple text display with optional icon.

```python
from osintbuddy.elements import Text

Text(
    label="Description",
    value="A brief description here",
    icon="info-circle",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `value` | `str` | `""` | Display value |
| `icon` | `str` | `None` | Icon identifier |
| `width` | `int` | `12` | Grid width |

### CopyText

Text with a copy-to-clipboard button.

```python
from osintbuddy.elements import CopyText

CopyText(
    label="API Key",
    value="sk-abc123...",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `value` | `str` | `""` | Copyable value |
| `width` | `int` | `12` | Grid width |

### CopyCode

Monospace code display with copy functionality.

```python
from osintbuddy.elements import CopyCode

CopyCode(
    label="Command",
    value="curl -X GET https://api.example.com",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `value` | `str` | `""` | Code content |
| `width` | `int` | `12` | Grid width |

### Json

Formatted JSON display with syntax highlighting.

```python
from osintbuddy.elements import Json

Json(
    label="Response Data",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `width` | `int` | `12` | Grid width |

### Image

An image display element.

```python
from osintbuddy.elements import Image

Image(
    label="Screenshot",
    width=6,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `width` | `int` | `12` | Grid width |

### Video

A video player element.

```python
from osintbuddy.elements import Video

Video(
    label="Recording",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `width` | `int` | `12` | Grid width |

### Pdf

A PDF viewer element.

```python
from osintbuddy.elements import Pdf

Pdf(
    label="Document",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `width` | `int` | `12` | Grid width |

### List

A list/array display.

```python
from osintbuddy.elements import List

List(
    label="Tags",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `width` | `int` | `12` | Grid width |

### Table

A tabular data display.

```python
from osintbuddy.elements import Table

Table(
    label="DNS Records",
    width=12,
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | Required | Element label |
| `width` | `int` | `12` | Grid width |

### Empty

A spacer element for layout purposes.

```python
from osintbuddy.elements import Empty

Empty(
    width=3,  # Creates empty space
)
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | `12` | Grid width |

---

## Field Types

Add semantic meaning to input elements using `field_type`:

```python
from osintbuddy.elements import TextInput
from osintbuddy.types import FieldType

elements = [
    TextInput(label="Email", field_type=FieldType.EMAIL),
    TextInput(label="Phone", field_type=FieldType.PHONE),
    TextInput(label="IP Address", field_type=FieldType.IP_ADDRESS),
    TextInput(label="Domain", field_type=FieldType.DOMAIN),
]
```

Field types enable type-based transform matching. See [Field Types](types.md) for the complete list.

---

## Serialization

Elements are converted to dictionaries for JSON serialization:

```python
element = TextInput(label="Email", icon="mail", field_type=FieldType.EMAIL)
data = element.to_dict()

# Result:
{
    "type": "text",
    "label": "Email",
    "icon": "mail",
    "value": "",
    "field_type": "email",
    "width": 12,
}
```

---

## Complete Example

A comprehensive entity using various elements:

```python
from osintbuddy import Plugin
from osintbuddy.elements import (
    TextInput,
    TextAreaInput,
    DropdownInput,
    Title,
    Text,
    CopyText,
    CopyCode,
    Image,
    Json,
    Table,
    Empty,
)
from osintbuddy.types import FieldType


class InvestigationReport(Plugin):
    version = "1.0.0"
    label = "Investigation Report"
    icon = "file-report"
    color = "#6366F1"
    category = "Reports"

    elements = [
        # Header row with image and title
        [
            Image(label="Logo", width=2),
            Title(label="Report Title", width=10),
        ],

        # Metadata row
        [
            TextInput(label="Case ID", icon="hash", width=4),
            DropdownInput(
                label="Status",
                options=[
                    {"label": "Open", "value": "open"},
                    {"label": "In Progress", "value": "in_progress"},
                    {"label": "Closed", "value": "closed"},
                ],
                value="open",
                width=4,
            ),
            TextInput(label="Priority", width=4),
        ],

        # Subject information
        Text(label="Subject", icon="user"),
        [
            TextInput(
                label="Subject Name",
                field_type=FieldType.PERSON_NAME,
                width=6
            ),
            TextInput(
                label="Subject Email",
                field_type=FieldType.EMAIL,
                width=6
            ),
        ],

        # URLs and references
        CopyText(label="Primary URL", field_type=FieldType.URL),
        CopyCode(label="API Endpoint"),

        # Detailed content
        TextAreaInput(
            label="Summary",
            field_type=FieldType.NOTES,
        ),

        # Structured data
        Json(label="Raw Data"),
        Table(label="Related Entities"),

        # Spacer for layout
        [
            Empty(width=8),
            TextInput(label="Analyst", width=4),
        ],
    ]
```

---

## JSON Definition

Elements can be defined in JSON for the compiler:

```json
{
  "elements": [
    {
      "type": "text",
      "label": "Email",
      "icon": "mail",
      "field_type": "email",
      "width": 12
    },
    [
      {
        "type": "text",
        "label": "First Name",
        "width": 6
      },
      {
        "type": "text",
        "label": "Last Name",
        "width": 6
      }
    ],
    {
      "type": "dropdown",
      "label": "Status",
      "options": [
        {"label": "Active", "value": "active"},
        {"label": "Inactive", "value": "inactive"}
      ],
      "width": 6
    },
    {
      "type": "textarea",
      "label": "Notes"
    },
    {
      "type": "title",
      "label": "Section Header"
    },
    {
      "type": "copy_text",
      "label": "URL"
    },
    {
      "type": "image",
      "label": "Screenshot"
    }
  ]
}
```

Type mapping:

| JSON type | Python class |
|-----------|-------------|
| `text` | `TextInput` |
| `textarea` | `TextAreaInput` |
| `dropdown` | `DropdownInput` |
| `upload` | `UploadFileInput` |
| `title` | `Title` |
| `text_display` | `Text` |
| `copy_text` | `CopyText` |
| `copy_code` | `CopyCode` |
| `json` | `Json` |
| `image` | `Image` |
| `video` | `Video` |
| `pdf` | `Pdf` |
| `list` | `List` |
| `table` | `Table` |
| `empty` | `Empty` |

## Next Steps

- [Field Types](types.md) - Complete list of semantic field types
- [Plugins](plugins.md) - Using elements in entity definitions
- [Transforms](transforms.md) - Accessing element data in transforms
