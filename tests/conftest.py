import sys
from pathlib import Path

# Make ``deckpip`` importable regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).parent.parent))
