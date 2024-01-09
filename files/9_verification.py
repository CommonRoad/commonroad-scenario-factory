from pathlib import Path
from commonroad.common.file_reader import CommonRoadFileReader

# simple check
files = Path("globetrotter").rglob("*.xml")
files_total = 0
files_successful = 0
files_error = []
for file in files:
    print(f"========== Open {file.stem} ==========")
    files_total += 1
    try:
        scenario, _ = CommonRoadFileReader(file).open()
        files_successful += 1
    except:
        files_error.append(file.stem)

print(f"Files in total: {files_total}")
print(f"Files successful: {files_successful}")
