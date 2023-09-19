# Tool to extract the skeleton from glTF files.
# Usage:  Run by itself without commandline arguments and it will read every .glb/.gltf file
# and extract the skeleton.
#
# For command line options, run:
# /path/to/python3 kuro_gltf_to_skeleton.py --help
#
# Requires both pyquaternion and pygltflib.
# These can be installed by:
# /path/to/python3 -m pip install numpy pyquaternion pygltflib
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import numpy, math, json, os, sys, glob
    from pyquaternion import Quaternion
    from pygltflib import GLTF2
    from lib_fmtibvb import read_struct_from_json
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def build_skeleton_struct (model_gltf, metadata = {}):
    if 'locators' in metadata:
        locators = metadata['locators']
    else:
        locators = False
    if 'non_skin_meshes' in metadata:
        skin_joints = [i for i in range(len(model_gltf.nodes)) if model_gltf.nodes[i].name not in metadata['non_skin_meshes']]
    else:
        skin_joints = sorted(list(set([x for y in model_gltf.skins for x in y.joints])))
    mesh_nodes = [i for i in range(len(model_gltf.nodes)) if model_gltf.nodes[i].mesh is not None]
    skel_struct = []
    for i in range(len(model_gltf.nodes)):
        skel_node = { "id_referenceonly": i, "name": model_gltf.nodes[i].name }
        transform = {}
        if model_gltf.nodes[i].matrix is not None:
                transform["pos_xyz"] = model_gltf.nodes[j].matrix[12:15]
                transform["scale"] = [numpy.linalg.norm(model_gltf.nodes[j].matrix[0:3]),\
                    numpy.linalg.norm(model_gltf.nodes[j].matrix[4:7]),\
                    numpy.linalg.norm(model_gltf.nodes[j].matrix[8:11])]
                r = numpy.array([(gltf.nodes[j].matrix[0:3]/transform["scale"][0]).tolist()+[0],\
                    (gltf.nodes[j].matrix[4:7]/transform["scale"][1]).tolist()+[0],\
                    (gltf.nodes[j].matrix[8:11]/transform["scale"][2]).tolist()+[0],[0,0,0,1]])
                q = Quaternion(matrix=r)
                transform["rotation_euler_rpy"] = [math.atan2(2.0*(q[2]*q[3] + q[0]*q[1]), q[0]*q[0] - q[1]*q[1] - q[2]*q[2] + q[3]*q[3]),\
                    math.asin(-2.0*(q[1]*q[3] - q[0]*q[2])),\
                    math.atan2(2.0*(q[1]*q[2] + q[0]*q[3]), q[0]*q[0] + q[1]*q[1] - q[2]*q[2] - q[3]*q[3])]
        else:
            if model_gltf.nodes[i].translation is not None:
                transform["pos_xyz"] = model_gltf.nodes[i].translation
            else:
                transform["pos_xyz"] = [0.0,0.0,0.0]
            if model_gltf.nodes[i].rotation is not None:
                q = Quaternion(model_gltf.nodes[i].rotation[3], model_gltf.nodes[i].rotation[0],\
                    model_gltf.nodes[i].rotation[1], model_gltf.nodes[i].rotation[2])
                transform["rotation_euler_rpy"] = [math.atan2(2.0*(q[2]*q[3] + q[0]*q[1]), q[0]*q[0] - q[1]*q[1] - q[2]*q[2] + q[3]*q[3]),\
                    math.asin(-2.0*(q[1]*q[3] - q[0]*q[2])),\
                    math.atan2(2.0*(q[1]*q[2] + q[0]*q[3]), q[0]*q[0] + q[1]*q[1] - q[2]*q[2] - q[3]*q[3])]
            else:
                transform["rotation_euler_rpy"] = [0.0,0.0,0.0]
            if model_gltf.nodes[i].scale is not None:
                transform["scale"] = model_gltf.nodes[i].scale
            else:
                transform["scale"] = [1.0,1.0,1.0]
        if i in mesh_nodes:
            skel_node['type'] = 2
            skel_node['mesh_index'] = model_gltf.nodes[i].mesh
        else:
            if not locators == False:
                if model_gltf.nodes[i].name in locators:
                    skel_node['type'] = 0
                else:
                    skel_node['type'] = 1
            else:
                if transform["rotation_euler_rpy"] == [0.0,0.0,0.0] and transform["scale"] == [1.0,1.0,1.0]:
                    skel_node['type'] = 0
                else:
                    skel_node['type'] = 1
            skel_node['mesh_index'] = -1
        skel_node['pos_xyz'] = transform["pos_xyz"]
        skel_node['unknown_quat'] = [0.0,0.0,0.0,1.0]
        if i in skin_joints:
            skel_node['skin_mesh'] = 2
        else:
            skel_node['skin_mesh'] = 0
        skel_node['rotation_euler_rpy'] = transform["rotation_euler_rpy"]
        skel_node['scale'] = transform["scale"]
        skel_node['unknown'] = [0.0,0.0,0.0]
        skel_node['children'] = []
        if model_gltf.nodes[i].children is not None:
            skel_node['children'] = model_gltf.nodes[i].children
        skel_struct.append(skel_node)
    return(skel_struct)

def process_gltf (gltf_filename):
    print("Processing {0}...".format(gltf_filename))
    try:
        model_gltf = GLTF2().load(gltf_filename)
    except:
        print("File {} not found, or is invalid, skipping...".format(gltf_filename))
        return False
    try:
        metadata = read_struct_from_json(".".join(gltf_filename.split('.')[:-1])+".metadata")
    except:
        metadata = {}
    skel_struct = build_skeleton_struct (model_gltf, metadata)
    with open(".".join(gltf_filename.split('.')[:-1])+'_skeleton.json', "wb") as f:
        f.write(json.dumps(skel_struct, indent=4).encode("utf-8"))    
    return True

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('gltf_filename', help="Name of gltf file to export from (required).")
        args = parser.parse_args()
        if os.path.exists(args.gltf_filename) and len(args.gltf_filename[-4:].lower().split('.gl')) > 1:
            process_gltf(args.gltf_filename)
    else:
        gltf_files = glob.glob('*.gl*')
        for i in range(len(gltf_files)):
            process_gltf(gltf_files[i])

