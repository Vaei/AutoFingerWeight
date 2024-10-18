import sys
import os
import inspect
import importlib
import maya.cmds as cmds
import math

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

        def __init__(self, chunk_name="UndoAutoFingerWeight", no_flush=False):
            self.chunk_name = chunk_name
            self.no_flush = no_flush

        def __enter__(self):
            # Open undo chunk
            if self.no_flush:
                cmds.undoInfo(stateWithoutFlush=False)
            cmds.undoInfo(openChunk=True, chunkName=self.chunk_name)

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Close the undo chunk when the context exits
            if self.no_flush:
                cmds.undoInfo(stateWithoutFlush=True)
            cmds.undoInfo(closeChunk=True)

            # If there's an exception, propagate it
            if exc_type:
                return False

    class GenerateWeightMesh:
        """Creates a mesh from the selected joint chains"""
        divisions = 3  # Number of divisions for bridging edges

        def __init__(self, radius, length):
            self.mesh = None

            with Core.UndoContext():  # Open undo chunk; the entire operation will automatically be undone in one step
                selected_joints = cmds.ls(selection=True, type="joint", long=True)
                if not selected_joints:
                    cmds.warning("Please select a joint chain.")
                    return

                cylinders = []

                # Generate a cylinder for each joint chain
                for joint in selected_joints:
                    cylinder = self.generate_cylinder_for_joint(joint, radius, length)
                    cylinders.append(cylinder)

                # Combine all cylinders into a single mesh
                if cylinders:
                    self.mesh = cmds.polyUnite(cylinders, ch=False)
                    self.mesh = cmds.ls(cmds.rename(self.mesh, "autoFingerWeightMesh"), long=True)
                    print("Mesh created:", self.mesh)

        @staticmethod
        def generate_cylinder_for_joint(start_joint, radius, length):
            """Processes a joint chain to create the continuous cylinder mesh, including dummy joints at the start and end."""

            # Retrieve all joints in the chain, with their relative positions
            joint_chain = cmds.listRelatives(start_joint, ad=True, type="joint", fullPath=True) or []
            joint_chain.reverse()  # Reverse the chain to get the correct order
            joint_chain.insert(0, start_joint)  # Add the starting joint back into the list

            mesh = None

            # Ensure there are enough joints in the chain to process
            if len(joint_chain) > 1:
                # Expand the chain by adding dummy joints at both ends
                expanded_joint_chain, dummy_first = Core.GenerateWeightMesh.expand_first_and_last_joints(joint_chain)

                # Create the mesh along the expanded joint chain
                mesh = Core.GenerateWeightMesh.create_mesh_along_joints(expanded_joint_chain, radius, length)

                # Delete the dummy joints using their references
                if dummy_first:
                    cmds.delete(dummy_first)
            else:
                cmds.warning("Selected joint chain has fewer than 2 joints.")

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
        def create_mesh_along_joints(joint_chain, radius, length):
            """Creates a continuous mesh along the joint chain by placing cylinders between each pair of joints"""
            positions = Helper.get_joint_positions(joint_chain)
            cylinders = []
            joint_edge_map = {}  # Dictionary to map joint indices to their associated open edges

            # Iterate through each joint pair and create a cylinder between them
            for i in range(len(positions) - 1):
                cylinder = Helper.create_cylinder_between_joints(positions[i], positions[i + 1], radius, length)
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
                    cmds.polyBridgeEdge(edges, ch=False, divisions=Core.GenerateWeightMesh.divisions, twist=0, taper=1, curveType=1, smoothingAngle=30)
                elif num != 8:  # This is a start/end tip with nothing to bridge
                    # But it's neither a joining edge nor a tip
                    cmds.warning("joint {i} has invalid number of edges: {num}")

            cmds.select(mesh)

            return mesh

    class AutoWeightMesh:
        """Automatically weights the mesh to the joint chain"""
        def __init__(self, mesh, base_joint):
            with Core.UndoContext():  # Open undo chunk; the entire operation will automatically be undone in one step
                selected_joints = cmds.ls(selection=True, type="joint", long=True)
                if not selected_joints:
                    cmds.warning("Please select joints.")
                    return
                if len(selected_joints) < 2:
                    cmds.warning("Please select at least two joints.")
                    return

                mesh = cmds.ls(mesh)[0]
                base_joint = cmds.ls(base_joint)[0]

                print(f"Mesh {mesh} base joint {base_joint}")

                # Separate the selected joints into individual finger joint chains
                joint_chains = Helper.separate_joint_chains(selected_joints)

                # Duplicate the weight mesh
                temp_mesh = cmds.duplicate(mesh, name=mesh[0]+"_temp", rr=True)[0]

                # Separate the mesh into individual finger meshes
                finger_meshes = cmds.polySeparate(temp_mesh, ch=False)

                # Assign finger meshes to their respective joint chains based on proximity
                joint_mesh_map = {}
                for i, chain in enumerate(joint_chains):
                    closest_finger_mesh = Helper.find_closest_finger_mesh(chain, finger_meshes)
                    if closest_finger_mesh:
                        joint_mesh_map[i] = closest_finger_mesh

                # Initialize an empty list for storing weights for each joint
                vertex_weight_map = {}

                # Set up the progress window
                cmds.progressWindow(title='Auto Finger Weight', progress=0, status='Auto-Weighting...', isInterruptable=True)

                # Iterate through each joint chain and assign weights to the vertices
                for i, chain in enumerate(joint_chains):
                    if cmds.progressWindow(query=True, isCancelled=True):
                        cmds.progressWindow(endProgress=True)
                        return

                    # Update progress for each chain
                    cmds.progressWindow(edit=True, step=1, status=f"Assigning weights for chain {i + 1}/{len(joint_chains)}")

                    # Get the assigned finger mesh
                    finger_mesh = joint_mesh_map.get(i)
                    if not finger_mesh:
                        cmds.warning(f"No finger mesh assigned for joint chain {i}")
                        continue

                    # Get the vertices for this finger mesh
                    vertices = Helper.get_ring_vertices_for_joint(finger_mesh, chain)
                    consumed_vertices = vertices

                    # Assign the first vertex ring to the base joint with full weight
                    Helper.accumulate_weights(vertex_weight_map, base_joint, vertices, 1.0)

                    # Assign the last vertex ring to the last joint with full weight
                    end_vertices = Helper.get_ring_vertices_for_joint(finger_mesh, chain, True)
                    Helper.accumulate_weights(vertex_weight_map, chain[-1], end_vertices, 1.0)

                    cmds.select(vertices)

                    # Traverse to the next vertex ring and assign weights to the relevant joint
                    max_attempts = 666
                    attempts = 0
                    vtx_ring_index = 0  # 0 is the first potential finger ring NOT the base_joint ring
                    while vertices:
                        if cmds.progressWindow(query=True, isCancelled=True):
                            cmds.progressWindow(endProgress=True)
                            return

                        # Update progress for each vertex ring
                        cmds.progressWindow(edit=True, step=1, status=f"Processing ring {vtx_ring_index + 1} of chain {i + 1}")

                        # Weight all the vertex rings in between the ends. 0 is the first vtx ring that is not the end ring!
                        vertices = Helper.get_next_ring_vertices(vertices, consumed_vertices)
                        if not vertices or all(v in end_vertices for v in vertices):  # If vertices are in the end ring, we have already assigned those
                            break
                        consumed_vertices += vertices
                        cmds.select(vertices)

                        # Determine knuckle position
                        knuckle_pos = Helper.get_knuckle_position(vtx_ring_index)
                        pre_knuckle, knuckle_start, knuckle_mid, knuckle_end, post_knuckle = Helper.expand_knuckle_pos_as_bools(knuckle_pos)

                        # There are 5 rings per knuckle, so we can determine the joint using the vtx ring index
                        joint_index = vtx_ring_index // 5
                        prev_joint = chain[joint_index - 1] if joint_index - 1 >= 0 else base_joint
                        is_last_joint = joint_index == len(chain) - 1

                        print(f"Ring {vtx_ring_index} knuckle position: {knuckle_pos} for joint {joint_index}")

                        # Determine which joints should receive weights
                        weight_joint = chain[joint_index]
                        weight_joint_partial = prev_joint
                        weight = 1.0
                        if pre_knuckle:
                            weight = 0.0
                        elif knuckle_start:
                            weight = 0.25
                        elif knuckle_mid:
                            weight = 0.5
                        elif knuckle_end:
                            weight = 0.75
                        elif post_knuckle:
                            weight = 1.0

                        # # If we are at the end of the chain, assign full weight to the last joint
                        # if is_last_joint and post_knuckle:
                        #     weight = 1.0
                        #     weight_joint_partial = None

                        # Accumulate weights for both the primary and secondary joints
                        Helper.accumulate_weights(vertex_weight_map, weight_joint, vertices, weight)
                        if weight_joint_partial:
                            Helper.accumulate_weights(vertex_weight_map, weight_joint_partial, vertices, 1.0 - weight)
                            print(
                                f"Ring {vtx_ring_index} assigned to {weight_joint} with weight {weight} and {weight_joint_partial} with weight {1.0 - weight}")
                        else:
                            print(f"Ring {vtx_ring_index} assigned to {weight_joint} with weight {weight}")

                        # Increment the vertex ring index
                        vtx_ring_index += 1

                        # Limit the number of attempts to avoid infinite loops
                        attempts += 1
                        if attempts >= max_attempts:
                            cmds.warning(f"Too many attempts to assign vertices to joints for joint chain {i}")
                            cmds.progressWindow(endProgress=True)
                            return

                # Close the progress window after all chains are processed
                cmds.progressWindow(endProgress=True)

                # Weight the original mesh
                Helper.apply_weights(mesh, base_joint, joint_chains, vertex_weight_map)

                # Delete the temporary mesh
                cmds.delete(temp_mesh)
                cmds.select(mesh)

                cmds.confirmDialog(title="Auto Finger Weight", message="Auto Finger Weighting Completed Successfully!", button=["OK"])