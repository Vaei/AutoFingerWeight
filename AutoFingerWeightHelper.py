import maya.cmds as cmds
import maya.api.OpenMaya as om
import math


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
    def create_cylinder_between_joints(pos1, pos2, radius):
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
        scale_factor = 0.85  # 15% reduction
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
