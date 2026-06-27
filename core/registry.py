from pathlib import Path
import yaml

BASE = Path.home() / "Lisa"
SKILLS_DIR = BASE / "skills"

def load_skills():
    skills = {}
    for file in SKILLS_DIR.glob("*.yaml"):
        data = yaml.safe_load(file.read_text())
        skills[data["name"]] = data
    return skills
