# Related Tests Controller

This VS Code extension adds a second Testing controller named `Related Tests`.

It discovers Python source files that declare a top-level module docstring like:

```python
"""
Tests:
- tests/core/test_guardrails.py
- tests/core/contracts/test_execution.py
"""
```

When you expand a source module in the Testing pane, the controller resolves only the related `tests/...py` files declared in that module. Running a source module node executes each related file through `python -m pytest`, which means existing `unittest.TestCase` suites still run under pytest collection.

The extension ships its own Python metadata helper under `python/related_tests_metadata.py`, so the editor-specific logic stays out of the runtime framework.

The global Testing-pane refresh remains global. For module-scoped refresh, use `Refresh Related Tests` on a source item in the `Related Tests` tree.
