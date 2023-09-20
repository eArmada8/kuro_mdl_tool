# Tool to extract the meshes, skins and skeleton from glTF files.
# Usage:  Run by itself without commandline arguments and it will read every .glb/.gltf file
# and extract the skeleton.
#
# For command line options, run:
# /path/to/python3 kuro_gltf_to_skeleton.py --help
#
# Requires both pyquaternion and pygltflib.
# These can be installed by:
# /path/to/python3 -m pip install numpy pyquaternion pygltflib
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import numpy, math, json, io, struct, re, os, sys, glob
    from pyquaternion import Quaternion
    from pygltflib import GLTF2
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

# This script outputs non-empty vgmaps by default, change the following line to True to change
complete_vgmaps_default = False

def accessor_stride(gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    componentSize = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    return(componentCount[accessor.type] * componentSize[accessor.componentType])

#Does not support sparse
def read_stream (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    bufferview = gltf.bufferViews[accessor.bufferView]
    buffer = gltf.buffers[bufferview.buffer]
    componentType = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    componentFormat = "<{0}{1}".format(componentCount[accessor.type],\
        componentType[accessor.componentType])
    componentStride = accessor_stride(gltf, accessor_num)
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

def dxgi_format (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    RGBAD = ['R','G','B','A','D']
    bytesize = {5120:'8', 5121: '8', 5122: '16', 5123: '16', 5125: '32', 5126: '32'}
    elementtype = {5120: 'SINT', 5121: 'UINT', 5122: 'SINT', 5123: 'UINT', 5125: 'UINT', 5126: 'FLOAT'}
    normelementtype = {5120: 'SNORM', 5121: 'UNORM', 5122: 'SNORM', 5123: 'UNORM'}
    numelements = {'SCALAR':1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
    dxgi_format = "".join([RGBAD[i]+bytesize[accessor.componentType] \
        for i in range(numelements[accessor.type])]) + '_'
    if accessor.normalized == True:
        dxgi_format += normelementtype[accessor.componentType]
    else:
        dxgi_format += elementtype[accessor.componentType]
    return(dxgi_format)

#adapted from concept3d @ stackexchange, thank you!
def calc_tangents (submesh):
    #If IB is flat list, convert to triangles
    if isinstance(submesh['ib'][0], list) is False:
        triangles = [[submesh['ib'][i*3],submesh['ib'][i*3+1], submesh['ib'][i*3+2]] for i in range(len(submesh['ib'])//3)]
    else:
        triangles = list(submesh['ib'])
    posBuffer = [x['Buffer'] for x in submesh['vb'] if x['SemanticName'] == 'POSITION'][0]
    normBuffer = [numpy.array(x['Buffer']) for x in submesh['vb'] if x['SemanticName'] == 'NORMAL'][0]
    texBuffer = [x['Buffer'] for x in submesh['vb'] if x['SemanticName'] == 'TEXCOORD' and x['SemanticIndex'] == '0'][0]
    tanBuffer = []
    binormalBuffer = []
    tan1 = [numpy.array([0.0,0.0,0.0]) for i in range(len(posBuffer))]
    tan2 = [numpy.array([0.0,0.0,0.0]) for i in range(len(posBuffer))]
    for i in range(len(triangles)):
        x1 = posBuffer[triangles[i][1]][0] - posBuffer[triangles[i][0]][0]
        x2 = posBuffer[triangles[i][1]][0] - posBuffer[triangles[i][0]][0]
        y1 = posBuffer[triangles[i][1]][1] - posBuffer[triangles[i][0]][1]
        y2 = posBuffer[triangles[i][2]][1] - posBuffer[triangles[i][0]][1]
        z1 = posBuffer[triangles[i][1]][2] - posBuffer[triangles[i][0]][2]
        z2 = posBuffer[triangles[i][2]][2] - posBuffer[triangles[i][0]][2]
        s1 = texBuffer[triangles[i][1]][0] - texBuffer[triangles[i][0]][0]
        s2 = texBuffer[triangles[i][2]][0] - texBuffer[triangles[i][0]][0]
        t1 = texBuffer[triangles[i][1]][1] - texBuffer[triangles[i][0]][1]
        t2 = texBuffer[triangles[i][2]][1] - texBuffer[triangles[i][0]][1]
        if (s1 * t2 - s2 * t1) == 0:
            r = 1.0 / 0.000001
        else:
            r = 1.0 / (s1 * t2 - s2 * t1)
        sdir = numpy.array([(t2 * x1 - t1 * x2) * r, (t2 * y1 - t1 * y2) * r,\
                    (t2 * z1 - t1 * z2) * r]);
        tdir = numpy.array([(s1 * x2 - s2 * x1) * r, (s1 * y2 - s2 * y1) * r,\
                    (s1 * z2 - s2 * z1) * r]);
        tan1[triangles[i][0]] += sdir
        tan1[triangles[i][1]] += sdir
        tan1[triangles[i][2]] += sdir
        tan2[triangles[i][0]] += tdir
        tan2[triangles[i][1]] += tdir
        tan2[triangles[i][2]] += tdir
    for a in range(len(posBuffer)):
        vector = tan1[a] - normBuffer[a] * numpy.dot(normBuffer[a], tan1[a])
        if not numpy.linalg.norm(vector) == 0.0:
            vector = vector / numpy.linalg.norm(vector)
        if numpy.dot(numpy.cross(normBuffer[a], tan1[a]), tan2[a]) < 0:
            handedness = -1
        else:
            handedness = 1
        tanBuffer.append(vector.tolist())
        binormalBuffer.append((numpy.cross(normBuffer[a], vector) * handedness).tolist())
    return (tanBuffer, binormalBuffer)

def dump_meshes (mesh_node, gltf, complete_maps = False):
    basename = mesh_node.name
    mesh = gltf.meshes[mesh_node.mesh]
    if mesh_node.skin is not None:
        skin = gltf.skins[mesh_node.skin]
        vgmap = {gltf.nodes[skin.joints[i]].name:i for i in range(len(skin.joints))}
    submeshes = []
    for i in range(len(mesh.primitives)):
        submesh = {'name': '{0}_{1:02d}'.format(basename, i)}
        print("Reading mesh {0}...".format(submesh['name']))
        tops = {0: 'pointlist', 4: 'trianglelist', 5: 'trianglestrip'}
        submesh['fmt'] = {'stride': '0', 'topology': tops[mesh.primitives[i].mode],\
            #'format': "DXGI_FORMAT_{0}".format(dxgi_format(gltf, mesh.primitives[i].indices)), 'elements': []}
            'format': "DXGI_FORMAT_R32_UINT", 'elements': []} # Force 32-bit indices
        submesh['ib'] = [x for y in read_stream(gltf, mesh.primitives[i].indices) for x in y]
        submesh['vb'] = []
        elements = []
        AlignedByteOffset = 0
        Semantics = {'POSITION': ['POSITION','0'], 'NORMAL': ['NORMAL','0'], 'TANGENT': ['TANGENT','0'],\
            'TEXCOORD_0': ['TEXCOORD','0'], 'TEXCOORD_1': ['TEXCOORD','1'], 'TEXCOORD_2': ['TEXCOORD','2'],\
            'COLOR_0': ['COLOR','0'], 'COLOR_1': ['COLOR','1'], 'WEIGHTS_0': ['BLENDWEIGHTS','0'],\
            'JOINTS_0': ['BLENDINDICES','0']}
        for semantic in Semantics:
            if hasattr(mesh.primitives[i].attributes, semantic):
                accessor = getattr(mesh.primitives[i].attributes, semantic)
                if accessor is not None:
                    submesh['vb'].append({'SemanticName': Semantics[semantic][0], 'SemanticIndex': Semantics[semantic][1],\
                        'Buffer': read_stream(gltf, accessor)})
                    dxgiformat = dxgi_format (gltf, accessor)
                    accstride = accessor_stride(gltf, accessor)
                    if semantic == 'JOINTS_0': # Kuro needs 128-bit blendindices, I believe
                        dxgiformat = 'R32G32B32A32_UINT'
                        accstride = 16
                    element = {'id': str(len(elements)), 'SemanticName': Semantics[semantic][0],\
                                'SemanticIndex': Semantics[semantic][1], 'Format': dxgiformat,\
                                'InputSlot': '0', 'AlignedByteOffset': str(AlignedByteOffset),\
                                'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}
                    elements.append(element)
                    AlignedByteOffset += accstride
        if 'TANGENT' not in [x['SemanticName'] for x in submesh['vb']]:
            tangentBuf, binormalBuf = calc_tangents (submesh)
            submesh['vb'].append({'SemanticName': 'TANGENT', 'SemanticIndex': '0', 'Buffer': tangentBuf})
            element = {'id': str(len(elements)), 'SemanticName': 'TANGENT',\
                'SemanticIndex': '0', 'Format': 'R32G32B32_FLOAT',\
                'InputSlot': '0', 'AlignedByteOffset': str(AlignedByteOffset),\
                'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}
            elements.append(element)
            AlignedByteOffset += 12
            #submesh['vb'].append({'SemanticName': 'BINORMAL', 'SemanticIndex': '0',\
                        #'Buffer': binormalBuf})
            #element = {'id': str(len(elements)), 'SemanticName': 'BINORMAL',\
                #'SemanticIndex': '0', 'Format': 'R32G32B32_FLOAT',\
                #'InputSlot': '0', 'AlignedByteOffset': str(AlignedByteOffset),\
                #'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}
            #elements.append(element)
            #AlignedByteOffset += 12
        submesh['fmt']['stride'] = str(AlignedByteOffset)
        submesh['fmt']['elements'] = elements
        if mesh_node.skin is not None:
            vgs_i = [i for i in range(len(submesh['vb'])) if submesh['vb'][i]['SemanticName'] == 'BLENDINDICES']
            if complete_maps == False and len(vgs_i) > 0:
                used_vgs = list(set([x for y in submesh['vb'][vgs_i[0]]['Buffer'] for x in y]))
                submesh['vgmap'] = {k:v for (k,v) in vgmap.items() if v in used_vgs }
            else:
                submesh['vgmap'] = dict(vgmap)
        submesh['uvmap'] = [{'m_index':i*3, 'm_inputSet':i} for i in range(len([x for x in elements if x['SemanticName']=='TEXCOORD']))]
        if mesh.primitives[i].material is not None:
            submesh['material'] = gltf.materials[mesh.primitives[i].material].name
        else:
            submesh['material'] = 'None'
        submeshes.append(submesh)
    return(submeshes)

def build_skeleton_struct (model_gltf, metadata = {}):
    if 'locators' in metadata:
        locators = metadata['locators']
    else:
        locators = False
    if 'non_skin_meshes' in metadata:
        skin_joints = [i for i in range(len(model_gltf.nodes)) if model_gltf.nodes[i].name not in metadata['non_skin_meshes']]
    else:
        skin_joints = sorted(list(set([x for y in model_gltf.skins for x in y.joints])))
    mesh_nodes = [i for i in range(len(model_gltf.nodes)) if model_gltf.nodes[i].mesh is not None]
    skel_struct = []
    for i in range(len(model_gltf.nodes)):
        skel_node = { "id_referenceonly": i, "name": model_gltf.nodes[i].name }
        transform = {}
        if model_gltf.nodes[i].matrix is not None:
                transform["pos_xyz"] = model_gltf.nodes[j].matrix[12:15]
                transform["scale"] = [numpy.linalg.norm(model_gltf.nodes[j].matrix[0:3]),\
                    numpy.linalg.norm(model_gltf.nodes[j].matrix[4:7]),\
                    numpy.linalg.norm(model_gltf.nodes[j].matrix[8:11])]
                r = numpy.array([(gltf.nodes[j].matrix[0:3]/transform["scale"][0]).tolist()+[0],\
                    (gltf.nodes[j].matrix[4:7]/transform["scale"][1]).tolist()+[0],\
                    (gltf.nodes[j].matrix[8:11]/transform["scale"][2]).tolist()+[0],[0,0,0,1]])
                q = Quaternion(matrix=r)
                transform["rotation_euler_rpy"] = [math.atan2(2.0*(q[2]*q[3] + q[0]*q[1]), q[0]*q[0] - q[1]*q[1] - q[2]*q[2] + q[3]*q[3]),\
                    math.asin(-2.0*(q[1]*q[3] - q[0]*q[2])),\
                    math.atan2(2.0*(q[1]*q[2] + q[0]*q[3]), q[0]*q[0] + q[1]*q[1] - q[2]*q[2] - q[3]*q[3])]
        else:
            if model_gltf.nodes[i].translation is not None:
                transform["pos_xyz"] = model_gltf.nodes[i].translation
            else:
                transform["pos_xyz"] = [0.0,0.0,0.0]
            if model_gltf.nodes[i].rotation is not None:
                q = Quaternion(model_gltf.nodes[i].rotation[3], model_gltf.nodes[i].rotation[0],\
                    model_gltf.nodes[i].rotation[1], model_gltf.nodes[i].rotation[2])
                transform["rotation_euler_rpy"] = [math.atan2(2.0*(q[2]*q[3] + q[0]*q[1]), q[0]*q[0] - q[1]*q[1] - q[2]*q[2] + q[3]*q[3]),\
                    math.asin(-2.0*(q[1]*q[3] - q[0]*q[2])),\
                    math.atan2(2.0*(q[1]*q[2] + q[0]*q[3]), q[0]*q[0] + q[1]*q[1] - q[2]*q[2] - q[3]*q[3])]
            else:
                transform["rotation_euler_rpy"] = [0.0,0.0,0.0]
            if model_gltf.nodes[i].scale is not None:
                transform["scale"] = model_gltf.nodes[i].scale
            else:
                transform["scale"] = [1.0,1.0,1.0]
        if i in mesh_nodes:
            skel_node['type'] = 2
            skel_node['mesh_index'] = model_gltf.nodes[i].mesh
        else:
            if not locators == False:
                if model_gltf.nodes[i].name in locators:
                    skel_node['type'] = 0
                else:
                    skel_node['type'] = 1
            else:
                if transform["rotation_euler_rpy"] == [0.0,0.0,0.0] and transform["scale"] == [1.0,1.0,1.0]:
                    skel_node['type'] = 0
                else:
                    skel_node['type'] = 1
            skel_node['mesh_index'] = -1
        skel_node['pos_xyz'] = transform["pos_xyz"]
        skel_node['unknown_quat'] = [0.0,0.0,0.0,1.0]
        if i in skin_joints:
            skel_node['skin_mesh'] = 2
        else:
            skel_node['skin_mesh'] = 0
        skel_node['rotation_euler_rpy'] = transform["rotation_euler_rpy"]
        skel_node['scale'] = transform["scale"]
        skel_node['unknown'] = [0.0,0.0,0.0]
        skel_node['children'] = []
        if model_gltf.nodes[i].children is not None:
            skel_node['children'] = model_gltf.nodes[i].children
        skel_struct.append(skel_node)
    return(skel_struct)

def define_bounding_box(composite_vbs):
    # Initialize bounding box - I have no idea why this works, but it does.
    box = {'min_x': True, 'min_y': True, 'min_z': True, 'max_x': False, 'max_y': False, 'max_z': False}
    # Check every position coordinate and spread out
    for i in range(len(composite_vbs)):
        element = int([x['id'] for x in composite_vbs[i]['fmt']['elements'] if x['SemanticName'] == 'POSITION'][0])
        #if len(composite_vbs[i]['vb'][element]['Buffer']) > 0:
        for j in range(len(composite_vbs[i]['vb'][element]['Buffer'])):
            box['min_x'] = min(box['min_x'], composite_vbs[i]['vb'][element]['Buffer'][j][0])
            box['min_y'] = min(box['min_y'], composite_vbs[i]['vb'][element]['Buffer'][j][1])
            box['min_z'] = min(box['min_z'], composite_vbs[i]['vb'][element]['Buffer'][j][2])
            box['max_x'] = max(box['max_x'], composite_vbs[i]['vb'][element]['Buffer'][j][0])
            box['max_y'] = max(box['max_y'], composite_vbs[i]['vb'][element]['Buffer'][j][1])
            box['max_z'] = max(box['max_z'], composite_vbs[i]['vb'][element]['Buffer'][j][2])
    return(box)

def process_gltf (gltf_filename, complete_maps = complete_vgmaps_default, overwrite = False):
    print("Processing {0}...".format(gltf_filename))
    try:
        model_gltf = GLTF2().load(gltf_filename)
    except:
        print("File {} not found, or is invalid, skipping...".format(gltf_filename))
        return False
    try:
        metadata = read_struct_from_json(".".join(gltf_filename.split('.')[:-1])+".metadata")
    except:
        metadata = {}
    model_name = gltf_filename.split('.gl')[0]
    if os.path.exists(model_name) and (os.path.isdir(model_name)) and (overwrite == False):
        if str(input(model_name + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(model_name):
        if not os.path.exists(model_name):
            os.mkdir(model_name)
        skel_struct = build_skeleton_struct (model_gltf, metadata)
        mesh_nodes = [x for x in model_gltf.nodes if x.mesh is not None]
        mesh_metadata = []
        for mesh_node in mesh_nodes:
            submeshes = dump_meshes(mesh_node, model_gltf, complete_maps = complete_maps)
            mesh_node_metadata = { 'name': mesh_node.name, 'primitives': [] }
            for i in range(len(submeshes)):
                write_fmt(submeshes[i]['fmt'], '{0}/{1}_{2}.fmt'.format(model_name, mesh_node.mesh, submeshes[i]['name']))
                write_ib(submeshes[i]['ib'], '{0}/{1}_{2}.ib'.format(model_name, mesh_node.mesh, submeshes[i]['name']), submeshes[i]['fmt'])
                write_vb(submeshes[i]['vb'], '{0}/{1}_{2}.vb'.format(model_name, mesh_node.mesh, submeshes[i]['name']), submeshes[i]['fmt'])
                if 'vgmap' in submeshes[i]:
                    with open('{0}/{1}_{2}.vgmap'.format(model_name, mesh_node.mesh, submeshes[i]['name']), 'wb') as f:
                        f.write(json.dumps(submeshes[i]['vgmap'], indent=4).encode("utf-8"))
                mesh_node_metadata['primitives'].append({'id_referenceonly': i,\
                    'material': model_gltf.materials[model_gltf.meshes[mesh_node.mesh].primitives[i].material].name})
            if not mesh_node.skin is None:
                ibmtx_raw = read_stream(model_gltf, model_gltf.skins[mesh_node.skin].inverseBindMatrices)
                bind_mtx = [numpy.linalg.inv(numpy.array([x[0:4],x[4:8],x[8:12],x[12:16]]).transpose()).transpose().tolist() for x in ibmtx_raw]
                joint_names = [model_gltf.nodes[x].name for x in model_gltf.skins[mesh_node.skin].joints]
                mesh_node_metadata['nodes'] = [{'name': joint_names[i], 'matrix': bind_mtx[i]} for i in range(len(bind_mtx))]
            bbox = define_bounding_box(submeshes)
            mesh_node_metadata['section2'] = {'data': [bbox['min_x'], bbox['min_y'], bbox['min_z'], 0, bbox['max_x'], bbox['max_y'], bbox['max_z'], 0, 0, 0, 0]}
            mesh_metadata.append(mesh_node_metadata)
        with open('{0}/skeleton.json'.format(model_name), "wb") as f:
            f.write(json.dumps(skel_struct, indent=4).encode("utf-8"))    
        with open('{0}/mesh_info.json'.format(model_name), "wb") as f:
            f.write(json.dumps(mesh_metadata, indent=4).encode("utf-8"))    
        with open('{0}/mdl_version.json'.format(model_name), 'wb') as f:
            f.write(json.dumps({'mdl_version': 1}, indent=4).encode("utf-8"))
    return True

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
        if complete_vgmaps_default == True:
            parser.add_argument('-p', '--partialmaps', help="Provide vgmaps with non-empty groups only", action="store_false")
        else:
            parser.add_argument('-c', '--completemaps', help="Provide vgmaps with entire mesh skeleton", action="store_true")
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('gltf_filename', help="Name of gltf file to export from (required).")
        args = parser.parse_args()
        if complete_vgmaps_default == True:
            complete_maps = args.partialmaps
        else:
            complete_maps = args.completemaps
        if os.path.exists(args.gltf_filename) and len(args.gltf_filename[-4:].lower().split('.gl')) > 1:
            process_gltf(args.gltf_filename, complete_maps = complete_maps, overwrite = args.overwrite)
    else:
        gltf_files = glob.glob('*.gl*')
        for i in range(len(gltf_files)):
            process_gltf(gltf_files[i])

