"""Named, schema-validated write functions an agent may call (design doc
build order stage 2). Nothing here exposes a way to write arbitrary graph
structure or request a whole corpus — each tool is task-shaped, and every
write it makes still goes through `graph.py`'s enforced boundary."""
