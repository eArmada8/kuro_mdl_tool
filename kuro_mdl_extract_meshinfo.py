# Research tool to understand ED9 / Kuro no Kiseki models in mdl format.  Not yet useful.
# Based on Uyjulian's script.
# Usage:  Run by itself without commandline arguments and it will read only the mesh section of
# every model it finds in the folder and output JSON files.
#
# For command line options (including option to dump vertices), run:
# /path/to/python3 kuro_mdl_extract_meshinfo.py
#
# Requires both blowfish and zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install blowfish zstandard
#
# GitHub eArmada8/misc_kiseki

import io, struct, sys, os, glob, json, blowfish, operator, zstandard

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

def obtain_mesh_data (mesh_section_bytes, read_vertices = False):
    with io.BytesIO(mesh_section_bytes) as f:
        blocks, = struct.unpack("<I",f.read(4))
        mesh_blocks = []
        for i in range(blocks):
            mesh_block = {}
            mesh_block["name"] = read_pascal_string(f).decode("ASCII")
            mesh_block["size"], = struct.unpack("<I",f.read(4))
            mesh_block["offset"] = f.tell()
            mesh_block["primitive_count"], = struct.unpack("<I",f.read(4))
            primitives = []
            for j in range(mesh_block["primitive_count"]):
                primitive = {}
                primitive["material_offset"], primitive["num_of_elements"] = struct.unpack("<2I",f.read(8))
                elements = []
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
                            element_type = 'H'
                    if read_vertices == False:
                        f.seek(element["size"],1) # Skipping actual data
                    else:
                        element["Buffer"] = []
                        match element_type:
                            case 'f':
                                for l in range(element["count"]):
                                    element["Buffer"].append(struct.unpack("<{0}f".format(int(element["stride"]/4)), f.read(element["stride"])))
                            case 'I':
                                for l in range(element["count"]):
                                    element["Buffer"].append(struct.unpack("<{0}I".format(int(element["stride"]/4)), f.read(element["stride"])))
                            case 'H':
                                for l in range(element["count"]):
                                    element["Buffer"].append(struct.unpack("<{0}H".format(int(element["stride"]/2)), f.read(element["stride"])))
                    elements.append(element)
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
        return(mesh_blocks)

def process_mdl (mdl_file, read_vertices = False, overwrite = False):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    mdl_data = decryptCLE(mdl_data)
    mesh_data = isolate_mesh_data(mdl_data)
    mesh_struct = obtain_mesh_data(mesh_data, read_vertices)
    json_filename = mdl_file + '.json'
    if os.path.exists(json_filename) and (overwrite == False):
        if str(input(json_filename + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(json_filename):
        with open(json_filename, 'wb') as f:
            f.write(json.dumps(mesh_struct, indent=4).encode("utf-8"))

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to convert file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--dumpvertices', help="Decode vertex buffers", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('mdl_filename', help="Name of mdl file to convert (required).")
        args = parser.parse_args()
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, read_vertices = args.dumpvertices, overwrite = args.overwrite)
    else:
        mdl_files = glob.glob('*.mdl')
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
