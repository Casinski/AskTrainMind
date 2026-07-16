import re

def _is_valid_section_index(idx: str, title: str) -> bool:
    parts = idx.split(".")
    if len(parts) < 2:
        return False
    for part in parts:
        if not part.isdigit():
            return False
    if len(parts) == 2 and parts[1] == "0":
        return False
    if len(parts) > 6:
        return False
    return True

def _clean_title(raw: str) -> str:
    cleaned = re.sub(r"^[\+\-–—•\*·►▪▸\uf02a\uf0b7\uf0d8\uf020\s]+", "", raw)
    return cleaned.strip()

# Simula esattamente quello che fa _extract_all_indexes
test_lines = [
    "5.0 ", "2F_04.01.Zefiro-", "4S_09.03.05.-.TCMS ",
    "3.2 ", "Pantograph Control",
    "3.2.1 ", "+Pantograph -  Lifting",
    "3.2.1.1 ", "Function Design",
    "3.2.1.1.1 Normal Condition ",
    "3.2.1.1.2 Failure Condition ",
    "3.2.1.1.3 Failure Supervision ",
]

lines = [ln.strip() for ln in test_lines]
print("Righe dopo strip:")
for i, l in enumerate(lines):
    print(f"  [{i}] repr={repr(l)}")
    
    m  = re.match(r"^(\d+(?:\.\d+){1,})\s+(.+)$", l)
    m2 = re.match(r"^(\d+(?:\.\d+){1,})\s*$", l)
    
    if m:
        idx   = m.group(1).strip()
        title = _clean_title(re.sub(r"\s+", " ", m.group(2)).strip())
        valid = _is_valid_section_index(idx, title)
        print(f"    → FORMATO A: idx='{idx}' title='{title}' valid={valid}")
    elif m2:
        idx   = m2.group(1).strip()
        valid = _is_valid_section_index(idx, "")
        print(f"    → FORMATO B: idx='{idx}' valid={valid}")
    else:
        print(f"    → nessun match")