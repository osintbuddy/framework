#   -------------------------------------------------------------
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""OSINTBuddy - Open Source Intelligence Plugin Framework

This package provides the core infrastructure for building OSINT plugins:
- Entity definitions with rich metadata and field types
- Transform decorators with dependency management
- Result types for subgraphs, custom edges, and file attachments
- JSON to Python entity compilation
- Structured CLI output for reliable parsing

Example usage:
    from osintbuddy import Plugin, transform, Entity, Edge, File
    from osintbuddy.elements import TextInput
    from osintbuddy.types import FieldType

    class EmailEntity(Plugin):
        version = "1.0.0"
        label = "Email"
        category = "Identity"
        elements = [
            TextInput(label="Email", field_type=FieldType.EMAIL),
        ]

    @transform(
        target="email@1.0.0",
        label="Find Social Profiles",
        deps=["requests"],
    )
    async def find_social(entity):
        return [Entity(
            data=SocialProfile.blueprint(username="..."),
            edge=Edge(label="profile for", color="#22C55E"),
        )]
"""
from __future__ import annotations

# Core plugin infrastructure
from osintbuddy.plugins import (
    Registry,
    Plugin,
    transform,
    load_plugins_fs,
    TransformPayload,
)

# Result types for transforms
from osintbuddy.results import (
    Entity,
    Edge,
    File,
    Subgraph,
    normalize_result,
)

# JSON to Python compiler
from osintbuddy.compiler import (
    compile_entity,
    compile_file,
    compile_directory,
)

# Field types for type-based matching
from osintbuddy.types import (
    FieldType,
    TypedValue,
    get_field_type,
    are_types_compatible,
)

# Settings for transforms
from osintbuddy.settings import (
    TransformSetting,
    SettingsManager,
    get_settings_manager,
)

# Transform sets for grouping
from osintbuddy.sets import (
    TransformSet,
)

# UI messages
from osintbuddy.messages import (
    UIMessage,
    MessageType,
    TransformResponse,
)

# Structured output
from osintbuddy.output import (
    emit_result,
    emit_error,
    emit_progress,
    emit_json,
    ProgressEmitter,
    ProgressEvent,
)

# Error types
from osintbuddy.errors import (
    PluginError,
    PluginWarn,
    PluginNotFoundError,
    TransformNotFoundError,
    TransformCollisionError,
    DependencyError,
    ConfigError,
    TransformTimeoutError,
    NetworkError,
    RateLimitError,
    AuthError,
    ErrorCode,
)

# Dependency management
from osintbuddy.deps import (
    ensure_deps,
    check_deps,
)
from osintbuddy.utils import (
    resolve_resource_path,
    read_resource_text,
    read_resource_json,
)

__version__ = "1.0.0"

__all__ = [
    # Version
    "__version__",
    # Core
    "Registry",
    "Plugin",
    "transform",
    "load_plugins_fs",
    "TransformPayload",
    # Results
    "Entity",
    "Edge",
    "File",
    "Subgraph",
    "normalize_result",
    # Compiler
    "compile_entity",
    "compile_file",
    "compile_directory",
    # Types
    "FieldType",
    "TypedValue",
    "get_field_type",
    "are_types_compatible",
    # Settings
    "TransformSetting",
    "SettingsManager",
    "get_settings_manager",
    # Sets
    "TransformSet",
    # Messages
    "UIMessage",
    "MessageType",
    "TransformResponse",
    # Output
    "emit_result",
    "emit_error",
    "emit_progress",
    "emit_json",
    "ProgressEmitter",
    "ProgressEvent",
    # Errors
    "PluginError",
    "PluginWarn",
    "PluginNotFoundError",
    "TransformNotFoundError",
    "TransformCollisionError",
    "DependencyError",
    "ConfigError",
    "TransformTimeoutError",
    "NetworkError",
    "RateLimitError",
    "AuthError",
    "ErrorCode",
    # Deps
    "ensure_deps",
    "check_deps",
    # Resources
    "resolve_resource_path",
    "read_resource_text",
    "read_resource_json",
]
