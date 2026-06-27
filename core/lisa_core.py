#!/usr/bin/env python3
import sys
from core.registry import load_skills
from core.planner import Planner
from core.router import choose_engine

def build_prompt(skill):
    agents = skill.get("agents", {})
    required = agents.get("required", [])
    optional = agents.get("optional", [])
    rules = "\n".join(f"- {rule}" for rule in skill.get("rules", []))

    return f"""You are Lisa Core executing skill: {skill['name']}.

Description:
{skill.get('description', '')}

Required agents:
{', '.join(required)}

Optional supporting agents:
{', '.join(optional)}

Repository:
{skill['repo']}

Rules:
{rules}

Output:
Save the final report to:
{skill['output']}

Report structure:
# {skill['name']}

## Summary
## Key Findings
## Architecture Notes
## Governance Risks
## Recommended Next Actions
"""

def list_skills(skills):
    print("\nLisa Core v0.2 — Skills\n")
    for name, skill in skills.items():
        print(f"{name}")
        print(f"  {skill.get('description','')}")
        print(f"  Engine: {skill.get('preferred_engine','claude')}")
        print()

def run_skill(skill):
    engine = choose_engine(skill)
    prompt = build_prompt(skill)

    print(f"\nLisa Core running skill: {skill['name']}")
    print(f"Engine: {engine.name}")
    print(f"Output: {skill['output']}\n")

    return engine.run(prompt, cwd=skill["repo"])

def main():
    skills = load_skills()
    planner = Planner()

    if len(sys.argv) < 2:
        list_skills(skills)
        return

    if sys.argv[1] == "skills":
        list_skills(skills)
        return

    if sys.argv[1] == "run" and len(sys.argv) >= 3:
        name = sys.argv[2]
        if name not in skills:
            print(f"Unknown skill: {name}")
            sys.exit(1)
        sys.exit(run_skill(skills[name]))

    if sys.argv[1] == "ask":
        text = " ".join(sys.argv[2:])
        workflow = planner.create_plan(text)

        print("\nExecution Plan\n")
        for step in workflow:
            print(f" • {step}")
        print()

        for step in workflow:
            if step not in skills:
                print(f"Unknown skill in plan: {step}")
                print("Run: lisa-core skills")
                sys.exit(1)
            result = run_skill(skills[step])
            if result != 0:
                sys.exit(result)
        return

    print("Usage:")
    print("  lisa-core skills")
    print("  lisa-core run architecture-review")
    print('  lisa-core ask "review WBS architecture"')
    print('  lisa-core ask "review implementation"')

if __name__ == "__main__":
    main()
