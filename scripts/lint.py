"""
Report the issues Codacy would flag as new on this branch and fix the ones Ruff can.

Codacy fails a pull request on any issue that its merge-base (git) does not have. This
runs in the dev image the checks behind nearly all of Codacy's findings on CUBE: Bandit
with pyproject.toml as its configuration, pyflakes and dodgy (Codacy's Prospector), Pylint
with Codacy's plugin and rules and ``uv audit`` for the lockfiles (Codacy's Trivy). It
checks the files changed since the merge-base, uncommitted and untracked ones included,
in the working tree and in the merge-base's tree and reports what only the working tree
has, keyed as Codacy keys an issue: file, rule, source line text and message.

    just lint [--all] [--base REF]
    just lint-fix [--unsafe] [--base REF]

``fix`` applies Ruff's fixes for the new pyflakes issues (safe ones only unless
``--unsafe``), then checks again. Exit status: 0 clean, 1 new issues, 2 failure.
"""

import argparse
import io
import json
import re
import subprocess  # nosec B404 - runs git and the linters with fixed argument lists
import sys
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from dodgy.checks import check_file


# Lockfiles and the uv project each belongs to.
LOCKFILES = {"uv.lock": ".", "benchmarks/uv.lock": "benchmarks"}

# The Pylint rules Codacy's coding standard for CUBE enables (as its API listed them).
PYLINT_RULES = """
    E0100 E0101 E0102 E0103 E0104 E0105 E0106 E0107 E0108 E0110 E0112 E0113 E0114 E0115
    E0117 E0202 E0203 E0211 E0236 E0238 E0239 E0240 E0241 E0301 E0302 E0601 E0603 E0604
    E0701 E0702 E0704 E0710 E0711 E0712 E1003 E1102 E1111 E1120 E1121 E1123 E1124 E1125
    E1126 E1127 E1132 E1200 E1201 E1205 E1206 E1300 E1301 E1302 E1303 E1304 E1305 E1306
    W0101 W0102 W0106 W0109 W0122 W0123 W0150 W0199 W0221 W0222 W0233 W0410 W0601 W0622
    W0702 W0705 W0711 W1300 W1301 W1302 W1303 W1305 W1306 W1307
""".split()

# A fix can leave another for the next pass, e.g. two names of one import statement.
FIX_PASSES = 10

# Right after a commit, Docker Desktop's file sharing can show the container the new ref a
# moment before the commit object and then git exits 128: try again after these delays.
GIT_RETRY_DELAYS = (0.5, 1.0)


class LintError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Issue:
    path: str
    rule: str
    text: str
    message: str
    line: int = field(default=0, compare=False)
    hint: str = field(default="", compare=False)


def run(cmd, cwd=".", ok=(0, 1), text=True, label=None):
    """
    Run a command and return its stdout; fail on an exit status not in ``ok``.
    """
    proc = subprocess.run(  # nosec B603 nosemgrep - fixed argument lists, no shell
        cmd, cwd=cwd, capture_output=True, text=text, check=False
    )
    if proc.returncode not in ok:
        stderr = proc.stderr if text else proc.stderr.decode(errors="replace")
        name = label or " ".join(cmd[:3])
        raise LintError(f"{name} exited {proc.returncode}: {stderr.strip()[-2000:]}",
                        proc.returncode)
    return proc.stdout


def git(*args, ok=(0,), text=True):
    # The checkout is mounted into the container, maybe owned by another uid.
    cmd = ["git", "-c", "safe.directory=*", *args]

    for delay in (*GIT_RETRY_DELAYS, None):
        try:
            return run(cmd, ok=ok, text=text, label=f"git {args[0]}")
        except LintError as e:
            if delay is None or e.status != 128:
                raise
            time.sleep(delay)


class Tree:
    """
    A checkout of the repository: the working tree or an extracted commit.
    """

    def __init__(self, root):
        self.root = Path(root)
        self._lines = {}

    def line(self, path, number):
        if path not in self._lines:
            try:
                self._lines[path] = (self.root / path).read_text(errors="replace"
                                                                 ).split("\n")
            except OSError:
                self._lines[path] = []

        lines = self._lines[path]
        return lines[number - 1].strip() if 0 < number <= len(lines) else ""

    def issue(self, path, number, rule, message, hint=""):
        return Issue(path, rule, self.line(path, number), message, number, hint)


def bandit(tree, files):
    out = run(["bandit", "-q", "-c", "pyproject.toml", "-f", "json", *files], tree.root)

    return [
        tree.issue(
            r["filename"].removeprefix("./"), r["line_number"], f"Bandit {r['test_id']}",
            r["issue_text"],
        )
        for r in json.loads(out)["results"]
    ]


def pyflakes(tree, files):
    fmt = "%(path)s\t%(row)d\t%(code)s\t%(text)s"
    out = run(["flake8", "--isolated", "--select=F", f"--format={fmt}", *files],
              tree.root)
    issues = []

    for row in filter(None, out.splitlines()):
        path, number, code, message = row.split("\t", 3)
        issues.append(tree.issue(path, int(number), f"pyflakes {code}", message))
    return issues


def dodgy(tree, files):
    return [
        tree.issue(path, number, f"dodgy {key}", message)
        for path in files
        for number, key, message in check_file(str(tree.root / path))
    ]


def pylint(tree, files):
    cmd = [
        "pylint", "--persistent=n", "--score=n", "--jobs=0", "--output-format=json2",
        "--load-plugins=pylint_django",
        "--disable=django-installed-checker,django-model-checker",
        "--disable=all", f"--enable={','.join(PYLINT_RULES)}", *files,
    ]
    out = run(cmd, tree.root, ok=range(32))  # 32 is a usage error, the rest flag findings
    return [
        tree.issue(m["path"], m["line"], f"Pylint {m['messageId']}", m["message"])
        for m in json.loads(out)["messages"]
    ]


def advisories(tree, lockfiles):
    issues = []

    for lockfile in lockfiles:
        project = LOCKFILES[lockfile]
        cmd = [
            "uv", "audit", "--frozen", "--no-dev", "--preview-features",
            "audit-command,json-output", "--output-format", "json", "--project", project,
        ]

        try:
            vulns = json.loads(run(cmd, tree.root))["vulnerabilities"]
        except (LintError, ValueError, KeyError) as e:
            print(f"warning: {lockfile} not audited: {e}", file=sys.stderr)
            continue

        upgrade = (
            "just lock-upgrade {}" if project == "."
            else f"just uv lock --upgrade-package {{}} --directory {project}"
        )
        seen = set()

        for vuln in vulns:
            name, version = vuln["dependency"]["name"], vuln["dependency"]["version"]
            ids = [vuln["id"], *vuln.get("aliases", [])]
            advisory = min((i for i in ids if i.startswith("GHSA-")), default=vuln["id"])

            if (name, advisory) in seen:  # the same advisory from another database
                continue

            seen.add((name, advisory))
            fixed = ", ".join(vuln.get("fix_versions") or ["no release yet"])
            summary = vuln.get("summary", "")
            message = f"{name} {version}: {advisory} {summary} (fixed in {fixed})"
            number = locked_line(tree, lockfile, name)
            issues.append(tree.issue(lockfile, number, "uv audit", message,
                                     upgrade.format(name)))
    return issues


def locked_line(tree, lockfile, name):
    for number, line in enumerate((tree.root / lockfile).read_text().split("\n"), 1):
        if line == f'name = "{name}"':
            return number
    return 0


def analyse(tree, files):
    python = [f for f in files if f.endswith(".py")]
    issues = []

    if python:
        for check in (bandit, pyflakes, dodgy, pylint):
            issues += check(tree, python)

    lockfiles = [f for f in files if f in LOCKFILES]

    if lockfiles:
        issues += advisories(tree, lockfiles)
    return issues


@dataclass
class Branch:
    """
    The files changed since the merge-base, and the merge-base's tree to compare with.
    """

    ref: str
    base: str
    files: list
    base_tree: Tree

    @classmethod
    def open(cls, ref, workdir):
        if ref is None:
            known = git("rev-parse", "-q", "--verify", "origin/master", ok=(0, 1))
            ref = "origin/master" if known else "master"

        base = git("merge-base", "HEAD", ref).strip()
        changed = git("diff", "--name-only", "--no-renames", "--diff-filter=d", base)
        untracked = git("ls-files", "--others", "--exclude-standard")

        files = sorted({f for f in (
            changed + untracked).splitlines() if Path(f).is_file()})

        if files:
            archive = git("archive", base, text=False)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(workdir, filter="data")
        return cls(ref, base, files, Tree(workdir))

    def in_base(self, files):
        return [f for f in files if (self.base_tree.root / f).is_file()]

    def compare(self):
        """
        Return the working tree's issues in the changed files, and those the base lacks.
        """
        with ThreadPoolExecutor(2) as pool:
            head = pool.submit(analyse, Tree("."), self.files)
            base = pool.submit(analyse, self.base_tree, self.in_base(self.files))
            head, base = head.result(), set(base.result())
        return head, [i for i in head if i not in base]


def report(branch, issues, new, show_all):
    marked = set(new) if show_all else set()
    path = None

    for issue in sorted(issues if show_all else new, key=lambda i: (i.path, i.line,
                                                                    i.rule)):
        if issue.path != path:
            path = issue.path
            print(f"\n{path}")

        mark = "*" if issue in marked else " "
        print(f" {mark}{issue.line:>5}  {issue.rule:<14} {issue.message}")

        if issue.hint:
            print(f"{'':22}{issue.hint}")

    where = f"{len(branch.files)} files changed since {branch.base[:10]} ({branch.ref})"
    print(f"\n{len(new)} new issues in {where}" if new else f"\nNo new issues in {where}")

    if new:
        msg = "Codacy fails a pull request on any new issue"
        print(msg + (" (* above)" if show_all else ""))
    elif len(issues) and not show_all:
        print(f"{len(issues)} issues there predate the branch: `just lint --all` "
              "lists them")


def ruff_fixes(files, unsafe):
    """
    Ruff's fixes for pyflakes rules, by file, rule and the name or line they concern.
    """
    cmd = ["ruff", "check", "--isolated", "--no-cache", "--select=F",
           "--output-format=json"]
    fixes = {}

    for d in json.loads(run([*cmd, *files])):
        fix = d.get("fix")

        if fix and fix["edits"] and (unsafe or fix["applicability"] == "safe"):
            path = str(Path(d["filename"]).relative_to(Path.cwd()))
            fixes[(path, d["code"], subject(d["message"],
                                            d["location"]["row"]))] = fix["edits"]
    return fixes


def subject(message, line):
    """
    What a pyflakes message is about: the name it quotes, else its line.
    """
    match = re.search(r"['`]([^'`]+)['`]", message)
    return match.group(1).split(" as ")[0] if match else line


def span(edit):
    return (edit["location"]["row"], edit["location"]["column"]), (
        edit["end_location"]["row"], edit["end_location"]["column"])


def overlaps(edits, others):
    return any(s < e2 and s2 < e for s, e in map(span,
                                                 edits) for s2, e2 in map(span, others))


def apply_edits(path, edits):
    """
    Apply Ruff's edits (1-based rows and columns, end exclusive) to a file.
    """
    lines = Path(path).read_text().splitlines(keepends=True)
    starts = [0]

    for line in lines:
        starts.append(starts[-1] + len(line))

    text = "".join(lines)

    for edit in sorted(edits, key=span, reverse=True):
        (row, col), (end_row, end_col) = span(edit)
        start, end = starts[row - 1] + col - 1, starts[end_row - 1] + end_col - 1
        text = text[:start] + (edit.get("content") or "") + text[end:]

    Path(path).write_text(text)


def fix(branch, unsafe):
    """
    Apply Ruff's fixes to the new pyflakes issues until it has none left to apply.
    """
    python = [f for f in branch.files if f.endswith(".py")]
    if not python:  # flake8 given no files would check the whole tree
        return

    in_base = branch.in_base(python)
    old = set(pyflakes(branch.base_tree, in_base)) if in_base else set()
    applied = 0

    for _ in range(FIX_PASSES):
        new = [i for i in pyflakes(Tree("."), python) if i not in old]
        fixes = ruff_fixes(sorted({i.path for i in new}), unsafe) if new else {}
        chosen = {}

        for issue in new:
            edits = fixes.get((issue.path, issue.rule.split()[1], subject(issue.message,
                                                                          issue.line)))

            if edits and not overlaps(chosen.get(issue.path, []), edits):
                chosen.setdefault(issue.path, []).extend(edits)
                applied += 1

        if not chosen:
            break

        for path, edits in chosen.items():
            apply_edits(path, edits)
    print(f"Applied {applied} fixes" if applied else "No new issue Ruff can fix")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("command", choices=("check", "fix"))
    parser.add_argument("--base",
                        help="branch to compare with (origin/master, else master)")
    parser.add_argument("--all", action="store_true",
                        help="list pre-existing issues too")
    parser.add_argument("--unsafe", action="store_true",
                        help="also apply Ruff's unsafe fixes")
    args = parser.parse_args(argv)

    try:
        with tempfile.TemporaryDirectory(prefix="lint-base-") as workdir:
            branch = Branch.open(args.base, workdir)

            if not branch.files:
                print(f"No files changed since {branch.base[:10]} ({branch.ref})")
                return 0

            if args.command == "fix":
                fix(branch, args.unsafe)

            issues, new = branch.compare()
            report(branch, issues, new, args.all)
            return 1 if new else 0
    except LintError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
