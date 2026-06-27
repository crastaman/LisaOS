class Planner:

    def __init__(self):
        self.workflows = {
            "review implementation": [
                "architecture-review",
                "migration-audit",
                "regression-risk",
                "docs-review"
            ],
            "prepare release": [
                "architecture-review",
                "docs-review"
            ],
            "review architecture": [
                "architecture-review"
            ]
        }

    def create_plan(self, intent: str):
        intent = intent.lower()

        for trigger, workflow in self.workflows.items():
            if trigger in intent:
                return workflow

        return ["architecture-review"]
