# Tool to manipulate  ED9 / Kuro no Kiseki models in mdl format.  Dumps meshes for
# import into Blender.  Based on Uyjulian's script.
# Usage:  Run by itself without commandline arguments and it will read only the mesh section of
# every model it finds in the folder and output fmt / ib / vb files.
#
# For command line options (including option to dump vertices), run:
# /path/to/python3 kuro_mdl_export_meshes.py --help
#
# Requires both blowfish and zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install blowfish zstandard
#
# GitHub eArmada8/misc_kiseki

import io, struct, sys, os, glob, base64, json, blowfish, operator, zstandard
from itertools import chain
from lib_fmtibvb import *

# This script outputs non-empty vgmaps by default, change the following line to True to change
complete_vgmaps_default = False

# Thank you to authors of Kuro Tools for this decrypt function
# https://github.com/nnguyen259/KuroTools
def decryptCLE(file_content):
    key = b"\x16\x4B\x7D\x0F\x4F\xA7\x4C\xAC\xD3\x7A\x06\xD9\xF8\x6D\x20\x94"
    IV = b"\x9D\x8F\x9D\xA1\x49\x60\xCC\x4C"
    cipher = blowfish.Cipher(key, byte_order = "big")
    iv = struct.unpack(">Q", IV)
    dec_counter = blowfish.ctr_counter(iv[0], f = operator.add)

    magic = file_content[0:4]
    to_decrypt = [b"F9BA", b"C9BA"]
    to_decompress = [b"D9BA"]
    result = file_content
    while (magic in to_decrypt) or (magic in to_decompress):
        if (magic in to_decrypt):
            result = b"".join(cipher.decrypt_ctr(file_content[8:], dec_counter))
        elif(magic in to_decompress):
            decompressor = zstandard.ZstdDecompressor()
            result = decompressor.decompress(file_content[8:])
        file_content = result
        magic = file_content[0:4]

    return result

def get_kuro_ver (mdl_data):
    if mdl_data[4] == 1:
        return(1)
    else:
        return(2)

# From Julian Uy's ED9 MDL parser, thank you
def read_pascal_string(f):
    sz = int.from_bytes(f.read(1), byteorder="little")
    return f.read(sz)

def isolate_mesh_data (mdl_data):
    with io.BytesIO(mdl_data) as f:
        mdl_header = struct.unpack("<III",f.read(12))
        if not mdl_header[0] == 0x204c444d:
            sys.exit()
        contents = []
        while True:
            current_offset = f.tell()
            section_info = {}
            try:
                section_info["type"], section_info["size"] = struct.unpack("<II",f.read(8))
            except:
                break
            section_info["section_start_offset"] = f.tell()
            contents.append(section_info)
            f.seek(section_info["size"],1) # Move forward to the next section
        # Kuro models seem to only have one mesh section
        mesh_section = [x for x in contents if x["type"] == 1][0]
        f.seek(mesh_section["section_start_offset"],0)
        mesh_section_data = f.read(mesh_section["size"])
        return(mesh_section_data)

# Kuro 2 has separate primitive section
def isolate_primitive_data (mdl_data):
    with io.BytesIO(mdl_data) as f:
        mdl_header = struct.unpack("<III",f.read(12))
        if not mdl_header[0] == 0x204c444d:
            sys.exit()
        contents = []
        while True:
            current_offset = f.tell()
            section_info = {}
            try:
                section_info["type"], section_info["size"] = struct.unpack("<II",f.read(8))
            except:
                break
            section_info["section_start_offset"] = f.tell()
            contents.append(section_info)
            f.seek(section_info["size"],1) # Move forward to the next section
        # Kuro models seem to only have one primitive section?
        primitive_section = [x for x in contents if x["type"] == 4][0]
        f.seek(primitive_section["section_start_offset"],0)
        primitive_section_data = f.read(primitive_section["size"])
        return(primitive_section_data)

def parse_primitive_header (primitive_data):
    with io.BytesIO(primitive_data) as f:
        blocks, = struct.unpack("<I",f.read(4))
        data_offset = blocks * 20 + 4
        primitive_info = []
        for i in range(blocks):
            element = {}
            element["type_int"], element["size"], element["stride"], element["mesh"],\
                element["submesh"] = struct.unpack("<5I",f.read(20))
            element["offset"] = data_offset
            data_offset += element["size"]
            primitive_info.append(element)
    return(primitive_info)
            
def obtain_mesh_data (mdl_data, trim_for_gpu = False):
    kuro_ver = get_kuro_ver(mdl_data)
    mesh_data = isolate_mesh_data(mdl_data)
    if kuro_ver > 1:
        primitive_data = isolate_primitive_data(mdl_data)
        primitive_info = parse_primitive_header(primitive_data)
        prim = io.BytesIO(primitive_data)
    with io.BytesIO(mesh_data) as f:
        blocks, = struct.unpack("<I",f.read(4))
        mesh_blocks = []
        mesh_block_buffers = []
        # Meshes are separated into groups (hair, body, shadow)
        for i in range(blocks):
            mesh_block = {}
            mesh_block["name"] = read_pascal_string(f).decode("ASCII")
            mesh_block["size"], = struct.unpack("<I",f.read(4))
            mesh_block["offset"] = f.tell()
            mesh_block["primitive_count"], = struct.unpack("<I",f.read(4))
            primitives = []
            mesh_buffers = []
            for j in range(mesh_block["primitive_count"]):
                primitive = {}
                primitive["id_referenceonly"] = j # Not used at all for repacking, purely for convenience
                primitive["material_offset"], = struct.unpack("<I",f.read(4))
                if kuro_ver == 1:
                    primitive["num_of_elements"], = struct.unpack("<I",f.read(4))
                elif kuro_ver > 1:
                    primitive["num_of_elements"] = len([x for x in primitive_info if x['mesh'] == i and x['submesh'] == j])
                    primitive["triangle_count"], primitive["unk"] = struct.unpack("<2I",f.read(8))
                elements = []
                ibvb = {}
                buffers = []
                semantic_index = [0,0,0,0,0,0,0,0] # Counters for multiple indicies (e.g. TEXCOORD1, 2, etc)
                aligned_byte_offset = 0
                element_num = 0 # Needed for accurate count in fmt when skipping elements
                for k in range(primitive["num_of_elements"]):
                    element = {}
                    if kuro_ver == 1:
                        element["type_int"], element["size"], element["stride"] = struct.unpack("<3I",f.read(12))
                        element["offset"] = f.tell()
                    elif kuro_ver > 1:
                        prim_element = [x for x in primitive_info if x['mesh'] == i and x['submesh'] == j][k]
                        element["type_int"], element["size"], element["stride"], element["offset"] =\
                            prim_element["type_int"], prim_element["size"], prim_element["stride"], prim_element["offset"]
                        prim.seek(prim_element["offset"])
                    element["count"] = int(element["size"]/element["stride"])
                    # Vertex reading here!!
                    match element["type_int"]:
                        case 0:
                            element["Semantic"] = "POSITION"
                            element_type = 'f'
                        case 1:
                            element["Semantic"] = "NORMAL"
                            element_type = 'f'
                        case 2:
                            element["Semantic"] = "TANGENT"
                            element_type = 'f'
                        case 3:
                            element["Semantic"] = "COLOR"
                            element_type = 'U'
                        case 4:
                            element["Semantic"] = "TEXCOORD"
                            element_type = 'f'
                        case 5:
                            element["Semantic"] = "BLENDWEIGHTS"
                            element_type = 'f'
                        case 6:
                            element["Semantic"] = "BLENDINDICES"
                            element_type = 'I'
                        case 7:
                            element["Semantic"] = "TRIANGLES"
                            element_type = 'I'
                    element_index = semantic_index[element["type_int"]]
                    semantic_index[element["type_int"]] += 1
                    buffer = {}
                    buffer["stride"] = element["stride"] # Purely for convenience, used later to make fmt
                    buffer_data = []
                    match element_type:
                        case 'f': #32-bit FLOAT
                            format_colors = ['R32','B32','G32','A32','D32']
                            for l in range(element["count"]):
                                if kuro_ver == 1:
                                    buffer_data.append(struct.unpack("<{0}f".format(int(element["stride"]/4)), f.read(element["stride"])))
                                elif kuro_ver > 1:
                                    buffer_data.append(struct.unpack("<{0}f".format(int(element["stride"]/4)), prim.read(element["stride"])))
                                format_string = "".join(format_colors[0:int(element["stride"]/4)]) + "_FLOAT"
                        case 'I': #32-bit UINT
                            format_colors = ['R32','B32','G32','A32','D32']
                            for l in range(element["count"]):
                                if kuro_ver == 1:
                                    buffer_data.append(struct.unpack("<{0}I".format(int(element["stride"]/4)), f.read(element["stride"])))
                                elif kuro_ver > 1:
                                    buffer_data.append(struct.unpack("<{0}I".format(int(element["stride"]/4)), prim.read(element["stride"])))
                                format_string = "".join(format_colors[0:int(element["stride"]/4)]) + "_UINT"
                        case 'H': #16-bit UINT, not sure this is used by Kuro at all
                            format_colors = ['R16','B16','G16','A16','D16']
                            for l in range(element["count"]):
                                if kuro_ver == 1:
                                    buffer_data.append(struct.unpack("<{0}H".format(int(element["stride"]/2)), f.read(element["stride"])))
                                elif kuro_ver > 1:
                                    buffer_data.append(struct.unpack("<{0}H".format(int(element["stride"]/2)), prim.read(element["stride"])))
                                format_string = "".join(format_colors[0:int(element["stride"]/2)]) + "_UINT"
                        case 'U': #8-bit UNORM
                            format_colors = ['R8','B8','G8','A8']
                            float_max = ((2**8)-1) #Assuming all UNORM is 8-bit
                            for l in range(element["count"]):
                                if kuro_ver == 1:
                                    buffer_data.append([x / float_max for x in struct.unpack("<{0}B".format(int(element["stride"])), f.read(element["stride"]))])
                                elif kuro_ver > 1:
                                    buffer_data.append([x / float_max for x in struct.unpack("<{0}B".format(int(element["stride"])), prim.read(element["stride"]))])
                                format_string = "".join(format_colors[0:int(element["stride"])]) + "_UNORM"
                    buffer["fmt"] = {"id": str(element_num),
                        "SemanticName": element["Semantic"],\
                        "SemanticIndex": str(element_index),\
                        "Format": format_string,\
                        "InputSlot": "0",\
                        "AlignedByteOffset": str(aligned_byte_offset),\
                        "InputSlotClass": "per-vertex",\
                        "InstanceDataStepRate": "0"}
                    if element["type_int"] == 7:
                        ib = {}
                        ib["format"] = "DXGI_FORMAT_" + format_string
                        ib["Buffer"] = []
                        indices = list(chain.from_iterable(buffer_data))
                        triangle = []
                        vertex_num = 0
                        for l in range(len(indices)):
                            triangle.append(indices[l])
                            vertex_num += 1
                            if vertex_num % 3 == 0:
                                ib["Buffer"].append(triangle)
                                triangle = []
                    else:
                        # The next two lines makes the buffer fully compatible with lib_fmtibvb
                        buffer["SemanticName"] = buffer["fmt"]["SemanticName"]
                        buffer["SemanticIndex"] = buffer["fmt"]["SemanticIndex"]
                        # If Trim for GPU is on, discard texcoords above the 3rd, and the unknown buffers
                        if (trim_for_gpu == False) or (element_index < 3 and not element["type_int"] == 3):
                            aligned_byte_offset += element["stride"]
                            buffer["Buffer"] = buffer_data
                            buffers.append(buffer)
                            element_num += 1
                    elements.append(element)
                ibvb["ib"] = ib
                ibvb["vb"] = buffers
                mesh_buffers.append(ibvb)                    
                primitive["Elements"] = elements
                primitives.append(primitive)
            mesh_block["primitives"] = primitives
            mesh_block["node_count"], = struct.unpack("<I",f.read(4))
            if mesh_block["node_count"] > 0:
                nodes = []
                for j in range(mesh_block["node_count"]):
                    node = {}
                    node["name"] = read_pascal_string(f).decode("ASCII")
                    node["matrix"] = [struct.unpack("<4f",f.read(16)), struct.unpack("<4f",f.read(16)),\
                        struct.unpack("<4f",f.read(16)), struct.unpack("<4f",f.read(16))]
                    nodes.append(node)
                mesh_block["nodes"] = nodes
            section2 = {} # No idea what this is
            section2["size"], = struct.unpack("<I", f.read(4))
            if section2["size"] == 44:
                section2["data"] = struct.unpack("<3fI3f4I", f.read(44))
            else:
                f.seek(section2["size"],1)
            mesh_block["section2"] = section2
            mesh_blocks.append(mesh_block)
            mesh_block_buffers.append(mesh_buffers)
        mesh_data = {}
        mesh_data["mesh_blocks"] = mesh_blocks
        mesh_data["mesh_buffers"] = mesh_block_buffers
    if kuro_ver > 1:
        prim.close()
    return(mesh_data)

def isolate_material_data (mdl_data):
    with io.BytesIO(mdl_data) as f:
        mdl_header = struct.unpack("<III",f.read(12))
        if not mdl_header[0] == 0x204c444d:
            sys.exit()
        contents = []
        while True:
            current_offset = f.tell()
            section_info = {}
            try:
                section_info["type"], section_info["size"] = struct.unpack("<II",f.read(8))
            except:
                break
            section_info["section_start_offset"] = f.tell()
            contents.append(section_info)
            f.seek(section_info["size"],1) # Move forward to the next section
        # Kuro models seem to only have one material section
        material_section = [x for x in contents if x["type"] == 0][0]
        f.seek(material_section["section_start_offset"],0)
        material_section_data = f.read(material_section["size"])
        return(material_section_data)

def obtain_material_data (mdl_data):
    kuro_ver = get_kuro_ver(mdl_data)
    material_data = isolate_material_data(mdl_data)
    with io.BytesIO(material_data) as f:
        blocks, = struct.unpack("<I",f.read(4))
        material_blocks = []
        # Materials are not grouped like meshes, but roughly follow the same order
        for i in range(blocks):
            material_block = {}
            material_block['id_referenceonly'] = i # Not used at all for repacking, purely for convenience
            material_block['material_name'] = read_pascal_string(f).decode("ASCII")
            material_block['shader_name'] = read_pascal_string(f).decode("ASCII")
            material_block['str3'] = read_pascal_string(f).decode("ASCII")
            texture_element_count, = struct.unpack("<I",f.read(4))
            material_block['textures'] = []
            for j in range(texture_element_count):
                texture_block = {}
                texture_block['texture_image_name'] = read_pascal_string(f).decode("ASCII")
                texture_block['texture_slot'], = struct.unpack("<i",f.read(4))
                if kuro_ver > 1:
                    texture_block['unk_00'], = struct.unpack("<i",f.read(4))
                texture_block['unk_01'], texture_block['unk_02'] = struct.unpack("<2i",f.read(8))
                if kuro_ver > 1:
                    texture_block['unk_03'], = struct.unpack("<i",f.read(4))
                material_block['textures'].append(texture_block)
            shader_element_count, = struct.unpack("<I",f.read(4))
            material_block['shaders'] = []
            for j in range(shader_element_count):
                shader_block = {}
                shader_block['shader_name'] = read_pascal_string(f).decode("ASCII")
                shader_block['type_int'], = struct.unpack("<I",f.read(4))
                match shader_block['type_int']:
                    case 0 | 1:
                        shader_block['data'], = struct.unpack("<I",f.read(4))
                    case 2:
                        shader_block['data_base64'] = base64.b64encode(f.read(8)).decode()
                    case 3:
                        shader_block['data_base64'] = base64.b64encode(f.read(12)).decode()
                    case 4:
                        shader_block['data'], = struct.unpack("<f",f.read(4))
                    case 5:
                        shader_block['data'] = list(struct.unpack("<2f",f.read(8)))
                    case 6:
                        shader_block['data'] = list(struct.unpack("<3f",f.read(12)))
                    case 7:
                        shader_block['data_base64'] = base64.b64encode(f.read(16)).decode()
                    case 8:
                        shader_block['data_base64'] = base64.b64encode(f.read(64)).decode()
                    case 0xFFFFFFFF:
                        shader_block['data_base64'] = ''
                material_block['shaders'].append(shader_block)
            material_switch_count, = struct.unpack("<I",f.read(4))
            material_block['material_switches'] = []
            for j in range(material_switch_count):
                material_switch_block = {}
                material_switch_block['material_switch_name'] = read_pascal_string(f).decode("ASCII")
                material_switch_block['int2'], = struct.unpack("<i",f.read(4))
                material_block['material_switches'].append(material_switch_block)
            uv_map_index_count, = struct.unpack("<I",f.read(4))
            material_block['uv_map_indices'] = list(struct.unpack("{0}B".format(uv_map_index_count),f.read(uv_map_index_count)))
            unknown1_count, = struct.unpack("<I",f.read(4))
            material_block['unknown1'] = list(struct.unpack("{0}B".format(unknown1_count),f.read(unknown1_count)))
            material_block['unknown2'] = list(struct.unpack("<3IfI",f.read(20)))
            material_blocks.append(material_block)
        return(material_blocks)

def make_fmt_struct (mesh_buffers):
    fmt_struct = {}
    fmt_struct["stride"] = 0
    for i in range(len(mesh_buffers['vb'])):
        fmt_struct["stride"] += mesh_buffers['vb'][i]['stride']
    fmt_struct["stride"] = str(fmt_struct["stride"])
    fmt_struct["topology"] = "trianglelist"
    fmt_struct["format"] = mesh_buffers["ib"]["format"]
    fmt_struct["elements"] = [x["fmt"] for x in mesh_buffers["vb"]]
    return(fmt_struct)

def write_fmt_ib_vb (mesh_buffers, filename, node_list = False, complete_maps = False, write_empty_buffers = False):
    print("Processing submesh {0}...".format(filename))
    fmt_struct = make_fmt_struct(mesh_buffers)
    write_fmt(fmt_struct, filename + '.fmt')
    if len(mesh_buffers['ib']['Buffer']) > 0 or write_empty_buffers == True:
        write_ib(mesh_buffers['ib']['Buffer'], filename +  '.ib', fmt_struct)
        write_vb(mesh_buffers['vb'], filename +  '.vb', fmt_struct)
    if not node_list == False:
        # Find vertex groups referenced by vertices so that we can cull the empty ones
        active_nodes = list(set(list(chain.from_iterable([x["Buffer"] for x in mesh_buffers["vb"] \
            if x["fmt"]["SemanticName"] == 'BLENDINDICES'][0]))))
        vgmap_json = {}
        for i in range(len(node_list)):
            if (i in active_nodes) or (complete_maps == True):
                vgmap_json[node_list[i]["name"]] = i
        with open(filename + '.vgmap', 'wb') as f:
            f.write(json.dumps(vgmap_json, indent=4).encode("utf-8"))
    return

def process_mdl (mdl_file, complete_maps = complete_vgmaps_default, trim_for_gpu = False, overwrite = False):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    print("Processing {0}...".format(mdl_file))
    mdl_data = decryptCLE(mdl_data)
    mesh_struct = obtain_mesh_data(mdl_data, trim_for_gpu = trim_for_gpu)
    mesh_json_filename = mdl_file[:-4] + '/mesh_info.json'
    material_struct = obtain_material_data(mdl_data)
    material_json_filename = mdl_file[:-4] + '/material_info.json'
    mdl_version_json_filename = mdl_file[:-4] + '/mdl_version.json'
    if os.path.exists(mdl_file[:-4]) and (os.path.isdir(mdl_file[:-4])) and (overwrite == False):
        if str(input(mdl_file[:-4] + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(mdl_file[:-4]):
        if not os.path.exists(mdl_file[:-4]):
            os.mkdir(mdl_file[:-4])
        with open(mdl_version_json_filename, 'wb') as f:
            f.write(json.dumps({'mdl_version': get_kuro_ver(mdl_data)}, indent=4).encode("utf-8"))
        with open(mesh_json_filename, 'wb') as f:
            f.write(json.dumps(mesh_struct["mesh_blocks"], indent=4).encode("utf-8"))
        with open(material_json_filename, 'wb') as f:
            f.write(json.dumps(material_struct, indent=4).encode("utf-8"))
        for i in range(len(mesh_struct["mesh_buffers"])):
            if mesh_struct["mesh_blocks"][i]["node_count"] > 0:
                node_list = mesh_struct["mesh_blocks"][i]["nodes"]
            else:
                node_list = False
            for j in range(len(mesh_struct["mesh_buffers"][i])):
                write_fmt_ib_vb(mesh_struct["mesh_buffers"][i][j], mdl_file[:-4] +\
                    '/{0}_{1}_{2:02d}'.format(i, mesh_struct["mesh_blocks"][i]["name"], j),\
                    node_list = node_list, complete_maps = complete_maps)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        if complete_vgmaps_default == True:
            parser.add_argument('-p', '--partialmaps', help="Provide vgmaps with non-empty groups only", action="store_false")
        else:
            parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire mesh skeleton", action="store_true")
        parser.add_argument('-t', '--trim_for_gpu', help="Trim vertex buffer for GPU injection (3DMigoto)", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('mdl_filename', help="Name of mdl file to export from (required).")
        args = parser.parse_args()
        if complete_vgmaps_default == True:
            complete_maps = args.partialmaps
        else:
            complete_maps = args.completemaps
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, complete_maps = complete_maps, trim_for_gpu = args.trim_for_gpu, overwrite = args.overwrite)
    else:
        mdl_files = glob.glob('*.mdl')
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
