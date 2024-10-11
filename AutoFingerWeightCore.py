import sys
import os
import inspect
import importlib
import maya.cmds as cmds

# Get the current script's directory using inspect
script_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
sys.path.append(script_dir)

import AutoFingerWeightHelper
importlib.reload(AutoFingerWeightHelper)

from AutoFingerWeightHelper import Helper
from AutoFingerWeightHelper import Math

class Core:
    class UndoContext:
        """A context manager to handle undo operations"""
        def __enter__(self):
            # Open undo chunk
            cmds.undoInfo(openChunk=True, chunkName="Undo Auto Finger Weight")

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Close the undo chunk when the context exits
            cmds.undoInfo(closeChunk=True)

            # If there's an exception, propagate it
            if exc_type:
                return False

    class GenerateWeightMesh:
        """Creates a mesh from the selected joint chains"""
        def __init__(self, radius):
            self.mesh = None

            with Core.UndoContext():  # Open undo chunk; the entire operation will automatically be undone in one step
                selected_joints = cmds.ls(selection=True, type="joint", long=True)
                if not selected_joints:
                    cmds.warning("Please select a joint chain.")
                    return

                cylinders = []

                for joint in selected_joints:
                    cylinder = self.generate_cylinder_for_joint(joint, radius)
                    cylinders.append(cylinder)

                if cylinders:
                    self.mesh = cmds.polyUnite(cylinders, ch=False)
                    self.mesh = cmds.ls(cmds.rename(self.mesh, "autoFingerWeightMesh"), long=True)
                    print("Mesh created:", self.mesh)

        @staticmethod
        def generate_cylinder_for_joint(start_joint, radius):
            """Processes a joint chain to create the continuous cylinder mesh, including dummy joints at the start and end."""

            # Retrieve all joints in the chain, with their relative positions
            joint_chain = cmds.listRelatives(start_joint, ad=True, type="joint", fullPath=True) or []
            joint_chain.reverse()  # Reverse the chain to get the correct order
            joint_chain.insert(0, start_joint)  # Add the starting joint back into the list

            mesh = None
            print(mesh)

            # Ensure there are enough joints in the chain to process
            if len(joint_chain) > 1:
                # Expand the chain by adding dummy joints at both ends
                expanded_joint_chain, dummy_first = Core.GenerateWeightMesh.expand_first_and_last_joints(joint_chain)

                # Create the mesh along the expanded joint chain
                mesh = Core.GenerateWeightMesh.create_mesh_along_joints(expanded_joint_chain, radius)
                # print("Mesh created:", mesh)

                # Delete the dummy joints using their references
                if dummy_first:
                    cmds.delete(dummy_first)
            else:
                cmds.warning("Selected joint chain has fewer than 2 joints.")

            print(mesh)

            return mesh

        @staticmethod
        def expand_first_and_last_joints(joint_chain):
            """Expands the first and last joints by adding dummy joints along the X aim axis"""

            if len(joint_chain) < 2:
                return joint_chain  # No need to expand if there's only one joint

            positions = Helper.get_joint_positions(joint_chain)

            # Ensure they envelop the entire mesh, esp. if extending further than the joint
            start_length_scalar = 0.75
            last_length_scalar = 1.25

            # Expand first joint
            cmds.select(clear=True)

            first_joint_pos = positions[0]
            second_joint_pos = positions[1]
            first_aim_dir = Math.calculate_aim_direction(first_joint_pos, second_joint_pos)
            first_length = Math.calculate_distance(first_joint_pos, second_joint_pos) * start_length_scalar
            expanded_first_pos = [first_joint_pos[i] - first_aim_dir[i] * first_length for i in range(3)]
            dummy_first = cmds.joint(p=expanded_first_pos, name="dummy_first")

            # Expand last joint
            cmds.select(dummy_first)

            last_joint_pos = positions[-1]
            second_last_joint_pos = positions[-2]
            last_aim_dir = Math.calculate_aim_direction(second_last_joint_pos, last_joint_pos)
            last_length = Math.calculate_distance(last_joint_pos, second_last_joint_pos) * last_length_scalar
            expanded_last_pos = [last_joint_pos[i] + last_aim_dir[i] * last_length for i in range(3)]
            dummy_last = cmds.joint(p=expanded_last_pos, name="dummy_last")

            # Return the new joint chain with the dummies added
            return [dummy_first] + joint_chain + [dummy_last], dummy_first

        @staticmethod
        def create_mesh_along_joints(joint_chain, joint_radius):
            """Creates a continuous mesh along the joint chain by placing cylinders between each pair of joints"""
            positions = Helper.get_joint_positions(joint_chain)
            cylinders = []
            joint_edge_map = {}  # Dictionary to map joint indices to their associated open edges

            # Iterate through each joint pair and create a cylinder between them
            for i in range(len(positions) - 1):
                cylinder = Helper.create_cylinder_between_joints(positions[i], positions[i + 1], joint_radius)
                cylinders.append(cylinder)

                # Detect the open edges for each cylinder and map to the joint index
                open_edges = Helper.detect_open_edges(cylinder)

                # Create mapping to the closest joint
                for edge in open_edges:
                    # Get the world position of the midpoint of the edge
                    edge_midpoint = Helper.get_edge_midpoint(edge)

                    # Calculate distances to both joints (i and i + 1)
                    dist_to_joint_i = Math.calculate_distance(edge_midpoint, positions[i])
                    dist_to_joint_i_plus_1 = Math.calculate_distance(edge_midpoint, positions[i + 1])

                    # Assign the edge to the closest joint
                    closest_joint_index = i if dist_to_joint_i < dist_to_joint_i_plus_1 else i + 1

                    if closest_joint_index not in joint_edge_map:
                        joint_edge_map[closest_joint_index] = {
                            'joint': joint_chain[closest_joint_index],
                            'open_edges': []
                        }

                    joint_edge_map[closest_joint_index]['open_edges'].append(edge)

                # cmds.select(joint_edge_map[i+1]['open_edges'])

            # Combine all cylinders into a single mesh
            mesh = cmds.polyUnite(cylinders, ch=False)[0]

            # After uniting, recalculate the joint-edge mapping using world positions
            joint_edge_map = Helper.recalculate_edge_to_joint_mapping(mesh, joint_chain, positions)

            cmds.select(joint_edge_map[1]['open_edges'])

            # Now let's use joint_edge_map to perform the bridging
            for i in range(len(joint_chain) - 1):
                edges = joint_edge_map[i]['open_edges']
                num = len(edges)
                if num == 16:
                    # Bridge the edges
                    cmds.polyBridgeEdge(edges, ch=False, divisions=1, twist=0, taper=1, curveType=1, smoothingAngle=30)
                elif num != 8:  # This is a start/end tip with nothing to bridge
                    # But it's neither a joining edge nor a tip
                    cmds.warning("joint {i} has invalid number of edges: {num}")

            cmds.select(mesh)

            return mesh