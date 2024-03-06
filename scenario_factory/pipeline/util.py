from pathlib import Path

from commonroad.common.file_reader import CommonRoadFileReader


def successfully_open_commonroad_files_in_folder(folder: Path) -> None:
    """ "
    Count the number of successful and unsuccessful attempts to open CommonRoad files in a folder.

    Args:
        folder (Path): Path to the folder containing the CommonRoad files.
    """
    # simple check
    files = folder.glob("*.xml")
    files_total = 0
    files_successful = 0
    files_error = []
    for file in files:
        print(f"========== Open {file.stem} ==========")
        files_total += 1
        try:
            scenario, _ = CommonRoadFileReader(file).open()
            files_successful += 1
        except Exception as e:
            print(e)
            files_error.append(file.stem)

    print(f"Files in total: {files_total}")
    print(f"Files successful: {files_successful}")
