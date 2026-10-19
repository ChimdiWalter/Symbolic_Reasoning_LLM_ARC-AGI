"""Convert the discussion draft's Markdown to Emacs Org, with the same substance.

  python scripts/md_to_org.py IN.md OUT.org "Title" "Subtitle" "Author" "YYYY-MM-DD"

It handles headings, block quotes and rules line by line. It applies inline markup (bold, italic and code) to the
whole text, so emphasis may span one line break, as Org allows.
"""
import re
import sys


def convert(md, title, subtitle, author, date):
    lines, first, quote = [], True, False
    for line in md.splitlines():
        if line.startswith("# ") and first:
            first = False
            continue
        if line.startswith("*Working discussion note"):
            continue
        if line.startswith("> "):
            if not quote:
                lines.append("#+BEGIN_QUOTE")
                quote = True
            lines.append(line[2:])
            continue
        if quote and not line.startswith(">"):
            lines.append("#+END_QUOTE")
            quote = False
        if line.startswith("### "):
            lines.append("** " + line[4:])
        elif line.startswith("## "):
            lines.append("* " + line[3:])
        elif line.strip() == "---":
            lines.append("-----")
        else:
            lines.append(line)
    if quote:
        lines.append("#+END_QUOTE")
    body = "\n".join(lines)
    body = re.sub(r"`([^`\n]+)`", r"=\1=", body)
    bold = []

    def keep(m):
        bold.append(m.group(1))
        return f"\x00{len(bold) - 1}\x00"
    body = re.sub(r"\*\*([^\n]+?)\*\*", keep, body)
    body = re.sub(r"(?<![\w*\x00])\*(?![\s*])([^*\n]+(?:\n[^*\n]+)?)(?<!\s)\*(?![\w*])", r"/\1/", body)
    body = re.sub(r"\x00(\d+)\x00", lambda m: "*" + bold[int(m.group(1))] + "*", body)
    head = [f"#+TITLE: {title}", f"#+SUBTITLE: {subtitle}", f"#+AUTHOR: {author}", f"#+DATE: {date}",
            "#+OPTIONS: toc:nil num:nil ^:nil", "#+STARTUP: showall", ""]
    return "\n".join(head) + "\n" + body + "\n"


if __name__ == "__main__":
    a = sys.argv[1:]
    open(a[1], "w").write(convert(open(a[0]).read(), *a[2:6]))
