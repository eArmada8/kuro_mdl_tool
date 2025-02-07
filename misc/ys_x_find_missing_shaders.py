# Ys X missing shader finder.  After running kuro_mdl_export_meshes.py, run this script
# and input the name of the game you want to target, and it will search the database
# (by default 'ys_x_shaders.csv', set below) to generate a report
# of any shaders that do not exist in the target game.  Requires Python 3.10 or newer.
#
# Requires kuro_find_similar_shaders.py, place in the same folder.
# Requires ys_x_shaders.csv, obtain from
# https://raw.githubusercontent.com/eArmada8/kuro_mdl_tool/master/misc/ys_x_shaders.csv
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import json, glob, os, sys
    from kuro_find_similar_shaders import Shader_db
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

csv_file = 'ys_x_shaders.csv'

def find_missing_shaders(shader_db, game_type, mat_file):
    if os.path.exists(csv_file):
        print("Processing {}...".format(mat_file))
        with open(mat_file, 'rb') as f:
            material_info = json.loads(f.read())
        shaders_used = ["{0}#{1}".format(x['shader_name'], x['shader_switches_hash_referenceonly']) for x in material_info]
        missing_shaders = [x for x in shaders_used if not x in shader_db.restricted_list]
        print("Shaders missing: {}".format(missing_shaders))
        return(missing_shaders)

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    shader_db = Shader_db(csv_file)
    game_type = input("Please enter game [{}]: ".format(', '.join(shader_db.shader_array[0][1:3])))
    while not game_type in shader_db.shader_array[0][1:3]:
        game_type = input("Invalid entry. Please enter game [{}]: ".format(', '.join(shader_db.shader_array[0][1:3])))
    shader_db.set_restricted_list(game_type)
    missing_shader_report = {}
    mat_files = glob.glob('**/material_info.json')
    for mat_file in mat_files:
        missing_shader_report[mat_file] = find_missing_shaders(shader_db, game_type, mat_file)
    input("Press Enter to continue.")
    with open("missing_shaders.json", 'wb') as f:
        f.write(json.dumps(missing_shader_report, indent=4).encode('utf-8'))
