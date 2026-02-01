# Code Style Guide

## Python

### Formatting
- Black formatter (line length 88)
- isort for imports
- Type hints on all functions

### Imports Order
1. Standard library
2. Third-party
3. Local

### Naming
- snake_case for functions, variables
- PascalCase for classes
- UPPER_CASE for constants
- Descriptive names (no single letters except i,j,k for indices)

### Functions
```python
def process_data(
    input_path: Path,
    output_path: Path,
    *,
    batch_size: int = 32,
    verbose: bool = False,
) -> pd.DataFrame:
    """Process raw data and save results.

    Args:
        input_path: Path to input CSV file.
        output_path: Path to save processed data.
        batch_size: Number of samples per batch.
        verbose: Whether to print progress.

    Returns:
        DataFrame with processed results.

    Raises:
        FileNotFoundError: If input_path doesn't exist.
    """
    ...
```

### Patterns
- Prefer composition over inheritance
- Use dataclasses for data containers
- Use pathlib.Path over os.path
- Use f-strings over .format()
- Vectorize with numpy/pandas, avoid loops

### Don'ts
- No global mutable state
- No wildcard imports
- No bare except clauses
- No print() in library code (use logging)
