import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArelleResult:
    status: str
    return_code: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    log_excerpt: str


def validate_instance(path: str | Path, timeout: int = 120) -> ArelleResult:
    target = Path(path).resolve()
    with tempfile.TemporaryDirectory() as directory:
        log_path = Path(directory) / "arelle.log"
        command = [
            sys.executable,
            "-m",
            "arelle.CntlrCmdLine",
            "--file",
            str(target),
            "--validate",
            "--internetConnectivity=offline",
            "--formula=none",
            "--logFile",
            str(log_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        lines = [line.strip() for line in log_text.splitlines() if line.strip()]
        errors = tuple(line for line in lines if re.search(r"\[error\]", line, re.IGNORECASE))
        warnings = tuple(line for line in lines if re.search(r"\[warning\]", line, re.IGNORECASE))
        if completed.returncode != 0 or errors:
            status = "failed"
        elif warnings:
            status = "warning"
        else:
            status = "passed"
        return ArelleResult(
            status=status,
            return_code=completed.returncode,
            errors=errors[:20],
            warnings=warnings[:20],
            log_excerpt="\n".join(lines[-20:]),
        )
