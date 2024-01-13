# pylint: skip-file

import argparse
import glob
import io
import os
import subprocess
import sys

from github import Github
from pylint import lint as pl_run
from pylint.__pkginfo__ import __version__ as pl_version
from cython_lint import cython_lint as cl_run
from cython_lint import __version__ as cl_version
from cpplint import __VERSION__ as cp_version


def main():
    # Process command line arguments
    parser = argparse.ArgumentParser(
        "Check if any opened issues have been closed, run linters, and open an issue if any complain")
    parser.add_argument("--token", help="The GitHub API token to use")
    parser.add_argument("--repo", help="The owner and repository we are operating on")
    args = parser.parse_args()
    # Connect to GitHub REST API
    gh = Github(args.token)
    # Run the linters
    pylint(gh, args.repo)
    cython_lint(gh, args.repo)
    cpplint(gh, args.repo)


def _check_issues(gh, repo, tool):
    open_issues = gh.search_issues(f"repo:{repo} label:automated/{tool} is:issue is:open")
    if open_issues.totalCount != 0:
        print(f"Skipping '{tool}' run due to existing issue {open_issues[0].html_url}.")
        return True
    else:
        return False


def _file_issue(gh, repo, tool, tool_args, tool_version, output):
    issue_title = f"New version of pylint ({tool_version}) identifies new issues"
    issue_body = (f"A version of `{tool}` is available in the Python package repositories that identifies issues "
                  f"with the `spotfire` package.  Since we attempt to keep all lint issues out of the source "
                  f"code (either by fixing the issue identified or by disabling that message with a localized "
                  f"comment), this is indicative of a new check in this new version of `{tool}`.\n\n"
                  f"Please investigate these issues, and either fix the source or disable the check with a "
                  f"comment.  Further checks by this automation will be held until this issue is closed.  Make "
                  f"sure that the fix updates the `{tool}` requirement in `pyproject.toml` to the version "
                  f"identified here ({tool_version}).\n\n"
                  f"For reference, here is the output of this version of `{tool}`:\n\n"
                  f"```\n"
                  f"$ {tool} {tool_args}\n"
                  f"{output}\n"
                  f"```\n\n"
                  f"*This issue was automatically opened by the `pylint.yaml` workflow.*\n")
    repo = gh.get_repo(repo)
    repo_label = repo.get_label(f"automated/{tool}")
    new_issue = repo.create_issue(title=issue_title, body=issue_body, labels=[repo_label])
    print(f"Opened issue {new_issue.html_url}")


class _StdoutCapture:
    def __init__(self):
        self._saved = None
        self._capture = io.StringIO()

    def __enter__(self):
        self._saved = sys.stdout
        sys.stdout = self._capture

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._saved
        self._saved = None

    def output(self):
        return self._capture.getvalue()


def pylint(gh, repo):
    # Determine if we should run pylint
    if _check_issues(gh, repo, "pylint"):
        return

    # Now run pylint
    with _StdoutCapture() as capture:
        result = pl_run.Run(["spotfire"], exit=False)
    if result.linter.msg_status == 0:
        return

    # File an issue
    _file_issue(gh, repo, "pylint", "spotfire", pl_version, capture.output())


def cython_lint(gh, repo):
    # Determine if we should run cython-lint
    if _check_issues(gh, repo, "cython-lint"):
        return

    # Now run cython-lint
    with _StdoutCapture() as capture:
        result = cl_run.main(["spotfire", "vendor"])
    if result == 0:
        return

    # File an issue
    _file_issue(gh, repo, "cython-lint", "spotfire vendor", cl_version, capture.output())


def cpplint(gh, repo):
    # Determine if we should run cpplint
    if _check_issues(gh, repo, "cpplint"):
        return

    # Now run cpplint
    command = [sys.executable, "-m", "cpplint"]
    command.extend(glob.glob("spotfire/*_helpers.[ch]"))
    result = subprocess.run(command, capture_output=True, check=False)
    if not result.returncode:
        return

    # File an issue
    _file_issue(gh, repo, "cpplint", "spotfire/*_helpers.[ch]", cp_version, result.stdout.decode("utf-8"))


if __name__ == "__main__":
    main()
