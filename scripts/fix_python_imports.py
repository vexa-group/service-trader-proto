#!/usr/bin/env python3
"""
Post-processing script to fix Python proto imports and restructure to Go-like layout.

This script:
1. Moves proto files from trader/ to their respective service folders
2. Fixes imports using relative imports for same-service imports
3. Fixes imports using absolute imports for cross-service imports
4. Creates __init__.py files in each directory
"""

import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List


# Service folders we want to create
SERVICES = [
    "balance",
    "balance_entry",
    "balance_entry_source",
    "campaign",
    "campaign_action",
    "campaign_profit",
    "campaign_wallet",
    "common",
    "scenario",
    "scenario_action",
    "scenario_profit",
    "scenario_wallet",
    "setting",
    "strategy",
    "track",
    "trader_coin",
]


def get_base_dir() -> Path:
    """Get the base directory for generated Python code."""
    return Path("gen/python/service_trader_proto")


def get_service_dir(base_dir: Path) -> Path:
    """Get the service directory where protoc initially generates files."""
    return base_dir / "trader"


def create_service_directories(base_dir: Path) -> None:
    """Create service directories if they don't exist."""
    for service in SERVICES:
        service_dir = base_dir / service
        service_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {service_dir}")


def move_proto_files(base_dir: Path, service_dir: Path) -> Dict[str, List[str]]:
    """Move proto files from service/ to their respective service directories."""
    moved_files: Dict[str, List[str]] = {service: [] for service in SERVICES}

    for service in SERVICES:
        # Find files matching the service pattern
        for pattern in [f"{service}_pb2.py", f"{service}_pb2_grpc.py"]:
            src_file = service_dir / pattern
            if src_file.exists():
                dest_dir = base_dir / service
                dest_file = dest_dir / pattern
                shutil.move(str(src_file), str(dest_file))
                moved_files[service].append(str(dest_file))
                print(f"Moved: {src_file} -> {dest_file}")

    return moved_files


def fix_imports_in_file(file_path: Path, base_dir: Path) -> None:
    """Fix imports in a Python file."""
    with open(file_path, "r") as f:
        content = f.read()

    original_content = content
    service = file_path.parent.name

    # Fix same-service imports (relative imports)
    # Pattern: from trader import auth_pb2 as ... -> from . import auth_pb2 as ...
    content = re.sub(
        r"from trader import " + service + r"_pb2 as (\S+)",
        r"from . import " + service + r"_pb2 as \1",
        content,
    )

    # Fix cross-service imports (absolute imports)
    # Pattern: from trader import common_pb2 as ... -> from service_trader_proto.common import common_pb2 as ...
    for other_service in SERVICES:
        if other_service == service:
            continue
        # Match: from trader import {other_service}_pb2 as ...
        content = re.sub(
            r"from trader import " + other_service + r"_pb2 as (\S+)",
            r"from service_trader_proto."
            + other_service
            + r" import "
            + other_service
            + r"_pb2 as \1",
            content,
        )

    # Only write if content changed
    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed imports in: {file_path}")


def fix_all_imports(base_dir: Path, moved_files: Dict[str, List[str]]) -> None:
    """Fix imports in all moved files."""
    for _, files in moved_files.items():
        for file_path_str in files:
            file_path = Path(file_path_str)
            fix_imports_in_file(file_path, base_dir)


def create_init_files(base_dir: Path) -> None:
    """Create __init__.py files in all directories."""
    # Top-level __init__.py
    top_init = base_dir / "__init__.py"
    if not top_init.exists():
        top_init.touch()
        print(f"Created: {top_init}")

    # Service directory __init__.py files
    for service in SERVICES:
        service_init = base_dir / service / "__init__.py"
        if not service_init.exists():
            service_init.touch()
            print(f"Created: {service_init}")

    # Create py.typed
    py_typed = base_dir / "py.typed"
    if not py_typed.exists():
        py_typed.touch()
        print(f"Created: {py_typed}")


def update_top_level_init(base_dir: Path) -> None:
    """Update top-level __init__.py to expose all modules."""
    init_file = base_dir / "__init__.py"
    content = """\"\"\"Service Trader Proto - Python gRPC bindings.

This package contains the generated Python code for the Trader Service gRPC API.
\"\"\"

"""
    for service in SERVICES:
        content += f"from service_trader_proto import {service}\n"
    content += "\n__all__ = [\n"
    for service in SERVICES:
        content += f"    '{service}',\n"
    content += "]\n"

    with open(init_file, "w") as f:
        f.write(content)
    print(f"Updated: {init_file}")


def update_service_init_files(base_dir: Path) -> None:
    """Update service-level __init__.py files to expose pb2 and pb2_grpc."""
    for service in SERVICES:
        service_dir = base_dir / service
        init_file = service_dir / "__init__.py"
        has_pb2 = (service_dir / f"{service}_pb2.py").exists()
        has_pb2_grpc = (service_dir / f"{service}_pb2_grpc.py").exists()

        lines = [f'"""{service.capitalize()} service proto definitions."""', ""]
        exports: List[str] = []

        if has_pb2:
            lines.append(f"from . import {service}_pb2")
            exports.append(f"'{service}_pb2'")
        if has_pb2_grpc:
            lines.append(f"from . import {service}_pb2_grpc")
            exports.append(f"'{service}_pb2_grpc'")

        lines.extend(["", "__all__ = ["])
        for export in exports:
            lines.append(f"    {export},")
        lines.append("]")
        lines.append("")
        content = "\n".join(lines)

        with open(init_file, "w") as f:
            f.write(content)
        print(f"Updated: {init_file}")


def cleanup_trader_directory(base_dir: Path) -> None:
    """Remove the trader directory if it's empty."""
    trader_dir = base_dir / "trader"
    if trader_dir.exists() and trader_dir.is_dir():
        # Check if directory is empty (only __init__.py if anything)
        files = list(trader_dir.glob("*"))
        files = [f for f in files if f.name != "__init__.py"]
        if not files:
            shutil.rmtree(trader_dir)
            print(f"Removed empty directory: {trader_dir}")
        else:
            print(
                f"Warning: trader directory not empty, contains: {[f.name for f in files]}"
            )


def main() -> None:
    """Main function to run the fix script."""
    print("Starting Python proto import fix...")

    base_dir = get_base_dir()
    trader_dir = get_service_dir(base_dir)

    if not base_dir.exists():
        print(f"Error: Base directory {base_dir} does not exist!")
        sys.exit(1)

    if not trader_dir.exists():
        print(f"Error: Trader directory {trader_dir} does not exist!")
        sys.exit(1)

    # Step 1: Create service directories
    print("\n=== Step 1: Creating service directories ===")
    create_service_directories(base_dir)

    # Step 2: Move proto files
    print("\n=== Step 2: Moving proto files ===")
    moved_files = move_proto_files(base_dir, trader_dir)

    # Step 3: Fix imports
    print("\n=== Step 3: Fixing imports ===")
    fix_all_imports(base_dir, moved_files)

    # Step 4: Create __init__.py files
    print("\n=== Step 4: Creating __init__.py files ===")
    create_init_files(base_dir)

    # Step 5: Update __init__.py files with proper exports
    print("\n=== Step 5: Updating __init__.py files ===")
    update_top_level_init(base_dir)
    update_service_init_files(base_dir)

    # Step 6: Cleanup
    print("\n=== Step 6: Cleanup ===")
    cleanup_trader_directory(base_dir)

    print("\n=== Python proto import fix complete! ===")
    print("\nNew structure:")
    for service in SERVICES:
        service_dir = base_dir / service
        if service_dir.exists():
            files = [
                f.name for f in service_dir.glob("*.py") if f.name != "__init__.py"
            ]
            print(f"  {service}/: {', '.join(files)}")


if __name__ == "__main__":
    main()
