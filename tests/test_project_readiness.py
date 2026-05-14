import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".superpowers",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "test-results",
}
SKIP_FILES = {
    Path("tests/test_project_readiness.py"),
}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
LEGACY_BRAND_TOKENS = tuple(
    "".join(parts)
    for parts in (
        ("Çı", "rak"),
        ("Çı", "rağı"),
        ("çı", "rak"),
        ("çı", "rağı"),
        ("Ci", "rak"),
        ("ci", "rak"),
        ("CI", "RAK"),
        ("X-", "Ci", "rak"),
        ("VITE_", "CI", "RAK"),
    )
)


def project_files():
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield rel, path


class ProjectReadinessTests(unittest.TestCase):
    def test_buildathon_required_files_exist(self):
        required_paths = [
            "README.md",
            "idea.md",
            "prd.md",
            "tasks.md",
            "user-flow.md",
            "tech-stack.md",
            "features/main.py",
            "frontend/package.json",
            "frontend/src/App.jsx",
        ]

        missing = [path for path in required_paths if not (ROOT / path).exists()]

        self.assertEqual([], missing)

    def test_readme_has_buildathon_delivery_sections(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        required_sections = [
            "## Problem",
            "## Çözüm",
            "## Canlı Demo",
            "## Kullanılan Teknolojiler",
            "## Nasıl Çalıştırılır?",
            "## Demo Akışı",
            "## Güven Sınırları",
        ]

        missing = [section for section in required_sections if section not in readme]

        self.assertEqual([], missing)

    def test_legacy_brand_tokens_are_not_in_active_files(self):
        offenders = []
        for rel, path in project_files():
            if rel in SKIP_FILES or path.is_dir() or path.suffix not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            hits = [token for token in LEGACY_BRAND_TOKENS if token in text]
            if hits:
                offenders.append(f"{rel}: {', '.join(hits)}")

        self.assertEqual([], offenders)

    def test_legacy_brand_tokens_are_not_in_paths(self):
        offenders = [
            str(rel)
            for rel, _ in project_files()
            if rel not in SKIP_FILES
            and any(token.lower() in str(rel).lower() for token in LEGACY_BRAND_TOKENS)
        ]

        self.assertEqual([], offenders)

    def test_generated_or_local_artifacts_are_not_committed(self):
        forbidden_paths = [
            ".DS_Store",
            "".join(("ci", "rak", ".sqlite3")),
            "kanit.sqlite3",
            "frontend/node_modules",
            "frontend/dist",
            "frontend/test-results",
        ]

        present = [path for path in forbidden_paths if (ROOT / path).exists()]

        self.assertEqual([], present)

    def test_gitignore_excludes_local_artifacts(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        required_ignores = [
            ".env",
            ".venv/",
            ".superpowers/",
            ".DS_Store",
            "__pycache__/",
            "*.pyc",
            "*.sqlite3",
            ".pytest_cache/",
            "frontend/node_modules/",
            "frontend/dist/",
            "frontend/test-results/",
        ]

        missing = [pattern for pattern in required_ignores if pattern not in gitignore]

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
