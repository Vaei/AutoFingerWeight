import maya.cmds as cmds

class Widgets:
    class FloatSlider:
        """
        A reusable class to create a label, slider, and number field in Maya UI.
        """
        def reset_to_default(self):
            """
            Reset the slider and number field to their default values.
            """
            cmds.floatSlider(self.slider_control, edit=True, value=self.default_value)
            cmds.floatField(self.number_control, edit=True, value=self.default_value)

        def __init__(self, layout, label, min_val, max_val, default_value, step, height=40):
            self.label = label
            self.min_val = min_val
            self.max_val = max_val
            self.default_value = default_value
            self.step = step

            # Create the label, slider, and number field controls
            column_layout = cmds.rowColumnLayout(numberOfColumns=5, h=height, columnWidth=[(1, 100), (2, 150), (3, 60)], p=layout)
            self.label_control = cmds.text(label=label, p=column_layout)
            self.slider_control = cmds.floatSlider(min=self.min_val, max=self.max_val, value=self.default_value,
                                                   step=self.step, width=150, p=column_layout)  # Set width for the slider
            self.number_control = cmds.floatField(value=self.default_value, width=60, p=column_layout)  # Set width for the field
            self.reset_separator = cmds.separator(p=column_layout, style='none', w=10)
            self.reset_btn = cmds.button(label="X", p=column_layout, w=30, c=lambda _: self.reset_to_default())

            # Connect the slider and number input, so they update each other
            cmds.floatSlider(self.slider_control, edit=True, dragCommand=self.update_number_field)
            cmds.floatField(self.number_control, edit=True, changeCommand=self.update_slider)

        def update_number_field(self, value):
            """
            Update the number field when the slider is adjusted.
            """
            cmds.floatField(self.number_control, edit=True, value=value)

        def update_slider(self, value):
            """
            Update the slider when the number field is adjusted.
            """
            cmds.floatSlider(self.slider_control, edit=True, value=value)

        def get_value(self):
            """
            Retrieve the current value of the slider.
            """
            return cmds.floatField(self.number_control, query=True, value=True)

    class ObjectReference:
        """
        A reusable class to create a label, text field, and button in Maya UI for referencing objects.
        """
        def __init__(self, layout, label, button_callback, base_type, child_type=None):
            self.label = label
            self.base_type = base_type
            self.child_type = child_type
            self.object = None
            self.button_callback = button_callback

            # Create the label, text field, and button controls
            column_layout = cmds.rowColumnLayout(numberOfColumns=3, columnWidth=[(1, 100), (2, 240), (3, 50)], p=layout)
            self.label_control = cmds.text(label=label, p=column_layout)
            self.text_field = cmds.textField(editable=False, p=column_layout)
            self.assign_btn = cmds.button(label="<<", p=column_layout, c=lambda _: self.assign_object())

        def assign_object(self, optional_object=None):
            selection = [cmds.ls(selection=True, type=self.base_type, long=True)] if not optional_object else [optional_object]
            if selection:
                if self.child_type:
                    shape_nodes = cmds.listRelatives(selection[0], shapes=True, fullPath=True)
                    if shape_nodes and cmds.nodeType(shape_nodes[0]) == self.child_type:
                        self.object = selection[0]
                    else:
                        cmds.warning(f"Selected object does not have a child of type {self.child_type}.")
                        return
                else:
                    self.object = selection[0]

                short_name = cmds.ls(self.object, shortNames=True)[0]
                cmds.textField(self.text_field, edit=True, text=short_name)
            else:
                cmds.warning(f"No {self.base_type} object selected.")
            if self.button_callback:
                self.button_callback(self.object)

        def clear_object(self):
            self.object = None
            cmds.textField(self.text_field, edit=True, text="")