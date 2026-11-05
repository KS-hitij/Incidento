import re

def extract_readme_sections(readme_text):
    sections = {}

    # Split README at Markdown headings
    parts = re.split(
        r"(?m)(?=^#{1,6}\s+)",
        readme_text
    )

    for part in parts:
        part = part.strip()

        if not part:
            continue

        lines = part.splitlines()

        if lines[0].startswith("#"):
            heading = re.sub(r"^#+\s*", "", lines[0]).strip()
            content = "\n".join(lines[1:]).strip()

            sections[heading.lower()] = content

    return sections


def select_relevant_sections(sections):
    """Function to extract relevant sections from the README based on predefined keywords."""
    keywords = [
        "overview",
        "introduction",
        "architecture",
        "tech stack",
        "technology",
        "project structure",
        "installation",
        "configuration",
    ]

    selected = {}

    for heading, content in sections.items():

        if any(keyword in heading for keyword in keywords):
            selected[heading] = content

    return selected