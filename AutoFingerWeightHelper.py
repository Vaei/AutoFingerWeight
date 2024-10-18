import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import math
from enum import Enum

class Math:
    @staticmethod
    def calculate_distance(pos1, pos2):
        """Calculate the Euclidean distance between two points"""
        return math.sqrt(sum([(pos2[i] - pos1[i]) ** 2 for i in range(3)]))

    @staticmethod
    def calculate_aim_direction(pos1, pos2):
        """Calculate the normalized aim direction from pos1 to pos2"""
        direction = [(pos2[i] - pos1[i]) for i in range(3)]
        magnitude = Math.calculate_distance(pos1, pos2)
        return [d / magnitude for d in direction] if magnitude != 0 else [1, 0, 0]  # Default to X-axis if no movement


class Helper:
    @staticmethod
    def get_joint_positions(joint_chain):
        """Retrieve world-space positions of the joints"""
        return [cmds.xform(joint, q=True, ws=True, t=True) for joint in joint_chain]

    @staticmethod
    def get_edge_midpoint(edge):
        # Convert edge selection to vertices
        vertices = cmds.polyListComponentConversion(edge, fromEdge=True, toVertex=True)
        vertices = cmds.ls(vertices, fl=True)  # Flatten the list

        # Get world positions of the vertices
        pos1 = cmds.pointPosition(vertices[0], w=True)
        pos2 = cmds.pointPosition(vertices[1], w=True)

        # Calculate midpoint
        midpoint = [(pos1[i] + pos2[i]) / 2 for i in range(3)]

        return midpoint

    @staticmethod
    def create_cylinder_between_joints(pos1, pos2, radius, length):
        """Creates a cylinder between two joint positions"""
        height = Math.calculate_distance(pos1, pos2)

        # Create the cylinder and scale it based on the distance
        cylinder = cmds.polyCylinder(r=radius, h=height, sx=8, sy=1, sz=0, ch=False)[0]

        # Delete end caps
        cmds.delete(cylinder + ".f[9]")  # Top end cap
        cmds.delete(cylinder + ".f[8]")  # Bottom end cap

        # Move the cylinder to the midpoint between the two joints
        mid_pos = [(pos1[i] + pos2[i]) / 2 for i in range(3)]
        cmds.move(mid_pos[0], mid_pos[1], mid_pos[2], cylinder)

        # Align the cylinder towards the second joint using aimConstraint
        locator = cmds.spaceLocator()[0]
        cmds.move(pos2[0], pos2[1], pos2[2], locator)
        cmds.aimConstraint(locator, cylinder, aimVector=(0, 1, 0), upVector=(0, 0, 1), worldUpType="scene")
        cmds.delete(locator)  # Delete the locator after applying the constraint

        # Reduce the scale for aesthetic purposes
        scale_factor = 1.0 - length
        cmds.scale(scale_factor, scale_factor, scale_factor, cylinder)

        return cylinder

    @staticmethod
    def detect_open_edges(mesh):
        """Selects the open edges (holes) in the mesh"""
        # Convert the mesh to OpenMaya for processing
        selection_list = om.MSelectionList()
        selection_list.add(mesh)
        dag_path = selection_list.getDagPath(0)
        mfn_mesh = om.MFnMesh(dag_path)

        # Get the edges of the mesh
        edge_iter = om.MItMeshEdge(dag_path)

        open_edges = []

        while not edge_iter.isDone():
            if edge_iter.onBoundary():  # If the edge is not connected to a face
                open_edges.append(edge_iter.index())
            edge_iter.next()

        # Select the open edges
        open_edges_str = ["{}.e[{}]".format(mesh, edge) for edge in open_edges]
        return open_edges_str

    @staticmethod
    def recalculate_edge_to_joint_mapping(mesh, joint_chain, joint_positions):
        """
        Rebuilds the edge-to-joint map based on the world positions of the edges.
        Typically used after uniting the mesh.
        """
        joint_edge_map = {}  # New map to hold edge-to-joint mapping after uniting
        open_edges = Helper.detect_open_edges(mesh)  # Get open edges of the combined mesh

        for edge in open_edges:
            edge_midpoint = Helper.get_edge_midpoint(edge)  # Get world midpoint of edge

            # Find the nearest joint by comparing distances to each joint
            min_distance = float('inf')
            closest_joint_index = None
            for i, joint_pos in enumerate(joint_positions):
                dist = Math.calculate_distance(edge_midpoint, joint_pos)
                if dist < min_distance:
                    min_distance = dist
                    closest_joint_index = i

            # Add this edge to the map of the nearest joint
            if closest_joint_index not in joint_edge_map:
                joint_edge_map[closest_joint_index] = {
                    'joint': joint_chain[closest_joint_index],
                    'open_edges': []
                }
            joint_edge_map[closest_joint_index]['open_edges'].append(edge)

        return joint_edge_map

    @staticmethod
    def separate_joint_chains(selected_joints):
        """
        Separates the selected joints into individual finger chains.
        Assumes the joints are ordered from proximal to distal.
        """
        finger_chains = []
        current_chain = [selected_joints[0]]

        for i in range(1, len(selected_joints)):
            # Check if the current joint is part of the same finger chain
            if Helper.is_same_finger_chain(selected_joints[i - 1], selected_joints[i]):
                current_chain.append(selected_joints[i])
            else:
                finger_chains.append(current_chain)
                current_chain = [selected_joints[i]]

        finger_chains.append(current_chain)
        return finger_chains

    @staticmethod
    def is_same_finger_chain(joint_first, joint_second):
        """
        Checks if two joints are part of the same finger chain.
        Assumes the joints are ordered from proximal to distal.
        """
        # Get the parent of the second joint
        parent_joint = cmds.listRelatives(joint_second, parent=True, fullPath=True)
        if not parent_joint:
            return False

        # Check if the parent of the second joint is the first joint
        return parent_joint[0] == joint_first

    @staticmethod
    def find_closest_finger_mesh(chain, finger_meshes):
        """
        Finds the closest finger mesh to the given finger chain.
        Returns the name of the closest finger mesh.
        """
        chain_positions = Helper.get_joint_positions(chain)
        min_distance = float('inf')
        closest_mesh = None

        for mesh in finger_meshes:
            # Average all the vertices of the mesh to get a representative position
            average_pos = Helper.get_average_mesh_position(mesh)

            # Determine the distance to the chain
            distance = sum([Math.calculate_distance(average_pos, joint_pos) for joint_pos in chain_positions])
            if distance < min_distance:
                min_distance = distance
                closest_mesh = mesh

        return closest_mesh

    @staticmethod
    def get_average_mesh_position(mesh):
        """
        Calculate the average position of all vertices in the given mesh.
        """
        selection_list = om.MSelectionList()
        selection_list.add(mesh)
        dag_path = selection_list.getDagPath(0)
        mfn_mesh = om.MFnMesh(dag_path)

        points = mfn_mesh.getPoints()
        num_points = len(points)
        average_pos = [0, 0, 0]

        for i in range(num_points):
            average_pos[0] += points[i].x
            average_pos[1] += points[i].y
            average_pos[2] += points[i].z

        average_pos = [pos / num_points for pos in average_pos]
        return average_pos

    @staticmethod
    def get_ring_vertices_for_joint(mesh, joint_chain, get_end_rings=False):
        """
        Retrieves the vertices associated with the given joint chain.
        """
        index = 0 if not get_end_rings else -1
        # Start by selecting the open edges of the mesh
        open_edges = Helper.detect_open_edges(mesh)

        # Select the edge closest to the first joint in the chain
        joint_positions = Helper.get_joint_positions(joint_chain)
        first_joint_pos = joint_positions[index]

        # Separate the edges into connected groups
        edge_groups = Helper.separate_edge_groups(open_edges)

        closest_edge = None
        min_distance = float('inf')
        for edge in edge_groups:
            edge_midpoint = Helper.get_edge_midpoint(edge[index])
            distance = Math.calculate_distance(first_joint_pos, edge_midpoint)
            if distance < min_distance:
                min_distance = distance
                closest_edge = edge

        # Convert the edge to vertices
        vertices = cmds.polyListComponentConversion(closest_edge, fromEdge=True, toVertex=True)
        return cmds.ls(vertices, flatten=True)

    @staticmethod
    def separate_edge_groups(edges):
        """
        Separates the edges into connected groups.
        """
        edge_groups = []  # Store the edge groups
        visited_edges = set()  # Track visited edges

        # Iterate over all edges
        for edge in edges:
            if edge not in visited_edges:
                # New group of connected edges
                current_group = []
                edge_stack = [edge]

                while edge_stack:
                    current_edge = edge_stack.pop()
                    if current_edge not in visited_edges:
                        visited_edges.add(current_edge)
                        current_group.append(current_edge)

                        # Find connected edges and add them to the stack for processing
                        connected_edges = Helper.get_connected_edges(current_edge, edges)
                        edge_stack.extend([e for e in connected_edges if e not in visited_edges])

                edge_groups.append(current_group)

        return edge_groups

    @staticmethod
    def get_connected_edges(edge, all_edges):
        """
        Retrieves all edges connected to the given edge.
        """
        # Convert the edge to vertices
        vertices = cmds.polyListComponentConversion(edge, fromEdge=True, toVertex=True)
        vertices = cmds.ls(vertices, flatten=True)

        connected_edges = []

        # Find all edges connected to the vertices of the given edge
        for vert in vertices:
            # Convert the vertex back to edges
            edges = cmds.polyListComponentConversion(vert, fromVertex=True, toEdge=True)
            edges = cmds.ls(edges, flatten=True)

            # Only include edges that are in the provided all_edges list (open edges)
            connected_edges.extend([e for e in edges if e in all_edges])

        return connected_edges

    @staticmethod
    def grow_selection():
        """
        Grows the vertex selection to the next ring.
        mel.eval('GrowPolygonSelectionRegion;') , but this silences the output log
        """
        mel.eval('PolySelectTraverse 1')

    @staticmethod
    def get_next_ring_vertices(vertices, consumed_vertices):
        """
        Traverses the edge ring starting from the current edge.
        """
        cmds.select(vertices)
        Helper.grow_selection()
        next_edge_ring = cmds.ls(selection=True, flatten=True)
        next_edge_ring = list(set(next_edge_ring) - set(consumed_vertices))
        return next_edge_ring

    @staticmethod
    def select_corresponding_vertices_between_meshes(source_vertices, target_mesh):
        """
        Selects the corresponding vertices between two meshes based on their positions.
        """
        # Get the positions of the source vertices
        source_positions = [cmds.pointPosition(vert, world=True) for vert in source_vertices]

        # Get the positions of all vertices in the source mesh
        target_vertices = cmds.ls(target_mesh + '.vtx[*]', flatten=True)
        target_positions = [cmds.pointPosition(vert, world=True) for vert in target_vertices]

        # Find the closest vertex in the target mesh for each source vertex
        corresponding_vertices = []
        for source_pos in source_positions:
            min_distance = float('inf')
            closest_vertex = None
            for i, target_pos in enumerate(target_positions):
                distance = Math.calculate_distance(source_pos, target_pos)
                if distance < min_distance:
                    min_distance = distance
                    closest_vertex = target_vertices[i]
            corresponding_vertices.append(closest_vertex)

        # Select the corresponding vertices in the target mesh
        cmds.select(corresponding_vertices)
        return corresponding_vertices

    @staticmethod
    def does_finger_ring_have_full_weight(index, rings_per_knuckle=3):
        """
        Generate a repeating pattern where every `interval`-th item is True.
        The first ring on the knuckle is 0.5 on two joints, the second is 1.0 on one joint, the third is 0.5 on two joints, and so on.
        Therefore, this returns False, True, False, False, True, False, False, True, ...
        """
        return index % rings_per_knuckle == 1

    @staticmethod
    def should_assign_weight_ahead(index, rings_per_knuckle=3):
        """
        Generate a repeating pattern for whether to assign weight to the joint ahead.
        The pattern is False, False, True, False, False, True, ...
        """
        return index % rings_per_knuckle == 2

    class KnucklePosition(Enum):
        PRE_KNUCKLE = 0
        KNUCKLE_START = 1
        KNUCKLE_MID = 2
        KNUCKLE_END = 3
        POST_KNUCKLE = 4

    @staticmethod
    def get_knuckle_position(index):
        if index % 5 == 0:
            return Helper.KnucklePosition.PRE_KNUCKLE
        elif index % 5 == 1:
            return Helper.KnucklePosition.KNUCKLE_START
        elif index % 5 == 2:
            return Helper.KnucklePosition.KNUCKLE_MID
        elif index % 5 == 3:
            return Helper.KnucklePosition.KNUCKLE_END
        else:
            return Helper.KnucklePosition.POST_KNUCKLE

    @staticmethod
    def expand_knuckle_pos_as_bools(knuckle_pos):
        """
        Expand the knuckle position enum into booleans.
        """
        pre_knuckle = knuckle_pos == Helper.KnucklePosition.PRE_KNUCKLE
        knuckle_start = knuckle_pos == Helper.KnucklePosition.KNUCKLE_START
        knuckle_mid = knuckle_pos == Helper.KnucklePosition.KNUCKLE_MID
        knuckle_end = knuckle_pos == Helper.KnucklePosition.KNUCKLE_END
        post_knuckle = knuckle_pos == Helper.KnucklePosition.POST_KNUCKLE
        return pre_knuckle, knuckle_start, knuckle_mid, knuckle_end, post_knuckle

    @staticmethod
    def zero_all_weights(mesh, skin, joint_chains, base_joint):
        """
        Zero out all the weights on the selected vertices.
        """
        # Get all vertices of the mesh
        vertices = cmds.ls(mesh + '.vtx[*]', flatten=True)

        # Create a list of all joints (base_joint + all joints in the chains)
        all_joints = [base_joint]
        for chain in joint_chains:
            all_joints.extend(chain)

        # Set the weights for all vertices to 0 for each joint
        for joint in all_joints:
            cmds.skinPercent(skin[0], vertices, transformValue=[(joint, 0.0)])

    @staticmethod
    def accumulate_weights(vertex_weight_map, joint, vertices, weight):
        """Accumulate weights for each vertex influenced by the given joint."""
        for vertex in vertices:
            if vertex not in vertex_weight_map:
                vertex_weight_map[vertex] = {}
            if joint not in vertex_weight_map[vertex]:
                vertex_weight_map[vertex][joint] = 0.0
            vertex_weight_map[vertex][joint] += weight

    @staticmethod
    def apply_weights(mesh, base_joint, joint_chains, vertex_weight_map):
        """Apply the accumulated weights to the skin cluster."""
        # Weight the original mesh
        cmds.select(mesh)
        cmds.select(base_joint, add=1)

        cmds.progressWindow(title='Auto Finger Weight', progress=0, status='Setting up Skin Clusters...', isInterruptable=True)

        for chain in joint_chains:
            cmds.select(chain, add=1)
        skin = cmds.skinCluster(toSelectedBones=True, bindMethod=0, normalizeWeights=1, weightDistribution=0,
                                maximumInfluences=3, obeyMaxInfluences=True, dropoffRate=10,
                                removeUnusedInfluence=False)

        # Shift all weights to 1.0 on the base joint; we don't want to be removing weight from arbitrary joints once they're assigned
        cmds.skinPercent(skin[0], mesh, transformValue=[(base_joint, 1.0)])

        # Cache all influences before locking them, we don't want to change the user's settings
        cached_influences = {}
        influences = cmds.skinCluster(skin[0], query=True, influence=True)
        for influence in influences:
            cached_influences[influence] = cmds.getAttr(f"{influence}.liw")

        cmds.progressWindow(endProgress=True)

        try:
            # Lock all influences except the base joint
            for influence in influences:
                if influence != base_joint:
                    cmds.setAttr(f"{influence}.liw", 1)  # Lock influence weights
                else:
                    cmds.setAttr(f"{influence}.liw", 0)  # Unlock the base joint

            # Initialize the progress window
            total_vertices = len(vertex_weight_map)
            cmds.progressWindow(title='Auto Finger Weight', progress=0, status='Assigning Weights...', maxValue=total_vertices, isInterruptable=True)

            # Iterate through the vertices and assign weights
            for i, (vertex, joint_weights) in enumerate(vertex_weight_map.items()):
                if cmds.progressWindow(query=True, isCancelled=True):
                    cmds.warning("Operation canceled by user.")
                    cmds.progressWindow(endProgress=True)
                    return

                # Update the progress for each vertex processed
                cmds.progressWindow(edit=True, progress=i + 1, status=f'Processing weights for vertex {i + 1}/{total_vertices}')

                for joint, weight in joint_weights.items():
                    # Get corresponding vertices between the two meshes
                    vertex = Helper.select_corresponding_vertices_between_meshes([vertex], mesh)

                    # Assign the skin weight to the vertex
                    cmds.skinPercent(skin[0], vertex, transformValue=[(joint, weight)])

            cmds.progressWindow(endProgress=True)

        finally:
            # Restore the lock state of the influences
            for influence in influences:
                if influence != base_joint:
                    cmds.setAttr(f"{influence}.liw", cached_influences[influence])