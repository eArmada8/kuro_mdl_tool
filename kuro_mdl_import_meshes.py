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

import io, struct, sys, os, shutil, glob, base64, json, blowfish, operator, zstandard
from itertools import chain
from lib_fmtibvb import *
from kuro_mdl_export_meshes import *

def compressCLE(file_content):
    magic = file_content[0:4]
    compressed_magic = b"D9BA"
    result = file_content
    if not magic == compressed_magic: # Don't compress files that are already compressed:
        compressor = zstandard.ZstdCompressor(level = 12, write_checksum = True)
        result = compressor.compress(file_content)
        result = compressed_magic + struct.pack("<I", len(result)) + result
    return result

def make_pascal_string(string):
    return struct.pack("<B", len(string)) + string.encode("utf8")

# Primitive data is in Kuro 2.  In Kuro 1, it will be an empty buffer.
def insert_model_data (mdl_data, material_section_data, mesh_section_data, primitive_section_data):
    with io.BytesIO(mdl_data) as f:
        new_mdl_data = f.read(12) #Header
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
            if section_info["type"] == 4: # Primitive section to replace
                section = primitive_section_data
            new_mdl_data += section
        # Catch the null bytes at the end of the stream
        f.seek(current_offset,0)
        new_mdl_data += f.read()
        return(new_mdl_data)

def build_material_section (mdl_filename, kuro_ver = 1):
    # Will read data from JSON file, or load original data from the mdl file if JSON is missing
    try:
        material_struct = read_struct_from_json(mdl_filename + "/material_info.json")
    except:
        with open(mdl_filename + '.mdl', "rb") as f:
            mdl_data = f.read()
        mdl_data = decryptCLE(mdl_data)
        material_data = isolate_material_data(mdl_data)
        material_struct = obtain_material_data(mesh_data)
    output_buffer = struct.pack("<I", len(material_struct))
    for i in range(len(material_struct)):
        material_block = make_pascal_string(material_struct[i]['material_name']) \
            + make_pascal_string(material_struct[i]['shader_name']) \
            + make_pascal_string(material_struct[i]['str3'])
        texture_blocks = bytes()
        texture_block_count = 0
        for j in range(len(material_struct[i]['textures'])):
            texture_blocks += make_pascal_string(material_struct[i]['textures'][j]['texture_image_name']) \
                + struct.pack("<3i", material_struct[i]['textures'][j]['texture_slot'],\
                material_struct[i]['textures'][j]['unk_01'], material_struct[i]['textures'][j]['unk_02'])
            if kuro_ver > 1:
                texture_blocks += struct.pack("<2i", material_struct[i]['textures'][j]['unk_03'],\
                    material_struct[i]['textures'][j]['unk_04'])
            texture_block_count += 1
        material_block += struct.pack("<I", texture_block_count) + texture_blocks
        shader_elements = bytes()
        shader_element_count = 0
        for j in range(len(material_struct[i]['shaders'])):
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
    try:
        mesh_struct = read_struct_from_json(mdl_filename + "/mesh_info.json")
    except:
        with open(mdl_filename + '.mdl', "rb") as f:
            mdl_data = f.read()
        mdl_data = decryptCLE(mdl_data)
        mesh_struct = obtain_mesh_data(mdl_data)["mesh_blocks"]
    output_buffer = struct.pack("<I", len(mesh_struct))
    if kuro_ver > 1:
        prim_output_header = bytes()
        prim_output_data = bytes()
        prim_buffer_count = 0
    for i in range(len(mesh_struct)):
        mesh_block = bytes()
        meshes = 0 # Keep count of actual meshes imported, in case some have been deleted
        for j in range(len(mesh_struct[i]["primitives"])):
            try:
                mesh_filename = mdl_filename + '/{0}_{1}_{2:02d}'.format(i, mesh_struct[i]["name"], j)
                fmt = read_fmt(mesh_filename + '.fmt')
                ib = list(chain.from_iterable(read_ib(mesh_filename + '.ib', fmt)))
                vb = read_vb(mesh_filename + '.vb', fmt)
                primitive_buffer = struct.pack("<I", mesh_struct[i]["primitives"][j]["material_offset"])
                if kuro_ver == 1:
                    primitive_buffer += struct.pack("<I", len(vb)+1)
                elif kuro_ver > 1:
                    primitive_buffer += struct.pack("<2I", len(ib), mesh_struct[i]["primitives"][j]["unk"])
                for k in range(len(vb)):
                    match vb[k]["SemanticName"]:
                        case "POSITION":
                            type_int = 0
                        case "NORMAL":
                            type_int = 1
                        case "TANGENT":
                            type_int = 2
                        case "UNKNOWN":
                            type_int = 3
                        case "TEXCOORD":
                            type_int = 4
                        case "BLENDWEIGHTS":
                            type_int = 5
                        case "BLENDINDICES":
                            type_int = 6
                    dxgi_format = fmt["elements"][k]["Format"].split('DXGI_FORMAT_')[-1]
                    dxgi_format_split = dxgi_format.split('_')
                    vec_format = re.findall("[0-9]+",dxgi_format_split[0])
                    vec_elements = len(vec_format)
                    vec_stride = int(int(vec_format[0]) * len(vec_format) / 8)
                    match dxgi_format_split[1]:
                        case "FLOAT":
                            element_type = 'f'
                        case "UINT":
                            element_type = 'I' # Assuming 32-bit since Kuro models all use 32-bit
                    raw_buffer = struct.pack("<{0}{1}".format(vec_elements*len(vb[k]["Buffer"]), element_type), *list(chain.from_iterable(vb[k]["Buffer"])))
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
            except:
                pass
        mesh_block = struct.pack("<I", meshes) + mesh_block
        if "nodes" in mesh_struct[i].keys():
            node_count = len(mesh_struct[i]["nodes"])
        else:
            node_count = 0
        node_block = struct.pack("<I", node_count)
        if node_count > 0:
            for j in range(node_count):
                node_block += make_pascal_string(mesh_struct[i]["nodes"][j]["name"])
                node_block += struct.pack("<16f", *list(chain.from_iterable(mesh_struct[i]["nodes"][j]["matrix"])))
        mesh_block += node_block
        raw_section2 = struct.pack("<3fI3f4I", *mesh_struct[i]["section2"]["data"])
        section2_block = struct.pack("<I", len(raw_section2)) + raw_section2
        mesh_block = make_pascal_string(mesh_struct[i]["name"]) + struct.pack("<I", len(mesh_block)) + mesh_block + section2_block
        output_buffer += mesh_block
        mesh_section_buffer = struct.pack("<2I", 1, len(output_buffer)) + output_buffer
        primitive_section_buffer = bytes()
        if kuro_ver > 1: # Primitives in a separate section #4
            primitive_output_buffer = struct.pack("<I", prim_buffer_count) + prim_output_header + prim_output_data
            primitive_section_buffer += struct.pack("<2I", 4, len(primitive_output_buffer)) + primitive_output_buffer
    return(mesh_section_buffer, primitive_section_buffer)

def process_mdl (mdl_file, compress = True):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    print("Processing {0}...".format(mdl_file))
    mdl_data = decryptCLE(mdl_data)
    kuro_ver = get_kuro_ver(mdl_data)
    material_data = build_material_section(mdl_file[:-4], kuro_ver = kuro_ver)
    mesh_data, primitive_data = build_mesh_section(mdl_file[:-4], kuro_ver = kuro_ver)
    new_mdl_data = insert_model_data(mdl_data, material_data, mesh_data, primitive_data)
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
    if compress == True:
        new_mdl_data = compressCLE(new_mdl_data)
    with open(mdl_file,'wb') as f:
        f.write(new_mdl_data)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to import into file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-u', '--uncompressed', help="Do not apply zstandard compression", action="store_false")
        parser.add_argument('mdl_filename', help="Name of mdl file to import into (required).")
        args = parser.parse_args()
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, compress = args.uncompressed)
    else:
        mdl_files = glob.glob('*.mdl')
        mdl_files = [x for x in mdl_files if os.path.isdir(x[:-4])]
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
