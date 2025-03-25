# A small script to use after kuro_gltf_to_meshes.py, as the skeleton.json that comes out of
# Blender may not be fully accurate to the original Falcom skeleton.  This script will first ask
# for the new skeleton.json from kuro_gltf_to_meshes.py, then the original skeleton.json from
# kuro_mdl_export_meshes.py.  It will copy all the values from the original to the new, while
# preserving any additional bones added in Blender.
#
# GitHub eArmada8/kuro_mdl_tool

import json, os, sys

def replace_skeleton_parameters_with_originals (new_skeleton_file, original_skeleton_file):
    to_replace = ["type", "mesh_index", "pos_xyz", "unknown_quat",
        "skin_mesh", "rotation_euler_rpy", "scale", "unknown"]
    new_skel = json.loads(open(new_skeleton_file, 'rb').read())
    org_skel = json.loads(open(original_skeleton_file, 'rb').read())
    org_index = {org_skel[i]['name']:i for i in range(len(org_skel))}
    for i in range(len(new_skel)):
        if new_skel[i]['name'] in org_index:
            for key in to_replace:
                new_skel[i][key] = org_skel[org_index[new_skel[i]['name']]][key]
    return(new_skel)

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
        parser.add_argument('new_skeleton_file', help="Name of skeleton.json file to replace values in (required).")
        parser.add_argument('original_skeleton_file', help="Name of skeleton.json file with values to export from (required).")
        args = parser.parse_args()
        if os.path.exists(args.new_skeleton_file) and args.new_skeleton_file[-5:].lower() == '.json'\
            and os.path.exists(args.original_skeleton_file) and args.original_skeleton_file[-5:].lower() == '.json':
            new_skel = replace_skeleton_parameters_with_originals(new_skeleton_file, original_skeleton_file)
            open(new_skeleton_file, 'wb').write(json.dumps(new_skel, indent = 4).encode('utf-8'))
    else:
        new_skeleton_file = ''
        while not (os.path.exists(new_skeleton_file) and new_skeleton_file[-5:].lower() == '.json'):
            print("Please type the name of the new skeleton file from kuro_gltf_to_meshes.py.")
            new_skeleton_file = input('[or drag the file into the window] ').lstrip("\"").rstrip("\"")
        original_skeleton_file = ''
        while not (os.path.exists(original_skeleton_file) and original_skeleton_file[-5:].lower() == '.json'):
            print("Please type the name of the original skeleton file from kuro_mdl_export_meshes.py.")
            original_skeleton_file = input('[or drag the file into the window] ').lstrip("\"").rstrip("\"")
        new_skel = replace_skeleton_parameters_with_originals(new_skeleton_file, original_skeleton_file)
        open(new_skeleton_file, 'wb').write(json.dumps(new_skel, indent = 4).encode('utf-8'))