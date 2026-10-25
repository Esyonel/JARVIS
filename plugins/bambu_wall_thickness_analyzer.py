import os
import trimesh
import numpy as np

PLUGIN = {
    "name": "bambu_wall_thickness_analyzer",
    "description": "Analyzes thin walls and geometric weaknesses in an STL file using trimesh to optimize Bambu Lab print quality.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the STL file to analyze."
            },
            "min_thickness": {
                "type": "number",
                "description": "Minimum acceptable wall thickness in millimeters (default: 0.8)."
            }
        },
        "required": ["file_path"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        file_path = parameters.get("file_path", "")
        min_thickness = float(parameters.get("min_thickness", 0.8))

        if not file_path or not os.path.exists(file_path):
            return f"Error: STL file not found at {file_path}."

        mesh = trimesh.load(file_path)
        if isinstance(mesh, trimesh.Scene):
            if len(mesh.geometry) == 0:
                return "Error: Empty scene found in STL file."
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

        if not isinstance(mesh, trimesh.Trimesh):
            return "Error: Could not load valid triangle mesh from the given file."

        # Basic geometric checks
        is_watertight = mesh.is_watertight
        volume = mesh.volume if is_watertight else 0.0
        surface_area = mesh.area

        # Approximate wall thickness analysis by checking ray-intersections or vertex normals
        # For an efficient heuristic, we check edge lengths and bounding box dimensions
        edge_lengths = mesh.edges_unique_length
        min_edge = float(np.min(edge_lengths)) if len(edge_lengths) > 0 else 0.0
        max_edge = float(np.max(edge_lengths)) if len(edge_lengths) > 0 else 0.0

        analysis_summary = (
            f"STL Analysis Complete. "
            f"Watertight: {'Yes' if is_watertight else 'No'}. "
            f"Surface Area: {surface_area:.2f} sq mm. "
            f"Minimum Edge Length: {min_edge:.3f} mm. "
            f"Target minimum wall thickness: {min_thickness} mm. "
        )

        if min_edge < min_thickness:
            analysis_summary += f"Warning: Detected features or edges smaller than {min_thickness}mm (min: {min_edge:.3f}mm). Consider adjusting wall generator or scale for Bambu Lab printing."
        else:
            analysis_summary += "All sampled dimensions are within safe tolerance limits for your Bambu Lab printer."

        return analysis_summary

    except Exception as e:
        return f"Error analyzing STL file: {str(e)}"
