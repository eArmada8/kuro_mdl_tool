# Tool to convert glTF animations to Kuro no Kiseki MDL format.
# Usage:  Run by itself without commandline arguments and it will read every .mdl file,
# and if it finds an animation section AND a .gltf/.glb file with a matching filename,
# then it will extract the skeleton and animation from the .gltf/.glb file and insert those
# into the .mdl file.  Other sections (materials, meshes, primitives) will be left untouched.
#
# For command line options, run:
# /path/to/python3 kuro_mdl_import_animation.py --help
#
# Requires both kuro_gltf_to_meshes.py, kuro_mdl_import_meshes.py, and all dependencies.
#
# GitHub eArmada8/kuro_mdl_tool

try:
    from kuro_gltf_to_meshes import *
    from kuro_mdl_import_meshes import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

#Does not support sparse
def read_gltf_stream (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    bufferview = gltf.bufferViews[accessor.bufferView]
    buffer = gltf.buffers[bufferview.buffer]
    componentType = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
    componentSize = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    componentFormat = "<{0}{1}".format(componentCount[accessor.type],\
        componentType[accessor.componentType])
    componentStride = componentCount[accessor.type] * componentSize[accessor.componentType]
    data = []
    with io.BytesIO(gltf.get_data_from_buffer_uri(buffer.uri)) as f:
        f.seek(bufferview.byteOffset + accessor.byteOffset, 0)
        for i in range(accessor.count):
            data.append(list(struct.unpack(componentFormat, f.read(componentStride))))
            if (bufferview.byteStride is not None) and (bufferview.byteStride > componentStride):
                f.seek(bufferview.byteStride - componentStride, 1)
    if accessor.normalized == True:
        for i in range(len(data)):
            if componentType == 'b':
                data[i] = [x / ((2**(8-1))-1) for x in data[i]]
            elif componentType == 'B':
                data[i] = [x / ((2**8)-1) for x in data[i]]
            elif componentType == 'h':
                data[i] = [x / ((2**(16-1))-1) for x in data[i]]
            elif componentType == 'H':
                data[i] = [x / ((2**16)-1) for x in data[i]]
    return(data)

# We can maintain ability to extract multiple indices, although Kuro no Kiseki only has single animations so i=0 always to my knowledge
def extract_animation (gltf, i = 0):
    ani_struct = []
    for j in range(len(gltf.animations[i].channels)):
        sampler = gltf.animations[i].channels[j].sampler
        inputs = read_gltf_stream(gltf, gltf.animations[i].samplers[sampler].input)
        outputs = read_gltf_stream(gltf, gltf.animations[i].samplers[sampler].output)
        target_node = gltf.nodes[gltf.animations[i].channels[j].target.node]
        if gltf.animations[i].channels[j].target.path == 'rotation':
            # Get base rotations from the skeleton pose (needed to calculate the differential rotations the Kuro uses)
            if target_node.matrix is not None:
                base_s = [numpy.linalg.norm(target_node.matrix[0:3]), numpy.linalg.norm(target_node.matrix[4:7]),\
                    numpy.linalg.norm(target_node.matrix[8:11])]
                base_r_mtx = numpy.array([(target_node.matrix[0:3]/base_s[0]).tolist()+[0],\
                    (target_node.matrix[4:7]/base_s[1]).tolist()+[0],\
                    (target_node.matrix[8:11]/base_s[2]).tolist()+[0],[0,0,0,1]]).transpose()
                # I need a more robust mechanism to calculate quaternions from matrices, but since Kuro does not use matrices, this will do for now
                base_r = Quaternion(matrix = base_r_mtx)
            else:
                if target_node.rotation is not None:
                    base_r = Quaternion([target_node.rotation[3]]+target_node.rotation[0:3])
                else:
                    base_r = Quaternion()
            raw_outputs = [Quaternion([x[3]]+x[0:3]) for x in outputs]
            diff_outputs = [list(base_r.inverse * x) for x in raw_outputs] #wxyz
            outputs = [x[1:4]+[x[0]] for x in diff_outputs] #xyzw
        ani_block = {'name': target_node.name + '_' + \
            {'translation':'translate', 'rotation':'rotate', 'scale':'scale'}[gltf.animations[i].channels[j].target.path],\
            'bone': target_node.name, 'type': {'translation':9, 'rotation':10, 'scale':11}[gltf.animations[i].channels[j].target.path],\
            'num_keyframes': len(inputs), 'inputs': inputs, 'outputs': outputs, 'unknown': [[0.0,0.0,0.0,0.0,0.0] for i in range(len(inputs))]}
        # The most recent sampler is used for interpolation.  We can only use one anyway, since all the transformations are combined.
        ani_struct.append(ani_block)
    return(ani_struct)

def build_animation_section (ani_struct):
    output_buffer = struct.pack("<I", len(ani_struct))
    for i in range(len(ani_struct)):
        output_buffer += make_pascal_string(ani_struct[i]['name'])
        output_buffer += make_pascal_string(ani_struct[i]['bone'])
        output_buffer += struct.pack("<4I", ani_struct[i]['type'], 0, 0, ani_struct[i]['num_keyframes'])
        output_buffer += numpy.array([ani_struct[i]['inputs'][j]+ani_struct[i]['outputs'][j]+[0.0,0.0,0.0,0.0,0.0] for j \
            in range(ani_struct[i]['num_keyframes'])],dtype='float32').flatten().tobytes()
    timestamps = set([x for y in [x for y in ani_struct for x in y['inputs']] for x in y])
    output_buffer += struct.pack("<2f", min(timestamps), max(timestamps))
    return(struct.pack("<2I", 3, len(output_buffer)) + output_buffer)

def insert_animation_data (mdl_data, skeleton_section_data, animation_section_data):
    with io.BytesIO(mdl_data) as f:
        new_mdl_data = f.read(4) #Header
        orig_kuro_ver, = struct.unpack("<I", f.read(4))
        if orig_kuro_ver == 2:
            if sorted(mdl_contents(mdl_data)) == [2,3]:
                orig_kuro_ver = 1 #Silently downgrade to MDL version 1, as CLE Kuro 2 does not support v2 animations
            else:
                print("Warning!  Kuro 2 MDL detected and auto-downgrade not possible.  This MDL will crash the game.")
                print("If using with CLE Kuro 2, please downgrade MDL prior to animation import.")
                input("Press Enter to continue.")
        new_mdl_data += struct.pack("<I", orig_kuro_ver)
        new_mdl_data += f.read(4) #Not sure what this is in the header
        while True:
            current_offset = f.tell()
            section = f.read(8)
            section_info = {}
            try:
                section_info["type"], section_info["size"] = struct.unpack("<II",section)
                section += f.read(section_info["size"])
            except:
                break
            if section_info["type"] == 2: # Skeleton section to replace
                section = skeleton_section_data
            if section_info["type"] == 3: # Animation section to replace
                section = animation_section_data
            new_mdl_data += section
        # Catch the null bytes at the end of the stream
        f.seek(current_offset,0)
        new_mdl_data += f.read()
        return(new_mdl_data)

def get_gltf_name (animation):
    if os.path.exists(animation+'.glb'):
        filename = animation+'.glb'
    elif os.path.exists(animation+'.gltf'):
        filename = animation+'.gltf'
    else:
        print("Animation {} not found, skipping...".format(animation))
        return False
    return(filename)

def process_mdl (mdl_file, change_compression = False, use_json_data = False):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    print("Processing {0}...".format(mdl_file))
    if mdl_data[0:4] in [b"F9BA", b"C9BA", b"D9BA"]:
        compressed = True
        mdl_data = decryptCLE(mdl_data)
    else:
        compressed = False
    if 3 not in mdl_contents(mdl_data):
        print("Skipping {0} as it does not contain an animation.".format(mdl_file))
        return False
    if use_json_data == True:
        try:
            skel_struct = read_struct_from_json(mdl_file[:-4]+"_skeleton.json")
            ani_struct = read_struct_from_json(mdl_file[:-4]+"_ani_struct.json")
        except:
            print("Skipping {0} as animation data missing or invalid.".format(mdl_file))
            return False
    else:
        gltf_name = get_gltf_name(mdl_file[:-4])
        if gltf_name == False:
            print("Skipping {0} as there is no animation gltf file.".format(mdl_file))
            return False
        gltf = GLTF2().load(gltf_name)
        try:
            animation_metadata = read_struct_from_json(mdl_file[:-4]+'.metadata')
        except:
            print("{0} missing or unreadable, reading data from {0}.mdl instead...".format(mdl_file[:-4]+'.metadata', mdl_file))
            with open(mdl_file, "rb") as f:
                mdl_data = f.read()
            mdl_data = decryptCLE(mdl_data)
            skel_struct = obtain_skeleton_data(mdl_data)
            animation_metadata = { 'locators': [x['name'] for x in skel_struct if x['type'] == 0],\
                'non_skin_meshes': [x['name'] for x in skel_struct if x['skin_mesh'] == 0] }
        skel_struct = build_skeleton_struct(gltf, animation_metadata)
        ani_struct = extract_animation(gltf)
    skeleton_data = build_skeleton_section(skel_struct)
    ani_data = build_animation_section(ani_struct)
    new_mdl_data = insert_animation_data(mdl_data, skeleton_data, ani_data)
    # Instead of overwriting backups, it will just tag a number onto the end
    backup_suffix = ''
    if os.path.exists(mdl_file + '.bak' + backup_suffix):
        backup_suffix = '1'
        if os.path.exists(mdl_file + '.bak' + backup_suffix):
            while os.path.exists(mdl_file + '.bak' + backup_suffix):
                backup_suffix = str(int(backup_suffix) + 1)
        shutil.copy2(mdl_file, mdl_file + '.bak' + backup_suffix)
    else:
        shutil.copy2(mdl_file, mdl_file + '.bak')
    if (compressed == True and change_compression == False) or (compressed == False and change_compression == True):
        new_mdl_data = compressCLE(new_mdl_data)
    with open(mdl_file,'wb') as f:
        f.write(new_mdl_data)

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to import into file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--change_compression', help="Change compression (compressed to uncompressed or vice versa)", action="store_true")
        parser.add_argument('-j', '--use_json_data', help="Read data from JSON instead of glTF", action="store_true")
        parser.add_argument('mdl_filename', help="Name of mdl file to import into (required).")
        args = parser.parse_args()
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, change_compression = args.change_compression, use_json_data = args.use_json_data)
    else:
        mdl_files = glob.glob('*.mdl')
        mdl_files = [x for x in mdl_files]
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
