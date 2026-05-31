# File system utilities/PDF parsers

def read_local_document(file_path: str) -> str:
    """Reads structured text contents directly out of a file in the workspace."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"
