from pathlib import Path

class Aggregator:

    def __init__(self):
        self.results = []

    def add(self, result):
        self.results.append(result)

    def write_report(self, filename):

        output = [
            "# Lisa Executive Engineering Report",
            ""
        ]

        for result in self.results:

            output.append(f"## {result.skill}")
            output.append("")
            output.append(result.output)
            output.append("")

        Path(filename).write_text("\n".join(output))

        return filename
