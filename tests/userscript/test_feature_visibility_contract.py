import re
from pathlib import Path


SCRIPT = Path("zhipin-auto-greeting.user.js")


def test_every_feature_section_has_a_visibility_definition():
    source = SCRIPT.read_text(encoding="utf-8")
    definition_block = source[
        source.index("const FEATURE_BLOCK_DEFINITIONS = [") : source.index(
            "];", source.index("const FEATURE_BLOCK_DEFINITIONS = [")
        )
    ]
    defined_ids = set(re.findall(r"id: '([^']+)'", definition_block))
    section_ids = set(re.findall(r'data-feature-section="([^"]+)"', source))

    assert section_ids <= defined_ids, (
        f"feature sections without visibility definitions: "
        f"{sorted(section_ids - defined_ids)}"
    )
