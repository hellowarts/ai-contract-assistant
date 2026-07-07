from pathlib import Path

class KBManager:

    def __init__(self, kb_root):

        self.kb_root = Path(kb_root)

        self.kb = {
            "KB-001": self.kb_root / "KB-001.pdf",
            "KB-002": self.kb_root / "KB-002.pdf",
            "KB-003": self.kb_root / "KB-003.pdf",
            "KB-004": self.kb_root / "KB-004.pdf",
            "KB-005": self.kb_root / "KB-005.xlsx",
        }

    def get(self, kb_id):

        return self.kb[kb_id]

    def list(self):

        return self.kb