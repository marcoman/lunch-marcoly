#!/usr/bin/env python3
"""Add ApplicationName[language] banner to all grid navigator apps."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

APP_DIRS = [
    ROOT / "00-reference-code",
    ROOT / "01-reference-agent",
    ROOT / "10-code-control/11-flag-enablement",
    ROOT / "10-code-control/12-flag-variations",
    ROOT / "99-use-cases" / "01-abcd-test",
    ROOT / "99-use-cases" / "02-segments-by-name",
    ROOT / "99-use-cases" / "11-create-eval-flag",
]

LANG_DIRS = {
    "python-console",
    "node-console",
    "java-console",
    "python",
    "node",
    "java",
    "go",
    "rust",
    "cpp",
}


def app_name(app_dir: Path) -> str:
    if app_dir.parent.name == "99-use-cases":
        return app_dir.name
    return app_dir.name


def banner_for(app_dir: Path, lang: str) -> str:
    return f"{app_name(app_dir)}[{lang}]"


def already_has_banner(text: str, banner: str) -> bool:
    return banner in text


def patch_python_console(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False
    if 'APP_BANNER = "' in text:
        text = re.sub(r'APP_BANNER = "[^"]*"', f'APP_BANNER = "{banner}"', text)
    else:
        insert_after = 'COLS = ("l", "m", "r")\n'
        if insert_after not in text:
            insert_after = 'COLS = ["l", "m", "r"]\n'
        text = text.replace(
            insert_after,
            insert_after + f'\nAPP_BANNER = "{banner}"\n',
            1,
        )

    if "stdscr.addstr(0, 0, APP_BANNER)" not in text:
        # draw_screen with line variable
        if "line = 0" in text and "draw_name_line(stdscr, line" in text:
            text = text.replace(
                "    line = 0\n    draw_name_line",
                "    line = 0\n    stdscr.addstr(line, 0, APP_BANNER)\n    line += 1\n    draw_name_line",
                1,
            )
        elif "stdscr.addstr(0, 0, f\"Name:" in text:
            text = text.replace(
                '    stdscr.addstr(0, 0, f"Name:',
                '    stdscr.addstr(0, 0, APP_BANNER)\n    stdscr.addstr(1, 0, f"Name:',
                1,
            )
            text = text.replace(
                "    stdscr.addstr(1, 0, f\"Current position:",
                '    stdscr.addstr(2, 0, f"Current position:',
                1,
            )
            text = text.replace(
                "    stdscr.addstr(2, 0, f\"Previous position:",
                '    stdscr.addstr(3, 0, f"Previous position:',
                1,
            )
            text = re.sub(
                r"    stdscr\.addstr\((\d+), 0, \"Use arrow keys",
                lambda m: f'    stdscr.addstr({int(m.group(1)) + 1}, 0, "Use arrow keys',
                text,
                count=1,
            )
            text = re.sub(
                r"base_y, base_x = (\d+), 2",
                lambda m: f"base_y, base_x = {int(m.group(1)) + 1}, 2",
                text,
                count=1,
            )
        elif "stdscr.addstr(line, 0," in text and "APP_BANNER" in text:
            pass
        else:
            raise RuntimeError(f"unhandled python-console pattern: {path}")

    if 'stdscr.addstr(0, 0, "Login")' in text and "APP_BANNER" in text:
        text = text.replace(
            '    stdscr.addstr(0, 0, "Login")',
            '    stdscr.addstr(0, 0, APP_BANNER)\n    stdscr.addstr(2, 0, "Login")',
            1,
        )
        text = text.replace('    stdscr.addstr(2, 0, "Username: ")', '    stdscr.addstr(4, 0, "Username: ")', 1)
        text = text.replace("stdscr.getstr(2, 10", "stdscr.getstr(4, 10", 1)
        text = text.replace('    stdscr.addstr(4, 0, "Username is required', '    stdscr.addstr(6, 0, "Username is required', 1)

    path.write_text(text)
    return True


def patch_node_console(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False
    if "const APP_BANNER" not in text:
        text = text.replace(
            'const COLS = ["l", "m", "r"];',
            f'const COLS = ["l", "m", "r"];\nconst APP_BANNER = "{banner}";',
            1,
        )
    else:
        text = re.sub(r'const APP_BANNER = "[^"]*";', f'const APP_BANNER = "{banner}";', text)

    if "console.log(APP_BANNER);" not in text:
        text = text.replace(
            "  console.clear();",
            "  console.clear();\n  console.log(APP_BANNER);",
            1,
        )
    if 'console.log("Login\\n");' in text and "APP_BANNER" in text:
        text = text.replace(
            '    console.log("Login\\n");',
            '    console.log(APP_BANNER);\n    console.log("Login\\n");',
            1,
        )
    path.write_text(text)
    return True


def patch_java_console(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False
    if "APP_BANNER" not in text:
        text = text.replace(
            '    private static final String[] COLS = {"l", "m", "r"};',
            f'    private static final String[] COLS = {{"l", "m", "r"}};\n    private static final String APP_BANNER = "{banner}";',
            1,
        )
    else:
        text = re.sub(
            r'private static final String APP_BANNER = "[^"]*";',
            f'private static final String APP_BANNER = "{banner}";',
            text,
        )

    if 'writeLine(APP_BANNER);' not in text:
        text = text.replace(
            '        String prevText = previous == null ? "—" : formatPos(previous.row, previous.col);\n        writeLine("Name:',
            '        String prevText = previous == null ? "—" : formatPos(previous.row, previous.col);\n        writeLine(APP_BANNER);\n        writeLine("Name:',
            1,
        )
    if 'System.out.println("Login\\n");' in text and "APP_BANNER" in text:
        text = text.replace(
            '        System.out.println("Login\\n");',
            '        System.out.println(APP_BANNER);\n        System.out.println("Login\\n");',
            1,
        )
    path.write_text(text)
    return True


def patch_go(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False
    if "appBanner" not in text:
        text = text.replace(
            "var cols = [3]string{\"l\", \"m\", \"r\"}",
            f'const appBanner = "{banner}"\n\nvar cols = [3]string{{"l", "m", "r"}}',
            1,
        )
    else:
        text = re.sub(r'const appBanner = "[^"]*"', f'const appBanner = "{banner}"', text)

    if "writeLine(&out, appBanner)" not in text:
        text = text.replace(
            '\twriteLine(&out, fmt.Sprintf("Name: %s", username))',
            '\twriteLine(&out, appBanner)\n\twriteLine(&out, fmt.Sprintf("Name: %s", username))',
            1,
        )
    if 'fmt.Println("Login\\n")' in text and "appBanner" in text:
        text = text.replace(
            '\tfmt.Println("Login\\n")',
            '\tfmt.Println(appBanner)\n\tfmt.Println("Login\\n")',
            1,
        )
    path.write_text(text)
    return True


def patch_rust(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False
    if "APP_BANNER" not in text:
        text = text.replace(
            'const COLS: [&str; 3] = ["l", "m", "r"];',
            f'const APP_BANNER: &str = "{banner}";\n\nconst COLS: [&str; 3] = ["l", "m", "r"];',
            1,
        )
    else:
        text = re.sub(r'const APP_BANNER: &str = "[^"]*";', f'const APP_BANNER: &str = "{banner}";', text)

    if "print_line(out, y, APP_BANNER)" not in text:
        text = text.replace(
            "    let mut y = 0u16;\n    print_line(out, y, &format!(\"Name:",
            "    let mut y = 0u16;\n    print_line(out, y, APP_BANNER)?;\n    y += 1;\n    print_line(out, y, &format!(\"Name:",
            1,
        )
    if 'println!("Login\\n");' in text and "APP_BANNER" in text:
        text = text.replace(
            '    println!("Login\\n");',
            '    println!("{APP_BANNER}");\n    println!("Login\\n");',
            1,
        )
    path.write_text(text)
    return True


def patch_cpp(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False
    if "kAppBanner" not in text:
        text = text.replace(
            'constexpr std::array<const char*, 3> kCols = {"l", "m", "r"};',
            f'constexpr const char* kAppBanner = "{banner}";\nconstexpr std::array<const char*, 3> kCols = {{"l", "m", "r"}};',
            1,
        )
    else:
        text = re.sub(
            r'constexpr const char\* kAppBanner = "[^"]*";',
            f'constexpr const char* kAppBanner = "{banner}";',
            text,
        )

    if 'write_line(kAppBanner);' not in text:
        text = text.replace(
            '    write_line("Name: " + username);',
            '    write_line(kAppBanner);\n    write_line("Name: " + username);',
            1,
        )
    if 'std::cout << "Login\\n\\nUsername: ";' in text and "kAppBanner" in text:
        text = text.replace(
            '    std::cout << "Login\\n\\nUsername: ";',
            '    std::cout << kAppBanner << "\\n\\nLogin\\n\\nUsername: ";',
            1,
        )
    path.write_text(text)
    return True


def patch_index_html(path: Path, banner: str) -> bool:
    text = path.read_text()
    if already_has_banner(text, banner):
        return False

    login_marker = '<section id="login-screen">'
    if login_marker in text and f'<div class="app-banner">{banner}</div>' not in text:
        text = text.replace(
            login_marker,
            f'{login_marker}\n    <div class="app-banner">{banner}</div>',
            1,
        )

    header_marker = '<div class="header">'
    if header_marker in text:
        text = text.replace(
            header_marker,
            f'{header_marker}\n      <div class="app-banner">{banner}</div>',
            1,
        )

    if ".app-banner" not in text:
        text = text.replace(
            "    .header { margin-bottom: 1.5rem; line-height: 1.6; }",
            "    .app-banner { font-size: 0.875rem; color: #666; margin-bottom: 0.5rem; }\n    body.highlight-on .app-banner { color: #aaa; }\n    .header { margin-bottom: 1.5rem; line-height: 1.6; }",
            1,
        )
        if ".app-banner" not in text:
            text = text.replace(
                "    .header { margin-bottom: 1.5rem; line-height: 1.6; }",
                "    .app-banner { font-size: 0.875rem; color: #666; margin-bottom: 0.5rem; }\n    .header { margin-bottom: 1.5rem; line-height: 1.6; }",
                1,
            )
        if ".app-banner" not in text:
            text = text.replace(
                "    h1 { font-size: 1.25rem; margin-bottom: 1rem; }",
                "    .app-banner { font-size: 0.875rem; color: #666; margin-bottom: 0.5rem; }\n    h1 { font-size: 1.25rem; margin-bottom: 1rem; }",
                1,
            )

    path.write_text(text)
    return True


def main() -> None:
    changed: list[str] = []
    errors: list[str] = []

    for app_dir in APP_DIRS:
        name = app_name(app_dir)
        for lang in LANG_DIRS:
            lang_dir = app_dir / lang
            if not lang_dir.is_dir():
                continue
            banner = banner_for(app_dir, lang)
            try:
                if lang == "python-console":
                    for path in lang_dir.glob("*.py"):
                        if path.name.endswith("-experiment.py"):
                            continue
                        if patch_python_console(path, banner):
                            changed.append(str(path))
                elif lang == "node-console":
                    for path in lang_dir.glob("*.js"):
                        if path.name.endswith("-experiment.js"):
                            continue
                        if patch_node_console(path, banner):
                            changed.append(str(path))
                elif lang == "java-console":
                    path = lang_dir / "src/main/java/GridNavigator.java"
                    if path.is_file() and patch_java_console(path, banner):
                        changed.append(str(path))
                elif lang == "go":
                    path = lang_dir / "main.go"
                    if path.is_file() and patch_go(path, banner):
                        changed.append(str(path))
                elif lang == "rust":
                    path = lang_dir / "src/main.rs"
                    if path.is_file() and patch_rust(path, banner):
                        changed.append(str(path))
                elif lang == "cpp":
                    path = lang_dir / "main.cpp"
                    if path.is_file() and patch_cpp(path, banner):
                        changed.append(str(path))
                elif lang in ("python", "node"):
                    html = lang_dir / "index.html"
                    if html.is_file() and patch_index_html(html, banner):
                        changed.append(str(html))
                elif lang == "java":
                    html = lang_dir / "src/main/resources/public/index.html"
                    if html.is_file() and patch_index_html(html, banner):
                        changed.append(str(html))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{lang_dir}: {exc}")

    print(f"Updated {len(changed)} files")
    for path in changed:
        print(f"  {path}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors:
            print(f"  {err}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
