#!/usr/bin/env python3
"""Exercise the actual xv6 guest and retain its serial output; no dependencies."""
import argparse
import os
import re
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def run_vmtest(expect, send):
    """Run the page-protection suite and correlate its faults with the kernel."""
    send("vmtest")
    start = len(transcript)
    expect(b"$ ")   # returns whether vmtest finished or was killed
    output = bytes(transcript[start:]).replace(b"\r", b"")
    if b"vmtest: FAIL" in output or b"vmtest: ALL PASSED\n" not in output:
        raise RuntimeError("vmtest reported a failure")
    match = re.search(rb"vmtest: (\d+) child write faults observed", output)
    diagnostics = re.findall(rb"pid \d+ vmtest: trap 14 err 7 ", output)
    if not match or int(match.group(1)) != len(diagnostics) or not diagnostics:
        raise RuntimeError(f"vmtest saw {match and match.group(1)} faults but the "
                           f"kernel printed {len(diagnostics)} write-fault diagnostics")
    send("echo XV6_SHELL_ALIVE_AFTER_VMTEST")
    expect(b"\nXV6_SHELL_ALIVE_AFTER_VMTEST\n")
    expect(b"$ ")
    print(f"PASS: vmtest page protection ({len(diagnostics)} expected user write faults, "
          "shell still alive)")


transcript = bytearray()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", default="qemu-system-i386")
    parser.add_argument("--full", action="store_true", help="also run upstream usertests")
    parser.add_argument("--timeout", type=float, default=180, help="seconds per expected response")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    qemu = shutil.which(args.qemu)
    if not qemu:
        parser.error(f"QEMU not found: {args.qemu}")
    for disk in ("fs.img", "xv6.img"):
        if not (ROOT / disk).is_file():
            parser.error(f"Missing {disk}; run ./scripts/xv6 build first")
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    log_path = artifacts / ("usertests.log" if args.full else "smoke.log")
    command = [qemu, "-display", "none", "-monitor", "none", "-serial", "stdio",
               "-no-reboot", "-nic", "none", "-smp", "1", "-m", "512",
               "-drive", "file=fs.img,index=1,media=disk,format=raw",
               "-drive", "file=xv6.img,index=0,media=disk,format=raw"]
    with log_path.open("wb") as log:
        proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        pending = bytearray()

        def expect(marker):
            deadline = time.monotonic() + args.timeout
            while marker not in pending:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Timed out waiting for {marker!r}")
                for key, _ in selector.select(timeout=0.5):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        raise RuntimeError("QEMU stopped before the expected response")
                    log.write(chunk)
                    transcript.extend(chunk)
                    log.flush()
                    pending.extend(chunk.replace(b"\r", b""))
                    if b"panic:" in pending:
                        raise RuntimeError("Guest kernel panicked")
            end = pending.index(marker) + len(marker)
            del pending[:end]

        def send(command):
            proc.stdin.write(command.encode() + b"\n")
            proc.stdin.flush()

        try:
            expect(b"init: starting sh\n")
            expect(b"$ ")
            send("echo XV6_BASELINE_BOOT_OK")
            expect(b"\nXV6_BASELINE_BOOT_OK\n")
            expect(b"$ ")
            send("forktest")
            expect(b"fork test OK\n")
            expect(b"$ ")
            print("PASS: xv6 boot, shell command and upstream forktest")
            run_vmtest(expect, send)
            if args.full:
                send("usertests")
                expect(b"ALL TESTS PASSED\n")
                expect(b"$ ")
                print("PASS: upstream usertests")
        finally:
            selector.close()
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            proc.stdin.close()
            proc.stdout.close()
    print(f"Serial log: {log_path.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"FAIL: {exc}; inspect artifacts/*.log", file=sys.stderr)
        sys.exit(1)
