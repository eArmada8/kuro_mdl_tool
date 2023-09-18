# Tool to manipulate ED9 / Kuro no Kiseki models in mdl format.  Replace mesh section of
# Kuro no Kiseki mdl file with individual buffers previously exported.  Based on Uyjulian's script.
# Usage:  Run by itself without commandline arguments and it will read only the mesh section of
# every model it finds in the folder and replace them with fmt / ib / vb files in the same named
# directory.
#
# For command line options, run:
# /path/to/python3 kuro_mdl_import_meshes.py --help
#
# Requires both blowfish and zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install blowfish zstandard
#
# GitHub eArmada8/misc_kiseki

try:
    import io, struct, sys, os, shutil, glob, base64, json, blowfish, operator, zstandard
    from itertools import chain
    from lib_fmtibvb import *
    from kuro_mdl_export_meshes import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def compressCLE(file_content):
    magic = file_content[0:4]
    compressed_magic = b"D9BA"
    result = file_content
    if not magic == compressed_magic: # Don't compress files that are already compressed:
        compressor = zstandard.ZstdCompressor(level = 12, write_checksum = True)
        result = compressor.compress(file_content)
        while (len(result) % 8) > 0:
            result += b'\x00'
        result = compressed_magic + struct.pack("<I", len(result)) + result
    return result

def make_pascal_string(string):
    return struct.pack("<B", len(string)) + string.encode("utf8")

# Primitive data is in Kuro 2.  In Kuro 1, it will be an empty buffer.
# force_kuro_version should be either set to False, or to an integer.
def insert_model_data (mdl_data, skeleton_section_data, material_section_data, mesh_section_data, primitive_section_data, kuro_ver):
    with io.BytesIO(mdl_data) as f:
        new_mdl_data = f.read(4) #Header
        orig_kuro_ver, = struct.unpack("<I", f.read(4))
        kuro_ver = min(kuro_ver, orig_kuro_ver)
        new_mdl_data += struct.pack("<I", kuro_ver)
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
            if section_info["type"] == 0: # Material section to replace
                section = material_section_data
            if section_info["type"] == 1: # Mesh section to replace
                section = mesh_section_data
            if section_info["type"] == 2: # Skeleton section to replace
                section = skeleton_section_data
            if section_info["type"] == 4: # Primitive section to replace
                if kuro_ver > 1:
                    section = primitive_section_data
                else: # Needed if we are forcing downgrade to version 1
                    section = b''
            new_mdl_data += section
        # Catch the null bytes at the end of the stream
        f.seek(current_offset,0)
        new_mdl_data += f.read()
        return(new_mdl_data)

def build_skeleton_section (mdl_filename, kuro_ver = 1):
    # Will read data from JSON file, or load original data from the mdl file if JSON is missing
    try:
        skel_struct = read_struct_from_json(mdl_filename + "/skeleton.json")
    except:
        print("{0}/skeleton.json missing or unreadable, reading data from {0}.mdl instead...".format(mdl_filename))
        with open(mdl_filename + '.mdl', "rb") as f:
            mdl_data = f.read()
        mdl_data = decryptCLE(mdl_data)
        skel_struct = obtain_skeleton_data(mdl_data)
    output_buffer = struct.pack("<I", len(skel_struct))
    for i in range(len(skel_struct)):
        output_buffer += make_pascal_string(skel_struct[i]['name'])
        output_buffer += struct.pack("<Ii", skel_struct[i]['type'], skel_struct[i]['mesh_index'])
        output_buffer += struct.pack("<3f", *skel_struct[i]['pos_xyz'])
        output_buffer += struct.pack("<4f", *skel_struct[i]['unknown_quat'])
        output_buffer += struct.pack("<I", skel_struct[i]['skin_mesh'])
        output_buffer += struct.pack("<3f", *skel_struct[i]['rotation_euler_rpy'])
        output_buffer += struct.pack("<3f", *skel_struct[i]['scale'])
        output_buffer += struct.pack("<3f", *skel_struct[i]['unknown'])
        output_buffer += struct.pack("<I", len(skel_struct[i]['children']))
        output_buffer += struct.pack("<{}I".format(len(skel_struct[i]['children'])), *skel_struct[i]['children'])
    return(struct.pack("<2I", 2, len(output_buffer)) + output_buffer)

def build_material_section (mdl_filename, kuro_ver = 1):
    # Will read data from JSON file, or load original data from the mdl file if JSON is missing
    try:
        material_struct = read_struct_from_json(mdl_filename + "/material_info.json")
    except:
        print("{0}/material_info.json missing or unreadable, reading data from {0}.mdl instead...".format(mdl_filename))
        with open(mdl_filename + '.mdl', "rb") as f:
            mdl_data = f.read()
        mdl_data = decryptCLE(mdl_data)
        material_struct = obtain_material_data(mdl_data)
    output_buffer = struct.pack("<I", len(material_struct))
    for i in range(len(material_struct)):
        material_block = make_pascal_string(material_struct[i]['material_name']) \
            + make_pascal_string(material_struct[i]['shader_name']) \
            + make_pascal_string(material_struct[i]['str3'])
        texture_blocks = bytes()
        texture_block_count = 0
        for j in range(len(material_struct[i]['textures'])):
            texture_blocks += make_pascal_string(material_struct[i]['textures'][j]['texture_image_name']) \
                + struct.pack("<i", material_struct[i]['textures'][j]['texture_slot'])
            if kuro_ver > 1:
                texture_blocks += struct.pack("<i", material_struct[i]['textures'][j]['unk_00'])
            texture_blocks += struct.pack("<2i", material_struct[i]['textures'][j]['unk_01'], material_struct[i]['textures'][j]['unk_02'])
            if kuro_ver > 1:
                texture_blocks += struct.pack("<i", material_struct[i]['textures'][j]['unk_03'])
            texture_block_count += 1
        material_block += struct.pack("<I", texture_block_count) + texture_blocks
        shader_elements = bytes()
        shader_element_count = 0
        for j in range(len(material_struct[i]['shaders'])):
            if material_struct[i]['shaders'][j]['type_int'] in [0,1,4,5,6]: # These are decoded, so need to be encoded
                struct_dict = {0: "<I", 1: "<I", 4: "<f", 5: "<2f", 6: "<3f"}
                shader_elements += make_pascal_string(material_struct[i]['shaders'][j]['shader_name']) \
                    + struct.pack("<I", material_struct[i]['shaders'][j]['type_int'])
                if type(material_struct[i]['shaders'][j]['data']) == list:
                    shader_elements += struct.pack(struct_dict[material_struct[i]['shaders'][j]['type_int']], *material_struct[i]['shaders'][j]['data'])
                else:
                    shader_elements += struct.pack(struct_dict[material_struct[i]['shaders'][j]['type_int']], material_struct[i]['shaders'][j]['data'])
            else:
                shader_elements += make_pascal_string(material_struct[i]['shaders'][j]['shader_name']) \
                    + struct.pack("<I", material_struct[i]['shaders'][j]['type_int']) \
                    + base64.b64decode(material_struct[i]['shaders'][j]['data_base64'])
            shader_element_count += 1
        material_block += struct.pack("<I", shader_element_count) + shader_elements
        material_switches = bytes()
        material_switch_count = 0
        for j in range(len(material_struct[i]['material_switches'])):
            material_switches += make_pascal_string(material_struct[i]['material_switches'][j]['material_switch_name']) \
                + struct.pack("<i", material_struct[i]['material_switches'][j]['int2'])
            material_switch_count += 1
        material_block += struct.pack("<I", material_switch_count) + material_switches
        material_block += struct.pack("<I{0}B".format(len(material_struct[i]['uv_map_indices'])), len(material_struct[i]['uv_map_indices']), *material_struct[i]['uv_map_indices'])
        material_block += struct.pack("<I{0}B".format(len(material_struct[i]['unknown1'])), len(material_struct[i]['unknown1']), *material_struct[i]['unknown1'])
        material_block += struct.pack("<3IfI", *material_struct[i]['unknown2'])
        output_buffer += material_block
    return(struct.pack("<2I", 0, len(output_buffer)) + output_buffer)

def build_mesh_section (mdl_filename, kuro_ver = 1):
    # Ordinarily we do not need to parse the original file, but in case we do, we only want to do it once
    has_parsed_original_file = False
    try:
        mesh_struct_metadata = read_struct_from_json(mdl_filename + "/mesh_info.json")
    except:
        print("{0}/mesh_info.json missing or unreadable, reading data from {0}.mdl instead...".format(mdl_filename))
        with open(mdl_filename + '.mdl', "rb") as f:
            mdl_data = f.read()
        mdl_data = decryptCLE(mdl_data)
        mesh_struct = obtain_mesh_data(mdl_data)
        has_parsed_original_file = True
        mesh_struct_metadata = mesh_struct["mesh_blocks"]
    output_buffer = struct.pack("<I", len(mesh_struct_metadata))
    if kuro_ver > 1:
        prim_output_header = bytes()
        prim_output_data = bytes()
        prim_buffer_count = 0
    for i in range(len(mesh_struct_metadata)):
        mesh_block = bytes()
        meshes = 0 # Keep count of actual meshes imported, in case some have been deleted
        safe_filename = "".join([x if x not in "\/:*?<>|" else "_" for x in mesh_struct_metadata[i]["name"]])
        expected_vgmap = {mesh_struct_metadata[i]['nodes'][j]['name']:j for j in range(len(mesh_struct_metadata[i]['nodes']))}
        for j in range(len(mesh_struct_metadata[i]["primitives"])):
            try:
                mesh_filename = mdl_filename + '/{0}_{1}_{2:02d}'.format(i, safe_filename, j)
                fmt = read_fmt(mesh_filename + '.fmt')
                ib = list(chain.from_iterable(read_ib(mesh_filename + '.ib', fmt)))
                vb = read_vb(mesh_filename + '.vb', fmt)
            except FileNotFoundError:
                if kuro_ver > 1:
                    print("Submesh {0} not found, generating an empty submesh...".format(mesh_filename))
                    if has_parsed_original_file == False:
                        with open(mdl_filename + '.mdl', "rb") as f:
                            mdl_data = f.read()
                        mdl_data = decryptCLE(mdl_data)
                        mesh_struct = obtain_mesh_data(mdl_data)
                        has_parsed_original_file = True
                    # Generate an empty submesh
                    fmt = make_fmt_struct(mesh_struct["mesh_buffers"][i][j])
                    ib = []
                    vb = mesh_struct["mesh_buffers"][i][j]['vb']
                else:
                    print("Submesh {0} not found, skipping...".format(mesh_filename))
                    continue
            print("Processing submesh {0}...".format(mesh_filename))
            # VGMap sanity check - Make sure the .vgmap file matches the actual skin node tree
            try:
                vgmap = read_struct_from_json(mesh_filename + '.vgmap')
                if not (all([True if x in expected_vgmap else False for x in vgmap])\
                    and all([expected_vgmap[x] == vgmap[x] for x in vgmap])):
                    print("Warning! {}.vgmap does not match the internal skin node tree!".format(mesh_filename))
                    print("This model will likely have major animation distortions and may crash the game.")
                    input("Press Enter to continue.")
            except FileNotFoundError:
                print("{}.vgmap not found, vertex group sanity check skipped.".format(mesh_filename))
            primitive_buffer = struct.pack("<I", mesh_struct_metadata[i]["primitives"][j]["material_offset"])
            if kuro_ver == 1:
                primitive_buffer += struct.pack("<I", len(vb)+1)
            elif kuro_ver > 1:
                primitive_buffer += struct.pack("<2I", len(ib), mesh_struct_metadata[i]["primitives"][j]["unk"])
            for k in range(len(vb)):
                dxgi_format = fmt["elements"][k]["Format"].split('DXGI_FORMAT_')[-1]
                dxgi_format_split = dxgi_format.split('_')
                vec_type = dxgi_format_split[1]
                vec_format = re.findall("[0-9]+",dxgi_format_split[0])
                vec_first_color = dxgi_format_split[0][0] # Should be R in most cases, but will be B if format is B8G8R8A8_UNORM
                vec_elements = len(vec_format)
                vec_stride = int(int(vec_format[0]) * vec_elements / 8)
                reverse_colors = False # COLOR is BGR in Kuro 2
                match vb[k]["SemanticName"]:
                    case "POSITION":
                        type_int = 0
                    case "NORMAL":
                        type_int = 1
                    case "TANGENT":
                        type_int = 2
                    case "COLOR":
                        type_int = 3
                        if kuro_ver == 1: # Forcing 32-bit float since Kuro 1 uses float
                            if vec_first_color == 'B':
                                reverse_colors = True
                            vec_type = 'FLOAT'
                            vec_stride = 4 * vec_elements
                        elif kuro_ver == 2: # Forcing 8-bit unorm since Kuro 2 models use 8-bit UNORM
                            if vec_first_color == 'R':
                                reverse_colors = True
                            vec_type = 'UNORM'
                            vec_stride = vec_elements
                    case "TEXCOORD":
                        type_int = 4
                    case "BLENDWEIGHTS":
                        type_int = 5
                    case "BLENDINDICES":
                        type_int = 6
                if reverse_colors == True and vec_elements == 4: # vec_elements should ALWAYS be 4 with COLOR, but just in case
                    current_buffer = [[x[2],x[1],x[0],x[3]] for x in vb[k]["Buffer"]]
                else:
                    current_buffer = vb[k]["Buffer"]
                match vec_type:
                    case "FLOAT":
                        element_type = 'f'
                        data_list = list(chain.from_iterable(current_buffer))
                    case "UINT":
                        element_type = 'I' # Assuming 32-bit since Kuro models all use 32-bit
                        data_list = list(chain.from_iterable(current_buffer))
                    case "UNORM":
                        element_type = 'B'
                        float_max = ((2**8)-1)
                        data_list = [int(round(min(max(x,0), 1) * float_max)) for x in list(chain.from_iterable(current_buffer))]
                raw_buffer = struct.pack("<{0}{1}".format(len(data_list), element_type), *data_list)
                if kuro_ver == 1:
                    primitive_buffer += struct.pack("<3I", type_int, len(raw_buffer), vec_stride) + raw_buffer
                elif kuro_ver > 1:
                    prim_output_header += struct.pack("<5I", type_int, len(raw_buffer), vec_stride, i, j)
                    prim_output_data += raw_buffer
                    prim_buffer_count += 1
            # After VB, need to add IB
            # Making assumptions here that it will always be in Rxx_UINT format, saves a bunch of code
            vec_stride = int(int(re.findall("[0-9]+",fmt["format"].split('DXGI_FORMAT_')[-1].split('_')[0])[0]) / 8)
            raw_ibuffer = struct.pack("<{0}I".format(len(ib), element_type), *ib)
            if kuro_ver == 1:
                primitive_buffer += struct.pack("<3I", 7, len(raw_ibuffer), vec_stride) + raw_ibuffer
            elif kuro_ver > 1:
                prim_output_header += struct.pack("<5I", 7, len(raw_ibuffer), vec_stride, i, j)
                prim_output_data += raw_ibuffer
                prim_buffer_count += 1
            mesh_block += primitive_buffer
            meshes += 1
        mesh_block = struct.pack("<I", meshes) + mesh_block
        if "nodes" in mesh_struct_metadata[i].keys():
            node_count = len(mesh_struct_metadata[i]["nodes"])
        else:
            node_count = 0
        node_block = struct.pack("<I", node_count)
        if node_count > 0:
            for j in range(node_count):
                node_block += make_pascal_string(mesh_struct_metadata[i]["nodes"][j]["name"])
                node_block += struct.pack("<16f", *list(chain.from_iterable(mesh_struct_metadata[i]["nodes"][j]["matrix"])))
        mesh_block += node_block
        raw_section2 = struct.pack("<3fI3f4I", *mesh_struct_metadata[i]["section2"]["data"])
        section2_block = struct.pack("<I", len(raw_section2)) + raw_section2
        mesh_block = make_pascal_string(mesh_struct_metadata[i]["name"]) + struct.pack("<I", len(mesh_block)) + mesh_block + section2_block
        output_buffer += mesh_block
        mesh_section_buffer = struct.pack("<2I", 1, len(output_buffer)) + output_buffer
        primitive_section_buffer = bytes()
        if kuro_ver > 1: # Primitives in a separate section #4
            primitive_output_buffer = struct.pack("<I", prim_buffer_count) + prim_output_header + prim_output_data
            primitive_section_buffer += struct.pack("<2I", 4, len(primitive_output_buffer)) + primitive_output_buffer
    return(mesh_section_buffer, primitive_section_buffer)

def process_mdl (mdl_file, change_compression = False, force_kuro_version = False):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    print("Processing {0}...".format(mdl_file))
    if mdl_data[0:4] in [b"F9BA", b"C9BA", b"D9BA"]:
        compressed = True
        mdl_data = decryptCLE(mdl_data)
    else:
        compressed = False
    if obtain_material_data(mdl_data) == False:
        print("Skipping {0} as it is not a model file.".format(mdl_file))
        return False
    kuro_ver = get_kuro_ver(mdl_data)
    try: # Attempt to get MDL version from JSON file, if this fails just use version number embedded in MDL
        json_kuro_ver = read_struct_from_json(mdl_file[:-4] + '/mdl_version.json')['mdl_version']
        if json_kuro_ver > 0 and json_kuro_ver <= kuro_ver:
            kuro_ver = json_kuro_ver
    except:
        print("{0}/mdl_version.json missing or unreadable, reading data from {0}.mdl instead...".format(mdl_file[:-4]))
    # Command line option overrides JSON file
    if force_kuro_version != False and force_kuro_version < kuro_ver:
        kuro_ver = force_kuro_version
    skeleton_data = build_skeleton_section(mdl_file[:-4], kuro_ver)
    material_data = build_material_section(mdl_file[:-4], kuro_ver)
    mesh_data, primitive_data = build_mesh_section(mdl_file[:-4], kuro_ver)
    new_mdl_data = insert_model_data(mdl_data, skeleton_data, material_data, mesh_data, primitive_data, kuro_ver)
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
        parser.add_argument('-f', '--force_version', help="Force compile at a specific Kuro version (must be equal to or lower than original)", type=int, choices=range(1,3))
        parser.add_argument('-c', '--change_compression', help="Change compression (compressed to uncompressed or vice versa)", action="store_true")
        parser.add_argument('mdl_filename', help="Name of mdl file to import into (required).")
        args = parser.parse_args()
        if args.force_version == None:
            force_kuro_version = False
        else:
            force_kuro_version = args.force_version
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, change_compression = args.change_compression, force_kuro_version = force_kuro_version)
    else:
        mdl_files = glob.glob('*.mdl')
        mdl_files = [x for x in mdl_files if os.path.isdir(x[:-4])]
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
