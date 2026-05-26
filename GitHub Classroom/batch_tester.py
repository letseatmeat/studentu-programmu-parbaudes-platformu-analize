#!/usr/bin/env python3
"""
Diagnostic batch tester for the bus routes assignment.

The checker keeps the original strict pass/fail logic, but also records
diagnostic indicators:
- whether the program compiled;
- whether the expected content was present in stdout;
- whether the required "result:" marker was present;
- whether "result:" was printed as a separate line;
- whether the program exited with an acceptable return code.

This allows distinguishing between:
1) fully correct solutions;
2) content-correct solutions with output-format problems;
3) wrong-content solutions;
4) compilation/runtime/timeout problems.
"""

import argparse
import csv
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


TESTS = [
    {
        "name": "a_route",
        "stdin": "a\nRiga\nKraslava\ne\n",
        "kind": "route",
        "expected": [
            "Riga Kraslava Pr 15:00 11.00",
            "Riga Kraslava Pr 18:00 11.00",
        ],
    },
    {
        "name": "b_day",
        "stdin": "b\nPt\ne\n",
        "kind": "route",
        "expected": [
            "Riga Ventspils Pt 09:00 6.70",
            "Liepaja Ventspils Pt 17:00 5.50",
        ],
    },
    {
        "name": "c_price",
        "stdin": "c\n5.90\ne\n",
        "kind": "route",
        "expected": [
            "Kraslava Daugavpils Ot 10:00 3.00",
            "Dagda Kraslava Ce 18:00 2.50",
            "Liepaja Ventspils Pt 17:00 5.50",
        ],
    },
    {
        "name": "d_errtxt",
        "stdin": "d\ne\n",
        "kind": "csv",
        "expected": [
            "Ventsplis,8.00,Liepaja,Sv,20:00",
            "Dagda,Sv",
            "Dagda,Kraslava,Ce,18:00,2.50,Sv",
        ],
    },
]


def collapse_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def strip_all_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def safe_name(name: str) -> str:
    """Create a safe directory/file name for logs."""
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def norm_line(line: str, kind: str) -> str:
    if kind == "route":
        return collapse_spaces(line)
    if kind == "csv":
        return strip_all_ws(line)
    return line.strip()


def normalize_output(stdout: str, kind: str):
    lines = []
    for raw in stdout.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        t = raw.strip()
        if not t:
            continue
        lines.append(norm_line(t, kind))
    return lines


def result_marker_present_anywhere(lines) -> bool:
    """Detect result: even if it is printed in the same line as a prompt."""
    compact = strip_all_ws("\n".join(lines)).lower()
    return "result:" in compact


def result_marker_on_separate_line(lines) -> bool:
    """Strict requirement: result: must be a separate output line."""
    return any(strip_all_ws(line).lower() == "result:" for line in lines)


def contains_expected_sequence(lines, expected):
    """
    Check whether all expected lines appear in the expected order.
    Extra lines are allowed. This matches the original checker behavior.
    """
    idx = 0
    for line in lines:
        if idx < len(expected) and line == expected[idx]:
            idx += 1
    return idx == len(expected)


def classify_test(strict_ok: bool, content_ok: bool, result_any_ok: bool,
                  result_line_ok: bool, rc_ok: bool, timed_out: bool,
                  run_error: str = "") -> str:
    if strict_ok:
        return "strict_pass"
    if timed_out:
        return "timeout"
    if run_error:
        return f"run_error:{run_error}"
    if not rc_ok:
        return "runtime_error"
    if content_ok and result_any_ok and not result_line_ok:
        return "content_ok_format_issue"
    if content_ok and not result_any_ok:
        return "content_ok_missing_result_marker"
    if not content_ok and (result_line_ok or result_any_ok):
        return "wrong_content"
    if not content_ok and not result_any_ok:
        return "wrong_content_and_missing_result_marker"
    return "failed"


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", errors="replace")


def run_test(exe: Path, workdir: Path, test: dict, timeout: int, log_dir: Path | None = None):
    """
    Run one functional test and return a dictionary with strict and diagnostic results.
    """
    test_name = test["name"]
    stdin = test["stdin"]
    kind = test["kind"]
    expected = test["expected"]

    errf = workdir / "err.txt"
    if errf.exists():
        errf.unlink()

    if log_dir is not None:
        test_log_dir = log_dir / safe_name(test_name)
        test_log_dir.mkdir(parents=True, exist_ok=True)
        write_text(test_log_dir / "stdin.txt", stdin)
        write_text(test_log_dir / "expected.txt", "\n".join(expected) + "\n")
    else:
        test_log_dir = None

    try:
        proc = subprocess.run(
            [str(exe)],
            input=stdin.encode("utf-8", errors="ignore"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(workdir),
            timeout=timeout,
        )
        timed_out = False
        run_error = ""
        returncode = proc.returncode
        stdout_text = proc.stdout.decode("latin1", errors="replace")
        stderr_text = proc.stderr.decode("latin1", errors="replace")
    except subprocess.TimeoutExpired as e:
        timed_out = True
        run_error = ""
        returncode = -999
        stdout_text = (e.stdout or b"").decode("latin1", errors="replace") if isinstance(e.stdout, bytes) else str(e.stdout or "")
        stderr_text = (e.stderr or b"").decode("latin1", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")
    except Exception as e:
        timed_out = False
        run_error = type(e).__name__
        returncode = -998
        stdout_text = ""
        stderr_text = str(e)

    out_lines = normalize_output(stdout_text, kind)
    exp_lines = [norm_line(x, kind) for x in expected]

    content_ok = contains_expected_sequence(out_lines, exp_lines)
    result_any_ok = result_marker_present_anywhere(out_lines)
    result_line_ok = result_marker_on_separate_line(out_lines)
    rc_ok = returncode in (0, 1)

    strict_ok = (not timed_out) and (not run_error) and rc_ok and result_line_ok and content_ok

    classification = classify_test(
        strict_ok=strict_ok,
        content_ok=content_ok,
        result_any_ok=result_any_ok,
        result_line_ok=result_line_ok,
        rc_ok=rc_ok,
        timed_out=timed_out,
        run_error=run_error,
    )

    detail = []
    if timed_out:
        detail.append("timeout")
    if run_error:
        detail.append(f"run_error:{run_error}")
    if not result_line_ok:
        detail.append("missing_result_line")
    if not result_any_ok:
        detail.append("missing_result_marker")
    if not content_ok:
        detail.append("wrong_output")
    if not rc_ok:
        detail.append(f"rc={returncode}")

    sample = "\n".join(out_lines[:8])[:600]
    if sample:
        detail.append(f"out={sample}")

    note = ";".join(detail)

    if test_log_dir is not None:
        write_text(test_log_dir / "stdout.txt", stdout_text)
        write_text(test_log_dir / "stderr.txt", stderr_text)
        write_text(test_log_dir / "actual_normalized.txt", "\n".join(out_lines) + ("\n" if out_lines else ""))
        write_text(test_log_dir / "note.txt", note + "\n")
        write_text(
            test_log_dir / "diagnostic.txt",
            "\n".join([
                f"strict_ok={int(strict_ok)}",
                f"content_ok={int(content_ok)}",
                f"result_marker_ok={int(result_any_ok)}",
                f"result_line_ok={int(result_line_ok)}",
                f"rc_ok={int(rc_ok)}",
                f"returncode={returncode}",
                f"classification={classification}",
            ]) + "\n",
        )

    return {
        "strict_ok": int(strict_ok),
        "note": note,
        "content_ok": int(content_ok),
        "result_marker_ok": int(result_any_ok),
        "result_line_ok": int(result_line_ok),
        "rc_ok": int(rc_ok),
        "returncode": returncode,
        "classification": classification,
    }


def compile_source(src: Path, exe: Path, timeout: int, log_dir: Path | None = None):
    cmd = ["g++", "-std=gnu++17", "-O2", "-pipe", str(src), "-o", str(exe)]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        if log_dir is not None:
            write_text(log_dir / "compile_command.txt", " ".join(cmd) + "\n")
            write_text(log_dir / "compile_stdout.txt", "")
            write_text(log_dir / "compile_stderr.txt", "compile_timeout\n")
        return False, "compile_timeout"

    stdout_text = proc.stdout.decode("latin1", errors="replace")
    stderr_text = proc.stderr.decode("latin1", errors="replace")

    if log_dir is not None:
        write_text(log_dir / "compile_command.txt", " ".join(cmd) + "\n")
        write_text(log_dir / "compile_stdout.txt", stdout_text)
        write_text(log_dir / "compile_stderr.txt", stderr_text)

    if proc.returncode != 0:
        err = "\n".join(stderr_text.splitlines()[:20])
        return False, err[:1500]

    return True, ""


def parse_args():
    p = argparse.ArgumentParser(
        description="Diagnostic batch-test .cpp submissions for the bus routes assignment."
    )
    p.add_argument("--zip", default="/mnt/data/progas.zip", help="ZIP archive with .cpp files")
    p.add_argument("--db", default="/mnt/data/db.csv", help="db.csv test file")
    p.add_argument("--out-csv", default="webcat_batch_report.csv", help="Output CSV report")
    p.add_argument("--out-summary", default="webcat_batch_summary.txt", help="Output text summary")
    p.add_argument("--out-junit", default="", help="Optional JUnit XML report path")
    p.add_argument("--out-dir", default="", help="Optional directory for detailed per-file logs")
    p.add_argument("--limit", type=int, default=0, help="Only test the first N files (0 = all)")
    p.add_argument("--timeout", type=int, default=4, help="Seconds per program run")
    p.add_argument("--compile-timeout", type=int, default=20, help="Seconds per compilation")
    p.add_argument(
        "--fail-on-any-failure",
        action="store_true",
        help="Exit with status 1 if at least one submission fails strict checks",
    )
    return p.parse_args()


def add_junit_testcase(testsuite, classname: str, name: str, ok: bool, message: str, details: str = ""):
    case = ET.SubElement(testsuite, "testcase", {
        "classname": classname,
        "name": name,
    })
    if not ok:
        failure = ET.SubElement(case, "failure", {
            "message": message[:250],
            "type": "AssertionError",
        })
        failure.text = details[:4000]


def write_junit_report(rows, out_junit: Path):
    testsuite = ET.Element("testsuite", {
        "name": "student_cpp_batch_diagnostic",
        "tests": str(len(rows) * len(TESTS)),
        "failures": str(sum(1 for r in rows for t in TESTS if not r.get(t["name"], 0))),
    })

    for row in rows:
        classname = row["file"]
        for test in TESTS:
            tname = test["name"]
            ok = bool(row.get(tname, 0))
            classification = row.get(f"{tname}_classification", "")
            note = row.get(f"{tname}_note", "")
            details = (
                f"file={row['file']}\n"
                f"test={tname}\n"
                f"strict_ok={row.get(tname, 0)}\n"
                f"content_ok={row.get(tname + '_content_ok', 0)}\n"
                f"result_marker_ok={row.get(tname + '_result_marker_ok', 0)}\n"
                f"result_line_ok={row.get(tname + '_result_line_ok', 0)}\n"
                f"rc_ok={row.get(tname + '_rc_ok', 0)}\n"
                f"classification={classification}\n"
                f"note={note}\n"
            )
            add_junit_testcase(
                testsuite,
                classname=classname,
                name=tname,
                ok=ok,
                message=classification or "failed",
                details=details,
            )

    tree = ET.ElementTree(testsuite)
    out_junit.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_junit, encoding="utf-8", xml_declaration=True)


def diagnostic_group_for_row(row):
    if not row["compile_ok"]:
        return "compile_error"

    strict_all = bool(row["all_pass"])
    if strict_all:
        return "strict_pass"

    content_all = all(bool(row.get(t["name"] + "_content_ok", 0)) for t in TESTS)
    any_format_issue = any(
        row.get(t["name"] + "_classification", "") in (
            "content_ok_format_issue",
            "content_ok_missing_result_marker",
        )
        for t in TESTS
    )
    any_runtime = any(
        row.get(t["name"] + "_classification", "") in ("runtime_error", "timeout")
        or str(row.get(t["name"] + "_classification", "")).startswith("run_error:")
        for t in TESTS
    )

    if content_all and any_format_issue:
        return "content_ok_format_issue"
    if any_runtime:
        return "runtime_or_timeout"
    if any(row.get(t["name"] + "_content_ok", 0) for t in TESTS):
        return "partial_content_ok"
    return "wrong_content"


def main():
    args = parse_args()

    zip_path = Path(args.zip)
    db_path = Path(args.db)
    out_csv = Path(args.out_csv)
    out_summary = Path(args.out_summary)
    out_junit = Path(args.out_junit) if args.out_junit else None
    out_dir = Path(args.out_dir) if args.out_dir else None

    if not zip_path.exists():
        print(f"ERROR: ZIP archive not found: {zip_path}", file=sys.stderr)
        return 2
    if not db_path.exists():
        print(f"ERROR: db.csv not found: {db_path}", file=sys.stderr)
        return 2

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    with zipfile.ZipFile(zip_path) as zf:
        members = [i for i in zf.infolist() if i.filename.lower().endswith(".cpp")]
        members.sort(key=lambda i: Path(i.filename).name)

        if args.limit > 0:
            members = members[: args.limit]

        total_members = len(members)

        with tempfile.TemporaryDirectory(prefix="webcat_batch_") as td:
            root = Path(td)

            for idx, info in enumerate(members, start=1):
                src_name = Path(info.filename).name
                print(f"[{idx}/{total_members}] {src_name}", flush=True)

                work = root / safe_name(src_name).replace(".cpp", "")
                work.mkdir(parents=True, exist_ok=True)

                file_log_dir = out_dir / safe_name(src_name) if out_dir is not None else None
                if file_log_dir is not None:
                    file_log_dir.mkdir(parents=True, exist_ok=True)

                src_path = work / src_name
                src_path.write_bytes(zf.read(info.filename))
                shutil.copy2(db_path, work / "db.csv")

                exe = work / "prog"
                compile_ok, compile_msg = compile_source(
                    src_path,
                    exe,
                    args.compile_timeout,
                    log_dir=file_log_dir,
                )

                row = {
                    "file": src_name,
                    "compile_ok": int(bool(compile_ok)),
                    "compile_note": compile_msg,
                }

                strict_passes = 0
                content_passes = 0
                failed_parts = []
                format_issue_tests = []
                wrong_content_tests = []

                if compile_ok:
                    for test in TESTS:
                        tname = test["name"]
                        result = run_test(
                            exe=exe,
                            workdir=work,
                            test=test,
                            timeout=args.timeout,
                            log_dir=file_log_dir,
                        )

                        row[tname] = result["strict_ok"]
                        row[tname + "_note"] = result["note"]
                        row[tname + "_content_ok"] = result["content_ok"]
                        row[tname + "_result_marker_ok"] = result["result_marker_ok"]
                        row[tname + "_result_line_ok"] = result["result_line_ok"]
                        row[tname + "_rc_ok"] = result["rc_ok"]
                        row[tname + "_returncode"] = result["returncode"]
                        row[tname + "_classification"] = result["classification"]

                        strict_passes += result["strict_ok"]
                        content_passes += result["content_ok"]

                        if not result["strict_ok"]:
                            failed_parts.append(f"{tname}: {result['classification']}")
                        if result["classification"] in (
                            "content_ok_format_issue",
                            "content_ok_missing_result_marker",
                        ):
                            format_issue_tests.append(tname)
                        if not result["content_ok"]:
                            wrong_content_tests.append(tname)
                else:
                    for test in TESTS:
                        tname = test["name"]
                        row[tname] = 0
                        row[tname + "_note"] = "not_compiled"
                        row[tname + "_content_ok"] = 0
                        row[tname + "_result_marker_ok"] = 0
                        row[tname + "_result_line_ok"] = 0
                        row[tname + "_rc_ok"] = 0
                        row[tname + "_returncode"] = ""
                        row[tname + "_classification"] = "not_compiled"
                        failed_parts.append(f"{tname}: not_compiled")
                        wrong_content_tests.append(tname)

                row["passed_tests"] = strict_passes
                row["content_tests_passed"] = content_passes
                row["failed_tests"] = len(TESTS) - strict_passes
                row["all_pass"] = int(compile_ok and strict_passes == len(TESTS))
                row["all_content_ok"] = int(compile_ok and content_passes == len(TESTS))
                row["failed_parts"] = " | ".join(failed_parts)
                row["format_issue_tests"] = ",".join(format_issue_tests)
                row["wrong_content_tests"] = ",".join(wrong_content_tests)
                row["diagnostic_group"] = diagnostic_group_for_row(row)

                rows.append(row)

    fieldnames = ["file", "compile_ok", "compile_note"]

    for test in TESTS:
        tname = test["name"]
        fieldnames += [
            tname,
            tname + "_note",
            tname + "_content_ok",
            tname + "_result_marker_ok",
            tname + "_result_line_ok",
            tname + "_rc_ok",
            tname + "_returncode",
            tname + "_classification",
        ]

    fieldnames += [
        "passed_tests",
        "content_tests_passed",
        "failed_tests",
        "all_pass",
        "all_content_ok",
        "failed_parts",
        "format_issue_tests",
        "wrong_content_tests",
        "diagnostic_group",
    ]

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    compiled = sum(r["compile_ok"] for r in rows)
    compile_failed = total - compiled
    strict_all_pass = sum(r["all_pass"] for r in rows)
    content_all_ok = sum(r["all_content_ok"] for r in rows)

    strict_counts = {t["name"]: sum(r[t["name"]] for r in rows) for t in TESTS}
    content_counts = {t["name"]: sum(r[t["name"] + "_content_ok"] for r in rows) for t in TESTS}

    group_counts = {}
    for r in rows:
        group_counts[r["diagnostic_group"]] = group_counts.get(r["diagnostic_group"], 0) + 1

    out_summary.parent.mkdir(parents=True, exist_ok=True)
    with out_summary.open("w", encoding="utf-8") as f:
        f.write("Batch diagnostic summary\n")
        f.write("========================\n")
        f.write(f"Total files: {total}\n")
        f.write(f"Compiled: {compiled}\n")
        f.write(f"Compile failed: {compile_failed}\n")
        f.write(f"Strictly passed all 4 tests: {strict_all_pass}\n")
        f.write(f"Content-correct in all 4 tests: {content_all_ok}\n")
        f.write("\nStrict pass counts by test:\n")
        for k, v in strict_counts.items():
            f.write(f"{k}: {v}\n")
        f.write("\nContent-ok counts by test:\n")
        for k, v in content_counts.items():
            f.write(f"{k}: {v}\n")
        f.write("\nDiagnostic groups:\n")
        for k in sorted(group_counts):
            f.write(f"{k}: {group_counts[k]}\n")

        f.write("\nFiles failing strict checks:\n")
        for r in rows:
            if not r["all_pass"]:
                f.write(f"{r['file']}: {r['diagnostic_group']}; {r['failed_parts']}\n")

        f.write("\nFiles with content-correct but format-related problems:\n")
        for r in rows:
            if r["diagnostic_group"] == "content_ok_format_issue":
                f.write(f"{r['file']}: format_issue_tests={r['format_issue_tests']}\n")

        f.write("\nFiles passing all strict tests:\n")
        for r in rows:
            if r["all_pass"]:
                f.write(r["file"] + "\n")

    if out_junit is not None:
        write_junit_report(rows, out_junit)

    print("\nDone.")
    print(out_summary.read_text(encoding="utf-8", errors="replace"))
    print(f"CSV report: {out_csv.resolve()}")
    if out_junit is not None:
        print(f"JUnit report: {out_junit.resolve()}")
    if out_dir is not None:
        print(f"Detailed logs: {out_dir.resolve()}")

    if args.fail_on_any_failure and strict_all_pass != total:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
