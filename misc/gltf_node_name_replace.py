# Tool to change node names in a glTF file using a search and replace method.
# Usage:  Run by itself without commandline arguments and it will read every .glb/.gltf file
# and perform search and replace using replace_dict.json as a dictionary.
#
# replace_dict.json should look like: {'old1':'new1', 'old2':'new2'}
#
# Requires pygltflib, which can be installed by:
# /path/to/python3 -m pip install pygltflib
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import shutil, sys, os, glob
    from pygltflib import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def read_struct_from_json(filename, raise_on_fail = True):
    with open(filename, 'r') as f:
        try:
            return(json.loads(f.read()))
        except json.JSONDecodeError as e:
            print("Decoding error when trying to read JSON file {0}!\r\n".format(filename))
            print("{0} at line {1} column {2} (character {3})\r\n".format(e.msg, e.lineno, e.colno, e.pos))
            if raise_on_fail == True:
                input("Press Enter to abort.")
                raise
            else:
                return(False)

class bone_name_replace:
    def __init__(self, replace_dict_name = 'replace_dict.json'):
        self.replace_dict = read_struct_from_json(replace_dict_name)
    def replace_names(self, model_gltf):
        for old in self.replace_dict:
            bone_i = [i for i in range(len(model_gltf.nodes)) if model_gltf.nodes[i].name == old]
            if len(bone_i) > 0:
                model_gltf.nodes[bone_i[0]].name = self.replace_dict[old]
        return(model_gltf)

def process_gltf (gltf_filename):
    print("Processing {0}...".format(gltf_filename))
    try:
        model_gltf = GLTF2().load(gltf_filename)
    except:
        print("File {} not found, or is invalid, skipping...".format(gltf_filename))
        return False
    replacer = bone_name_replace('replace_dict.json')
    model_gltf = replacer.replace_names(model_gltf)
    # Instead of overwriting backups, it will just tag a number onto the end
    backup_suffix = ''
    if os.path.exists(gltf_filename + '.bak' + backup_suffix):
        backup_suffix = '1'
        if os.path.exists(gltf_filename + '.bak' + backup_suffix):
            while os.path.exists(gltf_filename + '.bak' + backup_suffix):
                backup_suffix = str(int(backup_suffix) + 1)
        shutil.copy2(gltf_filename, gltf_filename + '.bak' + backup_suffix)
    else:
        shutil.copy2(gltf_filename, gltf_filename + '.bak')
    model_gltf.save(gltf_filename)
    return True

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    gltf_files = glob.glob('*.glb')+glob.glob('*.gltf')
    for i in range(len(gltf_files)):
        process_gltf(gltf_files[i])