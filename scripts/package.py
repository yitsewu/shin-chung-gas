"""只封裝整合原始檔；固定 ZIP metadata，排除快取與測試資料。"""

from pathlib import Path
import hashlib
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
source = root / "custom_components/scgas"
destination = root / "dist"
destination.mkdir(exist_ok=True)
with ZipFile(destination / "scgas.zip", "w", compression=ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or (path.suffix not in {".py", ".json", ".yaml"} and path.name != "LICENSE")
        ):
            continue
        info = ZipInfo(path.relative_to(source).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
        info.create_system = 3
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, path.read_text("utf-8").replace("\r\n", "\n").encode("utf-8"))
digest = hashlib.sha256((destination / "scgas.zip").read_bytes()).hexdigest()
(destination / "SHA256SUMS").write_text(digest + "  scgas.zip\n", encoding="utf-8")
print(digest)
