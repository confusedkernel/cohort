"""Agents that read the graph, call tools, and write back — nothing else
(design doc §5 principle 3). No agent-to-agent messaging is defined here or
anywhere in MEEP; an agent's entire world is its tool loop against one
`Graph`."""
