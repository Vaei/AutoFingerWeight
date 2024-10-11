import sys
import os
import inspect
import importlib
import maya.cmds as cmds

# Get the current script's directory using inspect
script_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
sys.path.append(script_dir)

# Reload the modules to reflect changes
import AutoFingerWeightCore
importlib.reload(AutoFingerWeightCore)

import AutoFingerWeightWidgets
importlib.reload(AutoFingerWeightWidgets)

from AutoFingerWeightCore import Core
from AutoFingerWeightWidgets import Widgets

class Statics:
    windowName = "autoFingerWeightWindow"
    version = "1.0.0"
    version_flags = "alpha"
    windowSize = [352, 400]
    windowTitle = "Auto Finger Weight"

    @staticmethod
    def get_friendly_version():
        return Statics.version + "-" + Statics.version_flags


class Globals:
    window = None


class AutoFingerWeight:
    def init_ui(self):
        pass

    def create_ui(self):
        self.init_ui()

    def __init__(self):
        # Create window if it isn't already there
        if not cmds.window(Statics.windowName, q=1, exists=1):
            Globals.window = cmds.window(Statics.windowName, wh=Statics.windowSize,
                                              title=Statics.windowTitle + " (v" + Statics.get_friendly_version() + ")",
                                              sizeable=0)
            cmds.showWindow(Globals.window)
            cmds.window(Globals.window, e=1, wh=Statics.windowSize)  # resize to default size when reopened
            self.init_ui()

            self.layout = cmds.columnLayout(p=Globals.window)
            self.radius_widget = Widgets.FloatSlider(self.layout, "Radius", 0.0001, 2, 0.5, 0.1)

            # Mesh Generator
            cmds.separator(p=self.layout, h=40)

            cmds.text(bgc=[0.2, 0.2, 0.2],
                      label="Select the first joint in each finger chain only.",
                      p=self.layout, align='left', wordWrap=True, width=Statics.windowSize[0])
            self.generate_btn = cmds.button(label="Generate", p=self.layout, w=Statics.windowSize[0],
                                            c=lambda _: self.generator_callback())

            self.mesh_ref = Widgets.ObjectReference(self.layout, "Weight Mesh:", "transform", "mesh")

            # Auto-Weighting
            cmds.separator(p=self.layout, h=40)
            cmds.text(bgc=[0.2, 0.2, 0.2],
                      label="Base Weight Joint is where any weight that isn't on the finger joints will go.\n"
                            "Select every finger joint to auto-weight to the weight mesh.",
                      p=self.layout, align='left', wordWrap=True, width=Statics.windowSize[0])
            self.weight_base_ref = Widgets.ObjectReference(self.layout, "Base Weight Joint:", "joint")

            self.weight_btn = cmds.button(label="Weight", p=self.layout, w=Statics.windowSize[0],
                                          enable=False, c=lambda _: self.weight_callback())

            # Script Jobs
            cmds.scriptJob(event=["Undo", self.on_undo], parent=Globals.window)
            cmds.scriptJob(event=["SceneOpened", self.on_scene_loaded], parent=Globals.window)
            cmds.scriptJob(event=["SelectionChanged", self.on_selection_changed], parent=Globals.window)

        else:
            Globals.window = Statics.windowName

    def on_undo(self):
        weight_mesh = self.mesh_ref.object
        if weight_mesh and not cmds.objExists(weight_mesh[0]):
            self.mesh_ref.clear_object()

    def on_scene_loaded(self):
        self.mesh_ref.clear_object()

    def on_selection_changed(self):
        self.update_weight_button()

    def generator_callback(self):
        generator = Core.GenerateWeightMesh(self.radius_widget.get_value())
        self.mesh_ref.assign_object(generator.mesh)

    def update_weight_button(self):
        weight_mesh = self.mesh_ref.object
        base_joint = self.weight_base_ref.object
        joints_selected = cmds.ls(selection=True, type="joint")
        print("Weight mesh:", weight_mesh)
        print("Base joint:", base_joint)
        print("Joints selected:", joints_selected)

        enable_button = (weight_mesh is not None and cmds.objExists(weight_mesh) and
                        base_joint is not None and cmds.objExists(base_joint) and
                        len(joints_selected) > 0)
        print("Enable button:", weight_mesh is not None and cmds.objExists(weight_mesh))
        cmds.button(self.weight_btn, edit=True, enable=bool(enable_button))

    def weight_callback(self):
        # Implement the weight callback logic here
        pass


if __name__ == '__main__':
    # Dev only helper for reopening the window each time the script runs
    if cmds.window(Statics.windowName, q=1, exists=1):
        cmds.deleteUI(Statics.windowName)

    AutoFingerWeight()
