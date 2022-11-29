# Tool to convert ED9 / Kuro no Kiseki models in mdl format to glTF.  Not as useful as uyjulian's
# script, but is meant to be used as a research tool.
#
# Usage:  Run by itself without commandline arguments and it will convert mdl files that it finds.
#
# For command line options (including option to dump vertices), run:
# /path/to/python3 kuro_mdl_to_basic_gltf.py --help
#
# Requires both blowfish and zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install blowfish zstandard
#
# GitHub eArmada8/misc_kiseki

import io, struct, sys, os, glob, numpy, copy, json
from pyquaternion import Quaternion
from kuro_mdl_export_meshes import *

# Adapted from Julian Uy's ED9 MDL parser, thank you
def rpy2quat(rot_rpy): # Roll Pitch Yaw
    cr = numpy.cos(rot_rpy[0] * 0.5)
    sr = numpy.sin(rot_rpy[0] * 0.5)
    cp = numpy.cos(rot_rpy[1] * 0.5)
    sp = numpy.sin(rot_rpy[1] * 0.5)
    cy = numpy.cos(rot_rpy[2] * 0.5)
    sy = numpy.sin(rot_rpy[2] * 0.5)
    #wxyz
    return([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,\
        cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy])

# Takes quat/pos relative to parent, and reorients / moves to be relative to the origin.
# Parent bone must already be transformed.
def calc_abs_rotation_position(bone, parent_bone):
    q1 = Quaternion(bone['q_wxyz'])
    qp = Quaternion(parent_bone['abs_q'])
    bone["abs_q"] = list((qp * q1).unit)
    bone["abs_p"] = (numpy.array(qp.rotate(bone['pos_xyz'])) + parent_bone['abs_p']).tolist()
    return(bone)

def isolate_skeleton_data (mdl_data):
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
        # Kuro models seem to only have one skeleton section
        skeleton_section = [x for x in contents if x["type"] == 2][0]
        f.seek(skeleton_section["section_start_offset"],0)
        skeleton_section_data = f.read(skeleton_section["size"])
        return(skeleton_section_data)

def obtain_skeleton_data (skeleton_section_bytes):
    with io.BytesIO(skeleton_section_bytes) as f:
        blocks, = struct.unpack("<I",f.read(4))
        node_blocks = []
        # Materials are not grouped like meshes, but roughly follow the same order
        for i in range(blocks):
            node_block = {}
            node_block['id_referenceonly'] = i # Not used at all for repacking, purely for convenience
            node_block['name'] = read_pascal_string(f).decode("ASCII")
            # node_block['type']: 0 = transform only, 1 = skin child, 2 = mesh
            node_block['type'], node_block['mesh_index'] = struct.unpack("<Ii",f.read(8))
            node_block['pos_xyz'] = struct.unpack("<3f",f.read(12))
            node_block['unknown_quat'] = struct.unpack("<4f",f.read(16))
            node_block['skin_mesh'], = struct.unpack("<I",f.read(4))
            node_block['rotation_euler_rpy'] = struct.unpack("<3f",f.read(12))
            node_block['q_wxyz'] = rpy2quat(node_block['rotation_euler_rpy'])
            node_block['scale'] = struct.unpack("<3f",f.read(12))
            node_block['unknown'] = struct.unpack("<3f",f.read(12))
            child_count, = struct.unpack("<I",f.read(4))
            node_block['children'] = []
            for j in range(child_count):
                child, = struct.unpack("<I",f.read(4))
                node_block['children'].append(child)
            node_blocks.append(node_block)
        for i in range(len(node_blocks)):
            if i == 0:
                node_blocks[i]['parentID'] = -1
                node_blocks[i]['abs_q'] = node_blocks[i]['q_wxyz']
                node_blocks[i]['abs_p'] = node_blocks[i]['pos_xyz']
            else:
                node_blocks[i]['parentID'] = [x['id_referenceonly'] for x in node_blocks if i in x['children']][0]
                node_blocks[i] = calc_abs_rotation_position(node_blocks[i], node_blocks[node_blocks[i]['parentID']])  
    return(node_blocks)

# This only handles formats compatible with Kuro MDL (Float, UINT)
def convert_format_for_gltf(dxgi_format):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        vec_bits = int(vec_format[0])
        vec_elements = len(vec_format)
        if numtype == 'FLOAT':
            componentType = 5126
            componentStride = len(re.findall('[0-9]+', dxgi_format)) * 4
        elif numtype == 'UINT':
            if vec_bits == 32:
                componentType = 5125
                componentStride = len(re.findall('[0-9]+', dxgi_format)) * 4
            elif vec_bits == 16:
                componentType = 5123
                componentStride = len(re.findall('[0-9]+', dxgi_format)) * 2
            elif vec_bits == 8:
                componentType = 5121
                componentStride = len(re.findall('[0-9]+', dxgi_format))
        accessor_types = ["SCALAR", "VEC2", "VEC3", "VEC4"]
        accessor_type = accessor_types[len(re.findall('[0-9]+', dxgi_format))-1]
        return({'format': dxgi_format, 'componentType': componentType,\
            'componentStride': componentStride, 'accessor_type': accessor_type})
    else:
        return(False)

def convert_fmt_for_gltf(fmt):
    new_fmt = copy.deepcopy(fmt)
    stride = 0
    new_semantics = {'BLENDWEIGHTS': 'WEIGHTS', 'BLENDINDICES': 'JOINTS'}
    need_index = ['WEIGHTS', 'JOINTS', 'COLOR', 'TEXCOORD']
    for i in range(len(fmt['elements'])):
        if new_fmt['elements'][i]['SemanticName'] in new_semantics.keys():
            new_fmt['elements'][i]['SemanticName'] = new_semantics[new_fmt['elements'][i]['SemanticName']]
        new_info = convert_format_for_gltf(fmt['elements'][i]['Format'])
        new_fmt['elements'][i]['Format'] = new_info['format']
        if new_fmt['elements'][i]['SemanticName'] in need_index:
            new_fmt['elements'][i]['SemanticName'] = new_fmt['elements'][i]['SemanticName'] + '_' +\
                new_fmt['elements'][i]['SemanticIndex']
        new_fmt['elements'][i]['AlignedByteOffset'] = stride
        new_fmt['elements'][i]['componentType'] = new_info['componentType']
        new_fmt['elements'][i]['componentStride'] = new_info['componentStride']
        new_fmt['elements'][i]['accessor_type'] = new_info['accessor_type']
        stride += new_info['componentStride']
    index_fmt = convert_format_for_gltf(fmt['format'])
    new_fmt['format'] = index_fmt['format']
    new_fmt['componentType'] = index_fmt['componentType']
    new_fmt['componentStride'] = index_fmt['componentStride']
    new_fmt['accessor_type'] = index_fmt['accessor_type']
    new_fmt['stride'] = stride
    return(new_fmt)

def fix_strides(submesh):
    offset = 0
    for i in range(len(submesh['vb'])):
        submesh['vb'][i]['fmt']['AlignedByteOffset'] = str(offset)
        submesh['vb'][i]['stride'] = get_stride_from_dxgi_format(submesh['vb'][i]['fmt']['Format'])
        offset += submesh['vb'][i]['stride']
    return(submesh)

def local_to_global_bone_indices(mesh_index, mesh_struct, skel_struct):
    local_node_dict = {}
    for i in range(len(mesh_struct["mesh_blocks"][mesh_index]["nodes"])):
        local_node_dict[i] = mesh_struct["mesh_blocks"][mesh_index]["nodes"][i]["name"]
    global_node_dict = {}
    for key in local_node_dict:
        try:
            global_node_dict[key] = [x for x in skel_struct if x['name'] == local_node_dict[key]][0]['id_referenceonly']
        except IndexError: #Not sure why some names are missing
            try: # Attempt to remove suffix, e.g. Head_Top becomes Head
                global_node_dict[key] = [x for x in skel_struct if x['name'] == "_".join(local_node_dict[key].split('_')[:-1])][0]['id_referenceonly']
            except IndexError:
                global_node_dict[key] = 0
    return(global_node_dict)

def fix_weight_groups(submesh, global_node_dict):
    # Avoid some strange behavior from variable assignment, will copy instead
    new_submesh = copy.deepcopy(submesh)
    bone_element_index = int([x['fmt'] for x in new_submesh['vb'] if x['fmt']['SemanticName'] == 'BLENDINDICES'][0]['id'])
    weight_element_index = int([x['fmt'] for x in new_submesh['vb'] if x['fmt']['SemanticName'] == 'BLENDWEIGHTS'][0]['id'])
    #glTF does not support 32-bit bone indices for some reason, hopefully skeletons will fit into 16-bit
    new_submesh['vb'][bone_element_index]['fmt']['Format'] = re.sub("32","16", new_submesh['vb'][bone_element_index]['fmt']['Format'])
    new_submesh = fix_strides(new_submesh)
    # Remove invalid weight numbers (<0.00001 and negative numbers)
    #for i in range(len(new_submesh['vb'][weight_element_index]['Buffer'])):
        #new_submesh['vb'][weight_element_index]['Buffer'][i] = list(new_submesh['vb'][weight_element_index]['Buffer'][i])
        #for j in range(len(new_submesh['vb'][weight_element_index]['Buffer'][i])):
            #if (new_submesh['vb'][weight_element_index]['Buffer'][i][j] < 0.0000001):
                #new_submesh['vb'][weight_element_index]['Buffer'][i][j] = 0
    return(new_submesh)

def fix_tangent_length(submesh):
    tangent_element_index = int([x for x in submesh['fmt']['elements'] if x['SemanticName'] == 'TANGENT'][0]['id'])
    for i in range(len(submesh['vb'][tangent_element_index]['Buffer'])):
        submesh['vb'][tangent_element_index]['Buffer'][i][0:3] =\
            (submesh['vb'][tangent_element_index]['Buffer'][i][0:3] / numpy.linalg.norm(submesh['vb'][tangent_element_index]['Buffer'][i][0:3])).tolist()
    return(submesh)

def write_glTF(filename, mesh_struct, skel_struct):
    gltf_data = {}
    gltf_data['asset'] = { 'version': '2.0' }
    gltf_data['accessors'] = []
    gltf_data['bufferViews'] = []
    gltf_data['buffers'] = []
    gltf_data['meshes'] = []
    gltf_data['nodes'] = []
    gltf_data['scenes'] = [{}]
    gltf_data['scenes'][0]['nodes'] = [0]
    gltf_data['scene'] = 0
    gltf_data['skins'] = []
    giant_buffer = bytes()
    mesh_nodes = []
    buffer_view = 0
    for i in range(len(skel_struct)):
        node = {'children': skel_struct[i]['children'], 'name': skel_struct[i]['name']}
        if not list(skel_struct[i]['q_wxyz']) == [1,0,0,0]:
            node['rotation'] = skel_struct[i]['q_wxyz'][1:]+[skel_struct[i]['q_wxyz'][0]] #xyzw
        if not list(skel_struct[i]['scale']) == [1,1,1]:
            node['scale'] = skel_struct[i]['scale']
        if not list(skel_struct[i]['pos_xyz']) == [0,0,0]:
            node['translation'] = skel_struct[i]['pos_xyz']
        gltf_data['nodes'].append(node)
    for i in range(len(gltf_data['nodes'])):
        if len(gltf_data['nodes'][i]['children']) == 0:
            del(gltf_data['nodes'][i]['children'])
    for i in range(len(mesh_struct["mesh_buffers"])): # Mesh
        if mesh_struct["mesh_blocks"][i]["node_count"] > 0:
            has_skeleton = True
        else:
            has_skeleton = False
        if has_skeleton:
            global_node_dict = local_to_global_bone_indices(i, mesh_struct, skel_struct)
        for j in range(len(mesh_struct["mesh_buffers"][i])): # Submesh
            print("Processing {0} submesh {1}...".format(mesh_struct["mesh_blocks"][i]["name"], j))
            if has_skeleton:
                submesh = fix_weight_groups(mesh_struct["mesh_buffers"][i][j], global_node_dict)
            else:
                submesh = mesh_struct["mesh_buffers"][i][j]
            gltf_fmt = convert_fmt_for_gltf(make_fmt_struct(submesh))
            primitive = {"attributes":{}}
            vb_stream = io.BytesIO()
            write_vb_stream(submesh['vb'], vb_stream, gltf_fmt, e='<', interleave = False)
            block_offset = len(giant_buffer)
            for element in range(len(gltf_fmt['elements'])):
                primitive["attributes"][gltf_fmt['elements'][element]['SemanticName']]\
                    = len(gltf_data['accessors'])
                gltf_data['accessors'].append({"bufferView" : buffer_view,\
                    "componentType": gltf_fmt['elements'][element]['componentType'],\
                    "count": len(submesh['vb'][element]['Buffer']),\
                    "type": gltf_fmt['elements'][element]['accessor_type']})
                if gltf_fmt['elements'][element]['SemanticName'] == 'POSITION':
                    gltf_data['accessors'][-1]['max'] =\
                        [max([x[0] for x in submesh['vb'][element]['Buffer']]),\
                         max([x[1] for x in submesh['vb'][element]['Buffer']]),\
                         max([x[2] for x in submesh['vb'][element]['Buffer']])]
                    gltf_data['accessors'][-1]['min'] =\
                        [min([x[0] for x in submesh['vb'][element]['Buffer']]),\
                         min([x[1] for x in submesh['vb'][element]['Buffer']]),\
                         min([x[2] for x in submesh['vb'][element]['Buffer']])]
                gltf_data['bufferViews'].append({"buffer": 0,\
                    "byteOffset": block_offset,\
                    "byteLength": len(submesh['vb'][element]['Buffer']) *\
                    gltf_fmt['elements'][element]['componentStride'],\
                    "target" : 34962})
                block_offset += len(submesh['vb'][element]['Buffer']) *\
                    gltf_fmt['elements'][element]['componentStride']
                buffer_view += 1
            vb_stream.seek(0)
            giant_buffer += vb_stream.read()
            vb_stream.close()
            del(vb_stream)
            ib_stream = io.BytesIO()
            write_ib_stream(submesh['ib']['Buffer'], ib_stream, gltf_fmt, e='<')
            # IB is 16-bit so can be misaligned, unlike VB (which only has 32-, 64- and 128-bit types in Kuro)
            while (ib_stream.tell() % 4) > 0:
                ib_stream.write(b'\x00')
            primitive["indices"] = len(gltf_data['accessors'])
            gltf_data['accessors'].append({"bufferView" : buffer_view,\
                "componentType": gltf_fmt['componentType'],\
                "count": len([index for triangle in submesh['ib']['Buffer'] for index in triangle]),\
                "type": gltf_fmt['accessor_type']})
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": len(giant_buffer),\
                "byteLength": ib_stream.tell(),\
                "target" : 34963})
            buffer_view += 1
            ib_stream.seek(0)
            giant_buffer += ib_stream.read()
            ib_stream.close()
            del(ib_stream)
            primitive["mode"] = 4 #TRIANGLES
            mesh_nodes.append(len(gltf_data['nodes']))
            gltf_data['nodes'].append({'mesh': len(gltf_data['meshes']), 'name': "Mesh_{0}_{1}".format(i,j)})
            gltf_data['meshes'].append({"primitives": [primitive], "name": "Mesh_{0}_{1}".format(i,j)})
            if has_skeleton:
                gltf_data['nodes'][-1]['skin'] = len(gltf_data['skins'])
            del(submesh)
        if has_skeleton:
            inv_mtx_buffer = bytes()
            for k in global_node_dict:
                mtx = Quaternion(skel_struct[global_node_dict[k]]['abs_q']).transformation_matrix
                [mtx[0,3],mtx[1,3],mtx[2,3]] = skel_struct[global_node_dict[k]]['abs_p']
                inv_bind_mtx = numpy.linalg.inv(mtx)
                inv_bind_mtx = numpy.ndarray.transpose(inv_bind_mtx)
                inv_mtx_buffer += struct.pack("<16f", *[num for row in inv_bind_mtx for num in row])
            gltf_data['skins'].append({"inverseBindMatrices": len(gltf_data['accessors']), "joints": list(global_node_dict.values())})
            gltf_data['accessors'].append({"bufferView" : buffer_view,\
                "componentType": 5126,\
                "count": len(global_node_dict),\
                "type": "MAT4"})
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": len(giant_buffer),\
                "byteLength": len(inv_mtx_buffer)})
            buffer_view += 1
            giant_buffer += inv_mtx_buffer
    gltf_data['scenes'][0]['nodes'].extend(mesh_nodes)
    gltf_data['buffers'].append({"byteLength": len(giant_buffer), "uri": filename[:-4]+'.bin'})
    with open(filename[:-4]+'.bin', 'wb') as f:
        f.write(giant_buffer)
    with open(filename[:-4]+'.gltf', 'wb') as f:
        f.write(json.dumps(gltf_data, indent=4).encode("utf-8"))

def process_mdl (mdl_file, overwrite = False):
    with open(mdl_file, "rb") as f:
        mdl_data = f.read()
    print("Processing {0}...".format(mdl_file))
    mdl_data = decryptCLE(mdl_data)
    mesh_data = isolate_mesh_data(mdl_data)
    mesh_struct = obtain_mesh_data(mesh_data, trim_for_gpu = True)
    skel_data = isolate_skeleton_data(mdl_data)
    skel_struct = obtain_skeleton_data(skel_data)
    if os.path.exists(mdl_file[:-4] + '.gltf') and (overwrite == False):
        if str(input(mdl_file[:-4] + ".gltf exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(mdl_file[:-4] + '.gltf'):
        write_glTF(mdl_file, mesh_struct, skel_struct)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('mdl_filename', help="Name of mdl file to process.")
        args = parser.parse_args()
        if os.path.exists(args.mdl_filename) and args.mdl_filename[-4:].lower() == '.mdl':
            process_mdl(args.mdl_filename, overwrite = args.overwrite)
    else:
        mdl_files = glob.glob('*.mdl')
        for i in range(len(mdl_files)):
            process_mdl(mdl_files[i])
