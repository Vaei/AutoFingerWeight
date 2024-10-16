# AutoFingerWeight

Automatically generates blockout weighting for fingers.

Usage instructions are on the tool's UI itself.

## Installation
On Windows, this goes in your `My Documents\maya\scripts\` folder

Either clone this repo into the scripts folder, or download the repo and extract the files into it.

The resulting structure should be `\maya\scripts\AutoFingerWeight\AutoFingerWeight.py` (etc).

Restart Maya if it is open.

## Running the Script
Run this from the Maya script editor, or add it to a shelf as a python command:
```py
from AutoFingerWeight import AutoFingerWeight as AFW
AFW.AutoFingerWeight()
```

## How it Works
1. A mesh representing the fingers as cylinders is generated with edge rings for knuckles.
2. The generated mesh is auto-weighted to the joints.
3. The auto-weights are copied from the generated mesh to the target mesh.

After that, you will want to manually smooth the weights to get the desired result.