# Research tool to understand ED9 / Kuro no Kiseki models in mdl format.  Dumps meshes for
# import into Blender.  Based on Uyjulian's script.
# Usage:  Run by itself without commandline arguments and it will read only the mesh section of
# every model it finds in the folder and output fmt / ib / vb files.
#
# For command line options (including option to dump vertices), run:
# /path/to/python3 kuro_mdl_export_meshes.py
#
# Requires both blowfish and zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install blowfish zstandard
#
# GitHub eArmada8/misc_kiseki

import io, struct, sys, os, glob, json, blowfish, operator, zstandard
from itertools import chain
from lib_fmtibvb import *

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
    while (magic in to_decrypt) or (magic in to_decompress):
        if (magic in to_decrypt):
            result = b"".join(cipher.decrypt_ctr(file_content[8:], dec_counter))
        elif(magic in to_decompress):
            decompressor = zstandard.ZstdDecompressor()
            result = decompressor.decompress(file_content[8:])
        file_content = result
        magic = file_content[0:4]

    return result

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

def obtain_mesh_data (mesh_section_bytes):
    with io.BytesIO(mesh_section_bytes) as f:
        blocks, = struct.unpack("<I",f.read(4))
        mesh_blocks = []
        mesh_block_buffers = []
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
                primitive["material_offset"], primitive["num_of_elements"] = struct.unpack("<2I",f.read(8))
                elements = []
                ibvb = {}
                buffers = []
                semantic_index = [0,0,0,0,0,0,0,0]
                aligned_byte_offset = 0
                for k in range(primitive["num_of_elements"]):
                    element = {}
                    element["type_int"], element["size"], element["stride"] = struct.unpack("<3I",f.read(12))
                    element["offset"] = f.tell()
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
                            element["Semantic"] = "UNKNOWN"
                            element_type = 'f'
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
                    buffer["stride"] = element["stride"]
                    buffer["count"] = element["count"]
                    buffer_data = []
                    match element_type:
                        case 'f':
                            format_colors = ['R32','B32','G32','A32','D32']
                            for l in range(element["count"]):
                                buffer_data.append(struct.unpack("<{0}f".format(int(element["stride"]/4)), f.read(element["stride"])))
                                format_string = "".join(format_colors[0:int(element["stride"]/4)]) + "_FLOAT"
                        case 'I':
                            format_colors = ['R32','B32','G32','A32','D32']
                            for l in range(element["count"]):
                                buffer_data.append(struct.unpack("<{0}I".format(int(element["stride"]/4)), f.read(element["stride"])))
                                format_string = "".join(format_colors[0:int(element["stride"]/4)]) + "_UINT"
                        case 'H':
                            format_colors = ['R16','B16','G16','A16','D16']
                            for l in range(element["count"]):
                                buffer_data.append(struct.unpack("<{0}H".format(int(element["stride"]/2)), f.read(element["stride"])))
                                format_string = "".join(format_colors[0:int(element["stride"]/2)]) + "_UINT"
                    buffer["fmt"] = {"id": str(k),
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
                        aligned_byte_offset += element["stride"]
                        buffer["Buffer"] = buffer_data
                        buffers.append(buffer)
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
            section2 = {}
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
        return(mesh_data)

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

def write_fmt_ib_vb (mesh_buffers, filename, node_list = False, complete_maps = False):
    fmt_struct = make_fmt_struct(mesh_buffers)
    write_fmt(fmt_struct, filename + '.fmt')
    write_ib(mesh_buffers['ib']['Buffer'], filename +  '.ib', fmt_struct)
    write_vb(mesh_buffers['vb'], filename +  '.vb', fmt_struct)
    if not node_list == False:
        active_nodes = list(set(list(chain.from_iterable([x["Buffer"] for x in mesh_buffers["vb"] \
            if x["fmt"]["SemanticName"] == 'BLENDINDICES'][0]))))
        vgmap_json = {}
        for i in range(len(node_list)):
            if (i in active_nodes) or (complete_maps == True):
                vgmap_json[node_list[i]["name"]] = i
        with open(filename + '.vgmap', 'wb') as f:
            f.write(json.dumps(vgmap_json, indent=4).encode("utf-8"))
    return

def process_mdl (mdl_file, complete_maps = False, overwrite = False):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    mdl_data = decryptCLE(mdl_data)
    mesh_data = isolate_mesh_data(mdl_data)
    mesh_struct = obtain_mesh_data(mesh_data)
    json_filename = mdl_file[:-4] + '/mdl_info.json'
    if os.path.exists(mdl_file[:-4]) and (os.path.isdir(mdl_file[:-4])) and (overwrite == False):
        if str(input(mdl_file[:-4] + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(mdl_file[:-4]):
        if not os.path.exists(mdl_file[:-4]):
            os.mkdir(mdl_file[:-4])
        with open(json_filename, 'wb') as f:
            f.write(json.dumps(mesh_struct["mesh_blocks"], indent=4).encode("utf-8"))
        for i in range(len(mesh_struct["mesh_buffers"])):
            for j in range(len(mesh_struct["mesh_buffers"][i])):
                write_fmt_ib_vb(mesh_struct["mesh_buffers"][i][j], mdl_file[:-4] +\
                    '/{0}_{1}_{2:02d}'.format(i, mesh_struct["mesh_blocks"][i]["name"], j),\
                    node_list = mesh_struct["mesh_blocks"][i]["nodes"], complete_maps = complete_maps)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to convert file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire mesh skeleton", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('mdl_filename', help="Name of mdl file to convert (required).")
        args = parser.parse_args()
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, complete_maps = args.completemaps, overwrite = args.overwrite)
    else:
        mdl_files = glob.glob('*.mdl')
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
