"""ORBIT ML sandbox.

Isolated, deterministic training/evaluation sandbox for the exoplanet mission.
The backend spawns ``python -m ml_sandbox.train`` as a subprocess and reads one
JSON object from the last stdout line; see AGENTS.md section 3.3.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
