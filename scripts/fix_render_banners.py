#!/usr/bin/env python3
"""Ensure APP_BANNER appears in grid render (not just login) for all apps."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

APP_DIRS = [
    ROOT / "00-reference",
    ROOT / "10-flag-enablement",
    ROOT / "11-flag-variations",
    ROOT / "99-use-cases" / "01-abcd-test",
    ROOT / "99-use-cases" / "02-segments-by-name",
    ROOT / "99-use-cases" / "11-create-eval-flag",
]


def app_name(app_dir: Path) -> str:
    if app_dir.parent.name == "99-use-cases":
        return app_dir.name
    return app_dir.name


def patch_python_draw(path: Path) -> bool:
    text = path.read_text()
    if "APP_BANNER" not in text:
        return False
    if re.search(r"stdscr\.addstr\(line, 0, APP_BANNER\)", text):
        return False
    if "draw_name_line" in text and "line = 0" in text:
        old = "    line = 0\n    draw_name_line"
        if old in text:
            text = text.replace(
                old,
                "    line = 0\n    stdscr.addstr(line, 0, APP_BANNER)\n    line += 1\n    draw_name_line",
                1,
            )
            path.write_text(text)
            return True
    if "line = 0" in text and 'stdscr.addstr(line, 0, f"Name:' in text:
        text = text.replace(
            "    line = 0\n    stdscr.addstr(line, 0, f\"Name:",
            "    line = 0\n    stdscr.addstr(line, 0, APP_BANNER)\n    line += 1\n    stdscr.addstr(line, 0, f\"Name:",
            1,
        )
        path.write_text(text)
        return True
    return False


def patch_java_render(path: Path) -> bool:
    text = path.read_text()
    if "APP_BANNER" not in text or "writeLine(APP_BANNER);" in text:
        return False
    pattern = r"(        System\.out\.flush\(\);\n)(        String prevText|        String cohort|        writeLine\()"
    match = re.search(pattern, text)
    if not match:
        return False
    text = text.replace(
        match.group(1),
        match.group(1) + "        writeLine(APP_BANNER);\n",
        1,
    )
    path.write_text(text)
    return True


def patch_go_file(path: Path, banner: str) -> bool:
    text = path.read_text()
    changed = False

    if "appBanner" not in text:
        import_end = text.find("\n\n", text.find(")\n"))
        if import_end != -1:
            text = text[:import_end] + f'\n\nconst appBanner = "{banner}"' + text[import_end:]
            changed = True

    if 'fmt.Println("Login\\n")' in text and "fmt.Println(appBanner)" not in text:
        text = text.replace(
            'fmt.Println("Login\\n")',
            'fmt.Println(appBanner)\n\tfmt.Println("Login\\n")',
            1,
        )
        changed = True

    if "writeLine(&out, appBanner)" not in text:
        for marker in [
            '\tnameLine := fmt.Sprintf(\n',
            '\twriteLine(&out, fmt.Sprintf("Name:',
            '\twriteLine(&out, nameLine',
        ]:
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx] + "\twriteLine(&out, appBanner)\n" + text[idx:]
                changed = True
                break

    if changed:
        text = text.replace("\t\twriteLine(&out, appBanner)", "\twriteLine(&out, appBanner)")
        path.write_text(text)
    return changed


def patch_rust_render(path: Path) -> bool:
    text = path.read_text()
    if "APP_BANNER" not in text:
        return False
    if "print_line(out, y, APP_BANNER)" in text or "print_colored_line(out, y, APP_BANNER" in text:
        return False

    if "print_colored_line(out, y, &name_line" in text:
        old = "    let mut y = 0u16;\n    print_colored_line(out, y, &name_line"
        if old in text:
            text = text.replace(
                old,
                "    let mut y = 0u16;\n    print_colored_line(out, y, APP_BANNER, None)?;\n    y += 1;\n    print_colored_line(out, y, &name_line",
                1,
            )
            path.write_text(text)
            return True
        return False

    old = "    let mut y = 0u16;\n    print_line(\n        out,\n        y,\n        &format!(\"Name:"
    if old in text:
        text = text.replace(
            old,
            "    let mut y = 0u16;\n    print_line(out, y, APP_BANNER)?;\n    y += 1;\n    print_line(\n        out,\n        y,\n        &format!(\"Name:",
            1,
        )
        path.write_text(text)
        return True

    old2 = '    let mut y = 0u16;\n    print_line(out, y, &format!("Name:'
    if old2 in text:
        text = text.replace(
            old2,
            '    let mut y = 0u16;\n    print_line(out, y, APP_BANNER)?;\n    y += 1;\n    print_line(out, y, &format!("Name:',
            1,
        )
        path.write_text(text)
        return True
    return False


def patch_cpp_render(path: Path) -> bool:
    text = path.read_text()
    if "kAppBanner" not in text or "write_line(kAppBanner);" in text:
        return False
    match = re.search(
        r"(void render\([^{]+\) \{\n    std::cout << \"\\033\[2J\\033\[H\"[^\n]*\n(?:    const std::string[^\n]*\n)*)(    write_line\()",
        text,
    )
    if not match:
        return False
    text = text.replace(
        match.group(1),
        match.group(1) + "    write_line(kAppBanner);\n",
        1,
    )
    path.write_text(text)
    return True


def patch_node_render(path: Path) -> bool:
    text = path.read_text()
    if "APP_BANNER" not in text:
        return False
    pattern = r"(function render\([^{]+\) \{\n  process\.stdout\.write\([^\n]+\);\n)"
    if not re.search(pattern, text):
        pattern = r"(function render\([^{]+\) \{\n  console\.clear\(\);\n)"
    if not re.search(pattern, text):
        return False
    if re.search(r"process\.stdout\.write\([^\n]+\);\n  console\.log\(APP_BANNER\);", text):
        return False
    if re.search(r"console\.clear\(\);\n  console\.log\(APP_BANNER\);", text):
        return False
    text = re.sub(
        pattern,
        r"\1  console.log(APP_BANNER);\n",
        text,
        count=1,
    )
    path.write_text(text)
    return True


def main() -> None:
    changed = []
    for app_dir in APP_DIRS:
        name = app_name(app_dir)
        if (p := app_dir / "python-console").is_dir():
            for f in p.glob("*.py"):
                if f.name.endswith("-experiment.py"):
                    continue
                if patch_python_draw(f):
                    changed.append(str(f))
        java = app_dir / "java-console" / "src/main/java/GridNavigator.java"
        if java.is_file() and patch_java_render(java):
            changed.append(str(java))
        go = app_dir / "go" / "main.go"
        if go.is_file() and patch_go_file(go, f"{name}[go]"):
            changed.append(str(go))
        rust = app_dir / "rust" / "src/main.rs"
        if rust.is_file() and patch_rust_render(rust):
            changed.append(str(rust))
        cpp = app_dir / "cpp" / "main.cpp"
        if cpp.is_file() and patch_cpp_render(cpp):
            changed.append(str(cpp))
        if (p := app_dir / "node-console").is_dir():
            for f in p.glob("*.js"):
                if f.name.endswith("-experiment.js"):
                    continue
                if patch_node_render(f):
                    changed.append(str(f))

    print(f"Fixed render banner in {len(changed)} files")
    for c in changed:
        print(f"  {c}")


if __name__ == "__main__":
    main()
