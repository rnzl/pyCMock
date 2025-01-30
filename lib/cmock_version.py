import re
from pathlib import Path

class CMockVersion:
    """
    CMock Version - Reads and parses the version from the cmock.h header file.
    """
    @staticmethod
    def get_version():
        """
        Retrieve the CMock version from the header file.
        """
        # Path to the header file
        path = Path(__file__).parent.parent / "src" / "cmock.h"

        # Initialize version components
        version_components = [0, 0, 0]

        try:
            # Read and parse the header file
            with path.open("r") as file:
                for line in file:
                    for index, field in enumerate(["VERSION_MAJOR", "VERSION_MINOR", "VERSION_BUILD"]):
                        match = re.search(rf"CMOCK_{field}\s+(\d+)", line)
                        if match:
                            version_components[index] = int(match.group(1))
        except Exception as e:
            raise RuntimeError("Can't find or read the header file.") from e

        # Return the version as a string
        return ".".join(map(str, version_components))


# Retrieve the version
CMOCK_VERSION = CMockVersion.get_version()

# Alias for the gem version
GEM = CMOCK_VERSION

if __name__ == "__main__":
    # Output the version if the script is run directly
    print(f"CMock Version: {CMOCK_VERSION}")
