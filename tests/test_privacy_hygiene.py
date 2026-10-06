import hashlib
import subprocess
from pathlib import Path

# SHA-256 values of lower-case forbidden sample name stems; keep names out of source.
_FORBIDDEN_STEM_HASHES = {
    "a5dc5cb716a2f252e7ae54b6588c3d098c0fd6d788d6f16392f7b5bd29f0fa16",
    "5808131a76fd4fd12dac09f6577a8310e2a96ed1fb112e946ed5fd5fb24d867f",
    "33992f08035d209217bd1e2d3ac5d03179c33b90d63f399cfcc7850a2aa75d5f",
    "9feb928f7de99b4c784e04ce919d212c0f90809b9410f9f6546cc8c08446ab0d",
    "1502fe3254c08a797a35078d979660fb66a51393dec732df85d8fd284521ecea",
    "b13516707d22bf83a46848bc8f3d80cf8fc0dba7797199e417e286ebb681affd",
}


def test_tracked_text_has_no_private_sample_name_stems() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "-C", str(root), "grep", "-I", "-n", "-i", "-e", ".", "--"],
        capture_output=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr.decode(errors="replace")
    offenders = []
    for line in result.stdout.splitlines():
        lowered = line.decode(errors="replace").lower()
        if any(
            hashlib.sha256(stem.encode()).hexdigest() in _FORBIDDEN_STEM_HASHES
            for stem in _candidate_words(lowered)
        ):
            offenders.append(line.decode(errors="replace"))
    message = "Forbidden sample-name stem found in tracked text:\n" + "\n".join(offenders)
    assert not offenders, message


def _candidate_words(text: str) -> list[str]:
    words = []
    current = []
    for character in text:
        if "a" <= character <= "z":
            current.append(character)
        elif current:
            words.append("".join(current))
            current.clear()
    if current:
        words.append("".join(current))
    return words
