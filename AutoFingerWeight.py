import sys
import os
import inspect
import importlib
import maya.cmds as cmds
import maya.mel as mel

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
    windowSize = [400, 600]
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
        with Core.UndoContext("UndoAutoFingerWeightUI", True):
            # Create window if it isn't already there
            if not cmds.window(Statics.windowName, q=1, exists=1):
                Globals.window = cmds.window(Statics.windowName, wh=Statics.windowSize,
                                                  title=Statics.windowTitle + " (v" + Statics.get_friendly_version() + ")",
                                                  sizeable=0)
                cmds.showWindow(Globals.window)
                cmds.window(Globals.window, e=1, wh=Statics.windowSize)  # resize to default size when reopened
                self.init_ui()

                self.layout = cmds.scrollLayout(p=Globals.window)

                bgc = [0.18, 0.25, 0.25]
                text_bgc = [0.2, 0.2, 0.2]
                width = Statics.windowSize[0] - 16

                # Mesh Generator
                self.gen_layout = cmds.frameLayout(p=self.layout, bgc=bgc, label="Step 1: Weight-Mesh Generator", collapsable=True, collapse=False, w=width)

                cmds.text(bgc=text_bgc,
                          label="\nSelect the first joint in each finger chain only.\nThinner values tend to have better results. Don't match the finger.\nMore length provides more smoothing falloff for weights.\n\n",
                          p=self.gen_layout, align='left', wordWrap=True, width=width)

                self.thickness_widget = Widgets.FloatSlider(self.gen_layout, "Finger Thickness", 0.0001, 1, 0.75, 0.1)
                self.length_widget = Widgets.FloatSlider(self.gen_layout, "Knuckle Length", 0.0001, 1, 0.5, 0.05)

                self.generate_btn = cmds.button(label="Generate", p=self.gen_layout, w=width,
                                                c=self.afw_generator_callback)

                self.mesh_ref = Widgets.ObjectReference(self.gen_layout, "Weight Mesh:", self.update_weight_button, "transform", "mesh")

                # Auto-Weighting
                cmds.separator(p=self.layout, h=40)
                self.auto_layout = cmds.frameLayout(p=self.layout, bgc=bgc, label="Step 2: Auto-Weight", collapsable=True, collapse=True, w=width)

                cmds.text(bgc=text_bgc,
                          label="\nBase Weight Joint is where any weight that isn't on the finger joints will go.\n\n"
                                "Select every finger joint to auto-weight to the weight mesh. Descendants will not be auto added. Use Select Hierarchy button to select them.\n\n\n",
                          p=self.auto_layout, align='left', wordWrap=True, width=width)
                self.weight_base_ref = Widgets.ObjectReference(self.auto_layout, "Base Weight Joint:", None, "joint")

                self.hierarchy_btn = cmds.button(label="Select Hierarchy", p=self.auto_layout, w=width,
                                              enable=False, c=lambda _: cmds.select(hierarchy=True))

                self.weight_btn = cmds.button(label="Auto-Weight", p=self.auto_layout, w=width,
                                              enable=False, c=self.afw_weight_callback)

                # Flush Undo Queue
                cmds.separator(p=self.auto_layout, h=20)
                cmds.text(bgc=text_bgc,
                          label="\nUndoing auto-weight by mistake can take a long time and isn't stable. Consider flushing the undo queue before continuing.\n",
                          p=self.auto_layout, align='left', wordWrap=True, width=width)
                self.flush_undo_btn = cmds.button(label="Flush Undo Queue", p=self.auto_layout, w=width, c=self.afw_flush_undo)

                # Transfer Weights
                cmds.separator(p=self.layout, h=40)
                self.xfer_layout = cmds.frameLayout(p=self.layout, bgc=bgc, label="Step 3: Transfer Weighting", collapsable=True, collapse=True, w=width)
                cmds.text(bgc=text_bgc,
                          label="\nTransfer weights from auto-weighted mesh to actual mesh.\nRequires a valid Weight Mesh assigned\nSelect the mesh or vertices (recommended) you wish to copy to.\n\n",
                          p=self.xfer_layout, align='left', wordWrap=True, width=width)
                self.xfer_btn = cmds.button(label="Transfer Weights", p=self.xfer_layout, w=width,
                                              enable=True, c=self.afw_transfer_weight_callback)

                # Update button states
                self.update_weight_button()

                # Script Jobs
                cmds.scriptJob(event=["Undo", self.on_undo], parent=Globals.window)
                cmds.scriptJob(event=["SceneOpened", self.on_scene_loaded], parent=Globals.window)
                cmds.scriptJob(event=["SelectionChanged", self.on_selection_changed], parent=Globals.window)

                # DEV ONLY
                # self.mesh_ref.assign_object(cmds.ls("autoFingerWeightMesh"))
                # self.weight_base_ref.assign_object(cmds.ls("spine_05|clavicle_l|upperarm_l|lowerarm_l|hand_l"))
                # dev_base_fingers = ['spine_05|clavicle_l|upperarm_l|lowerarm_l|hand_l|thumb_01_l', 'spine_05|clavicle_l|upperarm_l|lowerarm_l|hand_l|thumb_01_l|thumb_02_l', 'spine_05|clavicle_l|upperarm_l|lowerarm_l|hand_l|thumb_01_l|thumb_02_l|thumb_03_l', 'index_metacarpal_l|index_01_l', 'index_metacarpal_l|index_01_l|index_02_l', 'index_metacarpal_l|index_01_l|index_02_l|index_03_l', 'middle_metacarpal_l|middle_01_l', 'middle_metacarpal_l|middle_01_l|middle_02_l', 'middle_metacarpal_l|middle_01_l|middle_02_l|middle_03_l', 'ring_metacarpal_l|ring_01_l', 'ring_metacarpal_l|ring_01_l|ring_02_l', 'ring_metacarpal_l|ring_01_l|ring_02_l|ring_03_l', 'pinky_metacarpal_l|pinky_01_l', 'pinky_metacarpal_l|pinky_01_l|pinky_02_l', 'pinky_metacarpal_l|pinky_01_l|pinky_02_l|pinky_03_l']
                # cmds.select(dev_base_fingers)
            else:
                Globals.window = Statics.windowName

    def on_undo(self):
        # Check if the undo state is the one we want to catch
        last_undo = cmds.undoInfo(q=True, redoName=True)
        if last_undo == "__main__.afw_generator_callback":
            # Clear the mesh reference if it doesn't exist anymore
            weight_mesh = self.mesh_ref.object
            if weight_mesh and not cmds.objExists(weight_mesh[0]):
                self.mesh_ref.clear_object()
        elif last_undo == "__main__.afw_weight_callback":
            # Leave weight paint mode if we were in it
            if 'artAttrSkin' in cmds.currentCtx():
                cmds.setToolTo('selectSuperContext')

    def on_scene_loaded(self):
        self.mesh_ref.clear_object()
        self.weight_base_ref.clear_object()

    def on_selection_changed(self):
        self.update_weight_button()

    def afw_generator_callback(self, *args):
        generator = Core.GenerateWeightMesh(self.thickness_widget.get_value(), self.length_widget.get_value())
        self.mesh_ref.assign_object(generator.mesh)

    def update_weight_button(self, *args):
        weight_mesh = self.mesh_ref.object
        base_joint = self.weight_base_ref.object
        joints_selected = cmds.ls(selection=True, type="joint")

        print("Weight Mesh: ", weight_mesh)

        enable_layout = weight_mesh and cmds.objExists(weight_mesh[0])
        enable_button = (enable_layout and base_joint and cmds.objExists(base_joint[0])
                         and len(joints_selected) > 0)

        cmds.frameLayout(self.auto_layout, edit=True, enable=bool(enable_layout))
        cmds.button(self.weight_btn, edit=True, enable=bool(enable_button))
        cmds.button(self.hierarchy_btn, edit=True, enable=bool(enable_button))

        cmds.frameLayout(self.auto_layout, edit=True, collapse=not enable_layout)

    def afw_weight_callback(self, *args):
        Core.AutoWeightMesh(self.mesh_ref.object, self.weight_base_ref.object)

    def update_flush_undo_button(self):
        can_flush = self.can_flush_undo()
        print("Can flush undo: ", can_flush)
        cmds.button(self.flush_undo_btn, edit=True, enable=can_flush)

    def can_flush_undo(self):
        has_empty_undo_queue = cmds.undoInfo(undoQueueEmpty=True, query=True)
        return not has_empty_undo_queue

    def afw_flush_undo(self, *args):
        cmds.flushUndo()
        self.update_flush_undo_button()

    @staticmethod
    def get_selected_mesh():
        selection = cmds.ls(selection=True, type="transform")
        if not selection:
            # Do we have vertices selected instead?
            selection = cmds.ls(selection=True)
            if cmds.objectType(selection[0]) == "mesh":
                return selection
        shape_nodes = cmds.listRelatives(selection[0], shapes=True, fullPath=True)
        if shape_nodes and cmds.nodeType(shape_nodes[0]) == "mesh":
            return selection
        return None

    def afw_transfer_weight_callback(self, *args):
        """
        Transfer weights from the weight mesh to the selected mesh or vertices.
        """
        weight_mesh = self.mesh_ref.object
        target_mesh = self.get_selected_mesh()
        if not weight_mesh:
            cmds.warning("No weight mesh assigned.")
            return
        if not target_mesh:
            cmds.warning("No valid mesh selected.")
            return

        # Get skin cluster from each mesh
        weight_skin_cluster = cmds.ls(cmds.listHistory(weight_mesh), type='skinCluster')[0]
        target_skin_cluster = cmds.ls(cmds.listHistory(target_mesh), type='skinCluster')[0]

        cmds.select(weight_mesh)
        cmds.select(target_mesh, add=True)

        mel.eval(f'copySkinWeights -ss "{weight_skin_cluster}" -ds "{target_skin_cluster}" -noMirror -surfaceAssociation closestPoint -influenceAssociation oneToOne;')


if __name__ == '__main__':
    with Core.UndoContext("UndoAutoFingerWeightMain", True):
        # Dev only helper for reopening the window each time the script runs
        if cmds.window(Statics.windowName, q=1, exists=1):
            cmds.deleteUI(Statics.windowName)

        AutoFingerWeight()
